# tests/test_data_availability.py
from datetime import date, datetime
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate
from scada_proxy.models import Institution, DeviceCategory, Device
from indicators.models import ElectricMeterIndicators, HourlyMeterIndicators
from indicators.views_availability import DataAvailabilityView
from indicators.services.date_ranges import COLOMBIA_TZ


@override_settings(
    ALLOWED_HOSTS=['testserver'],
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.dummy.DummyCache'}},
)
class DataAvailabilityTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='tav', password='x')
        self.factory = APIRequestFactory()
        self.inst = Institution.objects.create(scada_id='I5', name='Cesmag')
        self.cat = DeviceCategory.objects.create(scada_id='C5', name='electricmeter')
        self.dev = Device.objects.create(name='M', scada_id='AVM', category=self.cat, institution=self.inst)
        ElectricMeterIndicators.objects.create(
            device=self.dev, institution=self.inst, date=date(2024, 1, 15), time_range='daily')
        ElectricMeterIndicators.objects.create(
            device=self.dev, institution=self.inst, date=date(2026, 7, 18), time_range='daily')
        HourlyMeterIndicators.objects.create(
            device=self.dev, institution=self.inst,
            hour=datetime(2026, 6, 18, 0, 0, tzinfo=COLOMBIA_TZ))

    def _get(self, params):
        req = self.factory.get('/api/data-availability/', params)
        force_authenticate(req, user=self.user)
        return DataAvailabilityView.as_view()(req)

    def test_reports_min_max(self):
        resp = self._get({'institution_id': self.inst.id, 'category': 'electricMeter'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['daily_monthly']['min_date'], date(2024, 1, 15))
        self.assertEqual(resp.data['daily_monthly']['max_date'], date(2026, 7, 18))
        self.assertEqual(resp.data['hourly']['min_date'].date(), date(2026, 6, 18))

    def test_missing_params_400(self):
        resp = self._get({'institution_id': self.inst.id})
        self.assertEqual(resp.status_code, 400)

    def test_invalid_category_400(self):
        resp = self._get({'institution_id': self.inst.id, 'category': 'foo'})
        self.assertEqual(resp.status_code, 400)

    def test_no_data_returns_null(self):
        other = Institution.objects.create(scada_id='I6', name='Otra')
        resp = self._get({'institution_id': other.id, 'category': 'electricMeter'})
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data['daily_monthly']['min_date'])
