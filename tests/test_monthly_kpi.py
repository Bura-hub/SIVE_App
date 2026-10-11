"""
Tests del KPI mensual del inicio (calculate_monthly_consumption_kpi), con la convención de la tesis y del
mercado P2P (diseño, C10, C11 y D2): la demanda es la del circuito del Medidor 1 de cada institución configurada,
la generación la de su inversor, y el mes anterior se compara con el mismo tiempo transcurrido.
"""
from datetime import datetime, timedelta
from unittest import mock

from django.test import TestCase

from indicators.institution_config import INSTITUCIONES
from indicators.models import MonthlyConsumptionKPI
from indicators.services.date_ranges import COLOMBIA_TZ
from indicators.tasks import calculate_monthly_consumption_kpi
from scada_proxy.models import Device, DeviceCategory, Institution
from scada_proxy.tasks import upsert_measurements_page

HUDN = '40a047f8-295a-4b8a-8d2c-649ddc18e600'
AHORA = COLOMBIA_TZ.localize(datetime(2026, 7, 15, 12, 30))


class MonthlyKpiTests(TestCase):
    def setUp(self):
        cat_med = DeviceCategory.objects.create(scada_id='CAT_EM', name='electricMeter')
        cat_inv = DeviceCategory.objects.create(scada_id='CAT_INV', name='inverter')
        inst = Institution.objects.create(scada_id=HUDN, name='HUDN')
        cfg = INSTITUCIONES[HUDN]
        self.m1 = Device.objects.create(scada_id=cfg['medidor_demanda'], name='M1', category=cat_med,
                                        institution=inst)
        self.m2 = Device.objects.create(scada_id='otro-medidor', name='M2', category=cat_med, institution=inst)
        self.inv = Device.objects.create(scada_id=cfg['inversores_generacion'][0], name='Inv', category=cat_inv,
                                         institution=inst)

    @staticmethod
    def _hora(device, inicio, campo, valor):
        upsert_measurements_page(device, [
            (inicio + timedelta(minutes=2 * i), {campo: valor}) for i in range(30)
        ])

    @mock.patch('indicators.tasks.get_colombia_now', return_value=AHORA)
    def test_demanda_m1_generacion_y_mes_anterior_con_igual_tiempo(self, _now):
        h_actual = COLOMBIA_TZ.localize(datetime(2026, 7, 15, 10, 0))
        self._hora(self.m1, h_actual, 'totalActivePower', 9.0)
        self._hora(self.m2, h_actual, 'totalActivePower', 50.0)      # otro circuito: no se suma (C10)
        self._hora(self.inv, h_actual, 'acPower', 6000.0)
        # Mes anterior: una hora dentro de la ventana equivalente (15-jun 10:00) y otra fuera (20-jun).
        self._hora(self.m1, COLOMBIA_TZ.localize(datetime(2026, 6, 15, 10, 0)), 'totalActivePower', 4.0)
        self._hora(self.m1, COLOMBIA_TZ.localize(datetime(2026, 6, 20, 10, 0)), 'totalActivePower', 100.0)

        calculate_monthly_consumption_kpi.apply()
        kpi = MonthlyConsumptionKPI.objects.get(pk=1)
        self.assertAlmostEqual(kpi.total_consumption_current_month, 9.0)
        self.assertAlmostEqual(kpi.total_generation_current_month, 6.0)
        # Medidor bruto: la FV se consume en el circuito; de la red se toma D − autoconsumo.
        self.assertAlmostEqual(kpi.total_gross_consumption_current_month, 3.0)
        self.assertAlmostEqual(kpi.total_consumption_previous_month, 4.0)   # el 20-jun queda fuera (C11)
        horas = (AHORA - COLOMBIA_TZ.localize(datetime(2026, 7, 1))).total_seconds() / 3600
        self.assertAlmostEqual(kpi.avg_instantaneous_power_current_month, 6.0 * 1000 / horas)


class PlantInvertersTests(TestCase):
    def test_solo_inversores_de_plantas_vigentes_y_activo_con_datos_24h(self):
        from indicators.services.kpi import summarize_plant_inverters
        cat = DeviceCategory.objects.create(scada_id='CAT_INV', name='inverter')
        hoy = COLOMBIA_TZ.localize(datetime(2026, 7, 15, 12, 0))
        n_vigentes = 0
        for sid, cfg in INSTITUCIONES.items():
            inst = Institution.objects.create(scada_id=sid, name=cfg['nombre'])
            for inv in cfg['inversores_generacion']:
                d = Device.objects.create(scada_id=inv, name=inv[:6], category=cat, institution=inst)
                n_vigentes += 1
                if cfg['nombre'] != 'HUDN':
                    upsert_measurements_page(d, [(hoy - timedelta(hours=2), {'acPower': 1000.0})])
        Device.objects.create(scada_id='3a5eca15-cd03-4a83-8981-b432d2217344', name='Prueba', category=cat)
        r = summarize_plant_inverters(now=hoy)
        self.assertEqual(r['total'], n_vigentes)          # sin el de prueba ni los retirados
        self.assertEqual(r['active'], n_vigentes - 1)
        self.assertIn('HUDN', r['description'])
