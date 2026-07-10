"""
Test del saneamiento de rangos meteorológicos (arreglo de la Ola 1).

El cálculo de estaciones descarta lecturas fuera de rango físico plausible antes de
promediar (temperatura -20..60 °C, humedad 0..100 %, viento 0..150 km/h, etc.). Este
test verifica end-to-end que un pico imposible NO contamina los promedios/máximos.
"""
from datetime import datetime, time, timedelta

from django.test import TestCase
from django.utils import timezone

from indicators.models import WeatherStationIndicators
from indicators.tasks import calculate_weather_station_indicators
from scada_proxy.models import Device, Institution, DeviceCategory


class WeatherRangeSanitizationTests(TestCase):
    def setUp(self):
        self.category = DeviceCategory.objects.create(
            scada_id='CAT_WS', name='weatherStation', description='Estación')
        self.institution = Institution.objects.create(scada_id='INST_WS', name='Inst WS')
        self.device = Device.objects.create(
            name='Test WS', scada_id='TEST_WS_001',
            category=self.category, institution=self.institution)
        self.test_date = timezone.now().date()

    def test_pico_imposible_de_temperatura_se_descarta(self):
        from scada_proxy.tasks import upsert_measurements_page
        base = timezone.make_aware(datetime.combine(self.test_date, time(12, 0)))
        # Dos lecturas válidas de 25 °C y un pico imposible de 999 °C (fuera de -20..60).
        upsert_measurements_page(self.device, [
            (base, {'temperature': 25.0, 'humidity': 60.0, 'windSpeed': 10.0}),
            (base + timedelta(minutes=2), {'temperature': 999.0, 'humidity': 60.0, 'windSpeed': 10.0}),
            (base + timedelta(minutes=4), {'temperature': 25.0, 'humidity': 60.0, 'windSpeed': 10.0}),
        ])
        d = self.test_date.strftime('%Y-%m-%d')
        calculate_weather_station_indicators(
            time_range='daily', start_date_str=d, end_date_str=d, device_id=self.device.scada_id)
        ind = WeatherStationIndicators.objects.get(
            device=self.device, date=self.test_date, time_range='daily')
        # El pico de 999 °C se descarta: el máximo no lo refleja y el promedio es ~25.
        self.assertLessEqual(ind.max_temperature_c, 60.0)
        self.assertAlmostEqual(ind.avg_temperature_c, 25.0, places=1)
