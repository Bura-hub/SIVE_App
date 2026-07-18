from datetime import date
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate
from scada_proxy.models import Institution, DeviceCategory, Device
from indicators.models import WeatherStationIndicators
from indicators.views import WeatherStationIndicatorsView


@override_settings(
    ALLOWED_HOSTS=['testserver'],
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.dummy.DummyCache'}},
)
class WeatherAggregationViewTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='twea', password='x')
        self.factory = APIRequestFactory()
        self.inst = Institution.objects.create(scada_id='I4', name='Cesmag')
        self.cat = DeviceCategory.objects.create(scada_id='C4', name='weatherStation')
        self.d1 = Device.objects.create(name='WS1', scada_id='WS1', category=self.cat, institution=self.inst)
        self.d2 = Device.objects.create(name='WS2', scada_id='WS2', category=self.cat, institution=self.inst)
        for dev, temp in ((self.d1, 20.0), (self.d2, 24.0)):
            WeatherStationIndicators.objects.create(
                device=dev, institution=self.inst, date=date(2026, 7, 1),
                time_range='monthly', daily_irradiance_kwh_m2=5.0, avg_temperature_c=temp)

    def _get(self, params):
        req = self.factory.get('/api/weather-station-indicators/', params)
        force_authenticate(req, user=self.user)
        return WeatherStationIndicatorsView.as_view()(req)

    def test_all_stations_monthly_aggregated(self):
        resp = self._get({
            'time_range': 'monthly', 'institution_id': self.inst.id,
            'start_date': '2026-07-01', 'end_date': '2026-07-31'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['results']), 1)
        self.assertEqual(resp.data['results'][0]['daily_irradiance_kwh_m2'], 10.0)  # suma
        self.assertAlmostEqual(resp.data['results'][0]['avg_temperature_c'], 22.0)  # promedio
