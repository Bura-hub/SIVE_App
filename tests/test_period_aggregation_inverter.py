from datetime import date
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate
from scada_proxy.models import Institution, DeviceCategory, Device
from indicators.models import InverterIndicators
from indicators.views import InverterIndicatorsView


@override_settings(
    ALLOWED_HOSTS=['testserver'],
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.dummy.DummyCache'}},
)
class InverterAggregationViewTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='tinv', password='x')
        self.factory = APIRequestFactory()
        self.inst = Institution.objects.create(scada_id='I3', name='Cesmag')
        self.cat = DeviceCategory.objects.create(scada_id='C3', name='inverter')
        self.d1 = Device.objects.create(name='INV1', scada_id='INV1', category=self.cat, institution=self.inst)
        self.d2 = Device.objects.create(name='INV2', scada_id='INV2', category=self.cat, institution=self.inst)
        for dev in (self.d1, self.d2):
            InverterIndicators.objects.create(
                device=dev, institution=self.inst, date=date(2026, 7, 1),
                time_range='monthly', total_generated_energy_kwh=100.0,
                performance_ratio_pct=80.0)

    def _get(self, params):
        req = self.factory.get('/api/inverter-indicators/', params)
        force_authenticate(req, user=self.user)
        return InverterIndicatorsView.as_view()(req)

    def test_all_inverters_monthly_aggregated(self):
        resp = self._get({
            'time_range': 'monthly', 'institution_id': self.inst.id,
            'start_date': '2026-07-01', 'end_date': '2026-07-31'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['results']), 1)
        self.assertEqual(resp.data['results'][0]['total_generated_energy_kwh'], 200.0)
        self.assertAlmostEqual(resp.data['results'][0]['performance_ratio_pct'], 80.0)
