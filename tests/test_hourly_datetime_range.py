"""
Tests Task A2: soporte de hora inicio/fin (datetime) en el modo horario.

`resolve_indicators_hourly_datetime_range` añade precisión de hora/minuto a la
vista horaria existente (`resolve_indicators_hourly_range`, por día). Se usa
cuando la vista recibe `start_datetime`/`end_datetime` en query params; si no,
se mantiene el comportamiento actual por día.
"""
from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from indicators.models import HourlyMeterIndicators
from indicators.services.date_ranges import (
    resolve_indicators_hourly_datetime_range,
    COLOMBIA_TZ,
)
from indicators.views import ElectricMeterIndicatorsViewSet
from scada_proxy.models import Institution, DeviceCategory, Device


class HourlyDatetimeRangeTest(TestCase):
    def test_parses_minute_precision(self):
        s, e, err = resolve_indicators_hourly_datetime_range(
            "2026-07-18T08:00", "2026-07-18T14:30")
        self.assertIsNone(err)
        self.assertEqual(s.hour, 8)
        self.assertEqual(e.hour, 14)
        self.assertEqual(e.minute, 30)
        self.assertEqual(s.utcoffset(), timedelta(hours=-5))

    def test_rejects_bad_format(self):
        s, e, err = resolve_indicators_hourly_datetime_range("18/07/2026", "x")
        self.assertIsNotNone(err)

    def test_rejects_start_after_end(self):
        s, e, err = resolve_indicators_hourly_datetime_range(
            "2026-07-18T14:00", "2026-07-18T08:00")
        self.assertIsNotNone(err)

    def test_rejects_over_31_days(self):
        start = "2026-06-01T00:00"
        end = "2026-07-03T00:00"  # 32 días
        s, e, err = resolve_indicators_hourly_datetime_range(start, end)
        self.assertIsNotNone(err)


# Las 3 vistas están decoradas con @cache_page (5 min) sobre Redis REAL (no una
# caché de test aislada). Se fuerza DummyCache para que @cache_page sea inerte
# (mismo patrón que tests/test_hourly_indicators_views.py).
@override_settings(
    ALLOWED_HOSTS=['testserver'],
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.dummy.DummyCache'}},
)
class HourlyDatetimeViewTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='tdt', password='x')
        self.factory = APIRequestFactory()
        self.inst = Institution.objects.create(scada_id='INST_DT', name='Inst DT')
        self.cat = DeviceCategory.objects.create(scada_id='CAT_DT', name='electricmeter_dt')
        self.dev = Device.objects.create(
            name='Medidor DT', scada_id='DEV_DT', category=self.cat, institution=self.inst)
        for h in (8, 12, 20):
            HourlyMeterIndicators.objects.create(
                device=self.dev, institution=self.inst,
                hour=datetime(2026, 7, 18, h, 0, tzinfo=COLOMBIA_TZ),
                net_energy_consumption_kwh=float(h))

    def _get(self, params):
        req = self.factory.get('/api/electric-meter-indicators/', params)
        force_authenticate(req, user=self.user)
        return ElectricMeterIndicatorsViewSet.as_view({'get': 'list'})(req)

    def test_datetime_range_filters_hours(self):
        resp = self._get({
            'time_range': 'hourly', 'institution_id': self.inst.id,
            'device_id': self.dev.id,
            'start_datetime': '2026-07-18T09:00', 'end_datetime': '2026-07-18T13:00'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['results']), 1)  # solo la hora 12
