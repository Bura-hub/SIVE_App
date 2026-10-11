"""
Estaciones meteorológicas, corrección de octubre de 2026 (C6, C7, C8 y media circular).
"""
from datetime import date, datetime, timedelta

import pytz
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from indicators.models import WeatherStationIndicators
from indicators.services.date_ranges import COLOMBIA_TZ
from indicators.services.weather_calc import (
    calculate_single_day_weather_chart_data,
    calculate_single_hour_weather_indicators,
    calculate_single_month_weather_indicators,
    circular_mean_deg,
)
from indicators.views import WeatherStationIndicatorsView
from scada_proxy.models import Device, DeviceCategory, Institution


def _row(ts, **kw):
    row = {'date': ts.astimezone(pytz.utc), 'irradiance': None, 'temperature': None,
           'humidity': None, 'windSpeed': None, 'windDirection': None, 'precipitation': None}
    row.update(kw)
    return row


def _bog(y, m, d, h, mi=0):
    return COLOMBIA_TZ.localize(datetime(y, m, d, h, mi))


class GraficaDelDiaTests(SimpleTestCase):
    def setUp(self):
        start = _bog(2025, 7, 1, 6)
        # 12 h × 30 muestras a 500 W/m²; 20 °C. Una lectura nocturna de 900 (sensor pegado).
        self.rows = [_row(start + timedelta(minutes=2 * i), irradiance=500.0, temperature=20.0)
                     for i in range(360)]
        self.rows.append(_row(_bog(2025, 7, 1, 21), irradiance=900.0, temperature=10.0))

    def test_irradiacion_del_dia_es_la_suma_de_muestras(self):
        chart = calculate_single_day_weather_chart_data(self.rows)
        # 360 × 500 × 2/60 / 1000 = 6 kWh/m². Antes: Σ 24 medias horarias × 2/60 / 1000 = 0,23.
        self.assertAlmostEqual(chart['daily_irradiance_kwh_m2'], 6.0)

    def test_horas_de_bogota_y_horas_vacias_en_none(self):
        chart = calculate_single_day_weather_chart_data(self.rows)
        self.assertAlmostEqual(chart['hourly_irradiance'][6], 500.0)
        self.assertEqual(chart['hourly_irradiance'][21], 0.0)   # noche: 0 por definición
        self.assertIsNone(chart['hourly_irradiance'][3])         # sin datos
        self.assertIsNone(chart['hourly_temperature'][3])

    def test_promedio_del_dia_sale_de_las_muestras(self):
        chart = calculate_single_day_weather_chart_data(self.rows)
        # Antes: Σ 13 medias / 24 horas (las vacías en 0) ≈ 10,4 °C.
        self.assertAlmostEqual(chart['avg_daily_temperature_c'], (360 * 20 + 10) / 361)


class MediaCircularTests(SimpleTestCase):
    def test_norte(self):
        self.assertAlmostEqual(circular_mean_deg([350.0, 10.0]) % 360, 0.0, places=6)

    def test_hora_con_viento_del_norte(self):
        t = _bog(2025, 7, 1, 12)
        ind = calculate_single_hour_weather_indicators([
            _row(t, windDirection=350.0), _row(t + timedelta(minutes=2), windDirection=10.0)])
        # Antes: media aritmética = 180° (sur).
        self.assertAlmostEqual(ind['avg_wind_direction_deg'] % 360, 0.0, places=6)

    def test_hora_sin_mediciones_de_viento(self):
        ind = calculate_single_hour_weather_indicators([_row(_bog(2025, 7, 1, 12), temperature=18.0)])
        self.assertIsNone(ind['avg_wind_direction_deg'])
        self.assertIsNone(ind['avg_wind_speed_kmh'])
        self.assertIsNone(ind['avg_irradiance_wm2'])


class MensualEnDiasDeBogotaTests(SimpleTestCase):
    def test_dias_de_bogota(self):
        # Dos días con 4 kWh/m² cada uno: 240 muestras a 500 W/m² de 08:00 a 16:00 Bogotá.
        rows = []
        for d in (1, 2):
            start = _bog(2025, 7, d, 8)
            rows += [_row(start + timedelta(minutes=2 * i), irradiance=500.0) for i in range(240)]
        month = calculate_single_month_weather_indicators(rows)
        self.assertAlmostEqual(month['daily_irradiance_kwh_m2'], 4.0)

    def test_tarde_de_bogota_no_pasa_al_dia_siguiente(self):
        rows = [_row(_bog(2025, 7, 1, 20) + timedelta(minutes=2 * i), temperature=12.0)
                for i in range(30)]   # 20:00 Bogotá = 01:00 UTC del día 2
        rows += [_row(_bog(2025, 7, 1, 10) + timedelta(minutes=2 * i), temperature=22.0)
                 for i in range(30)]
        rows.sort(key=lambda r: r['date'])
        month = calculate_single_month_weather_indicators(rows)
        # Un solo día de Bogotá: media de 60 muestras = 17 °C (con días UTC salían dos días, 22 y 12).
        self.assertAlmostEqual(month['avg_temperature_c'], 17.0)
        self.assertEqual(month['max_temperature_c'], 22.0)


@override_settings(
    ALLOWED_HOSTS=['testserver'],
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.dummy.DummyCache'}},
)
class TodosPromediaTests(TestCase):
    """C8: el agregado «Todos» promedia irradiación, HSP y precipitación entre estaciones."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(username='twx', password='x')
        self.inst = Institution.objects.create(scada_id='I8', name='Inst')
        cat = DeviceCategory.objects.create(scada_id='C8', name='weatherStation')
        for i, (h, p) in enumerate(((4.0, 1.0), (6.0, 3.0))):
            dev = Device.objects.create(name=f'E{i}', scada_id=f'E{i}', category=cat, institution=self.inst)
            WeatherStationIndicators.objects.create(
                device=dev, institution=self.inst, date=date(2025, 7, 1), time_range='daily',
                daily_irradiance_kwh_m2=h, daily_hsp_hours=h, daily_precipitation_cm=p)

    def test_promedio(self):
        req = APIRequestFactory().get('/api/weather-station-indicators/', {
            'time_range': 'daily', 'institution_id': self.inst.id,
            'start_date': '2025-07-01', 'end_date': '2025-07-01'})
        force_authenticate(req, user=self.user)
        r = WeatherStationIndicatorsView.as_view()(req).data['results'][0]
        # Antes: 10 kWh/m², 10 HSP y 4 cm (suma).
        self.assertAlmostEqual(r['daily_irradiance_kwh_m2'], 5.0)
        self.assertAlmostEqual(r['daily_hsp_hours'], 5.0)
        self.assertAlmostEqual(r['daily_precipitation_cm'], 2.0)
