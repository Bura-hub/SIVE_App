from datetime import date
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate
from scada_proxy.models import Institution, DeviceCategory, Device
from indicators.models import ElectricMeterIndicators
from indicators.views import ElectricMeterIndicatorsViewSet
from indicators.services.queries import aggregate_indicators_by_period


class AggregateHelperTest(TestCase):
    def setUp(self):
        self.inst = Institution.objects.create(scada_id='I1', name='Cesmag')
        self.cat = DeviceCategory.objects.create(scada_id='C1', name='electricmeter')
        self.d1 = Device.objects.create(name='M1', scada_id='M1', category=self.cat, institution=self.inst)
        self.d2 = Device.objects.create(name='M2', scada_id='M2', category=self.cat, institution=self.inst)
        for dev, val in ((self.d1, 10.0), (self.d2, 5.0)):
            ElectricMeterIndicators.objects.create(
                device=dev, institution=self.inst, date=date(2026, 6, 1),
                time_range='monthly', net_energy_consumption_kwh=val, avg_power_factor=0.9)

    def test_sum_and_avg_by_period(self):
        qs = ElectricMeterIndicators.objects.filter(institution=self.inst, time_range='monthly')
        rows = aggregate_indicators_by_period(
            qs, sum_fields=['net_energy_consumption_kwh'], avg_fields=['avg_power_factor'])
        self.assertEqual(len(rows), 1)  # un solo punto para junio
        self.assertEqual(rows[0]['net_energy_consumption_kwh'], 15.0)
        self.assertAlmostEqual(rows[0]['avg_power_factor'], 0.9)
        self.assertEqual(rows[0]['device_name'], 'Todos')


@override_settings(
    ALLOWED_HOSTS=['testserver'],
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.dummy.DummyCache'}},
)
class ElectricAggregationViewTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='tagg', password='x')
        self.factory = APIRequestFactory()
        self.inst = Institution.objects.create(scada_id='I2', name='Cesmag')
        self.cat = DeviceCategory.objects.create(scada_id='C2', name='electricmeter')
        self.d1 = Device.objects.create(name='M1', scada_id='MM1', category=self.cat, institution=self.inst)
        self.d2 = Device.objects.create(name='M2', scada_id='MM2', category=self.cat, institution=self.inst)
        self.d3 = Device.objects.create(name='M3', scada_id='MM3', category=self.cat, institution=self.inst)
        for dev in (self.d1, self.d2, self.d3):
            for d in (date(2026, 6, 1), date(2026, 7, 1)):
                ElectricMeterIndicators.objects.create(
                    device=dev, institution=self.inst, date=d,
                    time_range='monthly', net_energy_consumption_kwh=1.0)

    def _get(self, params):
        req = self.factory.get('/api/electric-meter-indicators/', params)
        force_authenticate(req, user=self.user)
        return ElectricMeterIndicatorsViewSet.as_view({'get': 'list'})(req)

    def test_all_devices_monthly_returns_one_point_per_month(self):
        resp = self._get({
            'time_range': 'monthly', 'institution_id': self.inst.id,
            'start_date': '2026-06-01', 'end_date': '2026-07-31'})
        self.assertEqual(resp.status_code, 200)
        # antes: 6 puntos (3 dispositivos x 2 meses). Ahora: 2 (uno por mes).
        self.assertEqual(len(resp.data['results']), 2)
        by_date = {r['date']: r for r in resp.data['results']}
        self.assertEqual(by_date[date(2026, 6, 1)]['net_energy_consumption_kwh'], 3.0)

    def test_single_device_unchanged(self):
        resp = self._get({
            'time_range': 'monthly', 'institution_id': self.inst.id,
            'device_id': self.d1.id,
            'start_date': '2026-06-01', 'end_date': '2026-07-31'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['results']), 2)  # 2 meses del dispositivo
        self.assertEqual(resp.data['results'][0]['device_name'], 'M1')
