"""
Pruebas de las correcciones de la app `external_energy` (integración con XM).

Cubre, con mocks de pydataxm:
  (a) La serie horaria de XM se agrega a nivel DIARIO: 1 registro por día con el promedio correcto.
  (b) Los ceros legítimos NO se descartan en las estadísticas (solo se filtran None/NaN).
  (c) Instanciar el servicio de XM NO altera el `requests.post` global del proceso.

Se ejecuta con: python manage.py test tests.test_external_energy_fixes
"""

import sys
import types
from datetime import date

from django.test import TestCase
from django.contrib.auth.models import User
from unittest import mock

from rest_framework.test import APIRequestFactory, force_authenticate

from external_energy import views
from external_energy.services import XMEnergyService
from external_energy.models import EnergyPrice


def _install_fake_pydataxm(dataframe):
    """Instala un módulo `pydataxm` falso en sys.modules cuyo ReadDB.request_data
    devuelve el DataFrame indicado. Devuelve los módulos originales para restaurarlos."""
    originals = {
        'pydataxm': sys.modules.get('pydataxm'),
        'pydataxm.pydataxm': sys.modules.get('pydataxm.pydataxm'),
    }

    pkg = types.ModuleType('pydataxm')
    sub = types.ModuleType('pydataxm.pydataxm')

    class ReadDB:
        def __init__(self, *args, **kwargs):
            pass

        def request_data(self, metric_id, entity, start, end):
            return dataframe

    sub.ReadDB = ReadDB
    pkg.pydataxm = sub
    sys.modules['pydataxm'] = pkg
    sys.modules['pydataxm.pydataxm'] = sub
    return originals


def _restore_modules(originals):
    for name, module in originals.items():
        if module is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = module


class HourlyToDailyAggregationTests(TestCase):
    """(a) Agregación horaria -> diaria al persistir precios."""

    def _build_hourly_dataframe(self):
        import pandas as pd

        # Dos días con 24 columnas horarias.
        # Día 1: 12 horas a 100 y 12 horas a 200 -> promedio diario = 150.
        # Día 2: 24 horas a 200               -> promedio diario = 200.
        data = {'Date': ['2026-01-01', '2026-01-02']}
        for h in range(1, 25):
            if h <= 12:
                data[f'Values_Hour{h:02d}'] = [100.0, 200.0]
            else:
                data[f'Values_Hour{h:02d}'] = [200.0, 200.0]
        return pd.DataFrame(data)

    def test_guarda_un_registro_por_dia_con_promedio(self):
        df = self._build_hourly_dataframe()
        originals = _install_fake_pydataxm(df)
        try:
            result = XMEnergyService().sync_all_data()
        finally:
            _restore_modules(originals)

        # La sincronización debe persistir sin error.
        self.assertNotIn('error', result, msg=result)

        # Un único registro por día (no 24 por el `unique` de la fecha).
        self.assertEqual(EnergyPrice.objects.count(), 2)
        self.assertEqual(result['prices_synced'], 2)

        p1 = EnergyPrice.objects.get(date=date(2026, 1, 1))
        p2 = EnergyPrice.objects.get(date=date(2026, 1, 2))
        self.assertAlmostEqual(float(p1.price_per_kwh), 150.0, places=2)
        self.assertAlmostEqual(float(p2.price_per_kwh), 200.0, places=2)
        self.assertEqual(p1.source, 'XM')

    def test_sincronizacion_repetida_no_duplica(self):
        """update_or_create deduplica sin depender de IntegrityError."""
        df = self._build_hourly_dataframe()
        originals = _install_fake_pydataxm(df)
        try:
            XMEnergyService().sync_all_data()
            second = XMEnergyService().sync_all_data()
        finally:
            _restore_modules(originals)

        self.assertEqual(EnergyPrice.objects.count(), 2)
        # En la segunda corrida no se crean nuevos, se actualizan.
        self.assertEqual(second.get('prices_created'), 0)
        self.assertEqual(second.get('prices_updated'), 2)


class ZeroValuesInStatsTests(TestCase):
    """(b) Los ceros no se descartan en las estadísticas."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username='tester_ee', password='secret123')

    def test_ceros_se_conservan_y_none_se_descarta(self):
        request = self.factory.get('/api/external-energy/generation/', {'range': 'week'})
        force_authenticate(request, user=self.user)

        fake_series = [
            {'date': '2026-01-01', 'value': 0.0},   # cero real -> se conserva
            {'date': '2026-01-02', 'value': 0.0},   # cero real -> se conserva
            {'date': '2026-01-03', 'value': 30.0},
            {'date': '2026-01-04', 'value': None},   # faltante -> se descarta
        ]

        with mock.patch('external_energy.views.XMEnergyService') as MockService:
            MockService.return_value.fetch_generation_data.return_value = fake_series
            response = views.generation_data(request)

        self.assertEqual(response.status_code, 200)
        data = response.data

        # Los ceros se conservan: el mínimo es 0 (no 30) y el promedio divide entre 3 (no 1).
        self.assertEqual(data['min_generation'], 0.0)
        self.assertEqual(data['total_generation'], 30.0)
        self.assertAlmostEqual(data['average_generation'], 10.0)  # (0 + 0 + 30) / 3
        self.assertEqual(data['max_generation'], 30.0)
        self.assertEqual(data['source'], 'XM')


class RequestsGlobalNotPatchedTests(TestCase):
    """(c) Instanciar el servicio de XM no altera el `requests.post` global."""

    def test_no_altera_requests_post_global(self):
        import requests
        from external_energy import services

        original_post = requests.post
        original_flag = services._ssl_verify
        try:
            # Forzar incluso la rama de SSL desactivado (la más peligrosa del bug original).
            services._ssl_verify = False
            services.XMEnergyService()  # instanciar dispara _check_api_availability

            self.assertIs(
                requests.post, original_post,
                "El servicio de XM alteró el requests.post global del proceso",
            )
            self.assertFalse(
                hasattr(requests, '_saved_post'),
                "El servicio dejó un monkey-patch (_saved_post) sobre requests",
            )
        finally:
            services._ssl_verify = original_flag
