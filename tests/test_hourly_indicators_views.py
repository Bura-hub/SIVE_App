"""
Tests ETAPA 3 (vista horaria, Opción B): contrato `time_range=hourly` en los 3
endpoints EXISTENTES de indicadores (ElectricMeterIndicatorsViewSet, InverterIndicatorsView,
WeatherStationIndicatorsView). NO se crean rutas nuevas: se reutilizan las mismas vistas,
ramificando por el query param `time_range`.

Modelos horarios (HourlyMeterIndicators/HourlyInverterIndicators/HourlyWeatherIndicators)
y `resolve_indicators_hourly_range` (tope 7 días/168h) ya existen desde la ETAPA 1
(indicators/models.py, indicators/services/date_ranges.py).

Contrato verificado:
- device_id es OBLIGATORIO cuando time_range='hourly' -> 400 si falta.
- El rango se resuelve con resolve_indicators_hourly_range: día único vía 'date', o
  'start_date'/'end_date' con tope de 7 días/168h -> 400 si se excede (NO se recorta).
- La fila serializada expone 'hour' en ISO-8601 y los campos propios de cada tabla horaria.
- daily/monthly de las 3 vistas siguen respondiendo 200 igual que antes (regresión).

Las vistas se invocan DIRECTAMENTE con APIRequestFactory (mismo patrón que
test_api_validation.py) para evitar el prefijo FORCE_SCRIPT_NAME (=/sive en prod) que
reverse() incrusta y que el cliente de test no resuelve.
"""
import json
from datetime import date, datetime

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from indicators.models import (
    ElectricMeterIndicators, InverterIndicators, WeatherStationIndicators,
    HourlyMeterIndicators, HourlyInverterIndicators, HourlyWeatherIndicators,
)
from indicators.services.date_ranges import COLOMBIA_TZ
from indicators.views import (
    ElectricMeterIndicatorsViewSet,
    InverterIndicatorsView,
    WeatherStationIndicatorsView,
)
from scada_proxy.models import Device, Institution, DeviceCategory


def _hour(d, h):
    """Datetime aware (Bogotá) para el inicio de la hora `h` del día `d`."""
    return COLOMBIA_TZ.localize(datetime(d.year, d.month, d.day, h, 0, 0))


# Las 3 vistas están decoradas con @cache_page (5 min) sobre Redis REAL (no una caché
# de test aislada). Con la caché real, una respuesta cacheada de una URL+querystring ya
# vista (en este u otro proceso) podría servirse en vez de ejecutar la vista de nuevo,
# dando falsos positivos/negativos. Se fuerza DummyCache para que @cache_page sea inerte
# (mismo patrón que test_admin_only_endpoints.py).
@override_settings(
    ALLOWED_HOSTS=['testserver'],
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.dummy.DummyCache'}},
)
class HourlyIndicatorsViewsTestCase(TestCase):
    """Fixtures compartidos: 1 institución + 1 medidor + 1 inversor + 1 estación,
    cada uno con 2 filas horarias de prueba en self.test_date."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(username='thourly', password='x')
        self.factory = APIRequestFactory()

        self.institution = Institution.objects.create(scada_id='INST_HOURLY', name='Institución Horaria')

        self.meter_cat = DeviceCategory.objects.create(
            scada_id='CAT_METER_H', name='electricmeter_h', description='Medidor')
        self.inverter_cat = DeviceCategory.objects.create(
            scada_id='CAT_INV_H', name='inverter_h', description='Inversor')
        self.weather_cat = DeviceCategory.objects.create(
            scada_id='CAT_WEATHER_H', name='weatherstation_h', description='Estación')

        self.meter = Device.objects.create(
            name='Medidor Horario', scada_id='METER_H_001', category=self.meter_cat, institution=self.institution)
        self.inverter = Device.objects.create(
            name='Inversor Horario', scada_id='INV_H_001', category=self.inverter_cat, institution=self.institution)
        self.weather = Device.objects.create(
            name='Estación Horaria', scada_id='WEATHER_H_001', category=self.weather_cat, institution=self.institution)

        self.test_date = date(2026, 7, 5)

        HourlyMeterIndicators.objects.create(
            device=self.meter, institution=self.institution, hour=_hour(self.test_date, 10),
            imported_energy_kwh=1.5, exported_energy_kwh=0.2, net_energy_consumption_kwh=1.3,
            peak_demand_kw=5.0, avg_demand_kw=3.0, load_factor_pct=60.0, avg_power_factor=0.95,
            measurement_count=12,
        )
        HourlyMeterIndicators.objects.create(
            device=self.meter, institution=self.institution, hour=_hour(self.test_date, 11),
            imported_energy_kwh=1.8, exported_energy_kwh=0.1, net_energy_consumption_kwh=1.7,
            peak_demand_kw=5.5, avg_demand_kw=3.2, load_factor_pct=58.0, avg_power_factor=0.96,
            measurement_count=12,
        )

        HourlyInverterIndicators.objects.create(
            device=self.inverter, institution=self.institution, hour=_hour(self.test_date, 10),
            energy_ac_kwh=2.0, energy_dc_kwh=2.2, dc_ac_efficiency_pct=90.9,
            avg_power_w=2000.0, max_power_w=2500.0, min_power_w=1500.0,
            measurement_count=12,
        )

        HourlyWeatherIndicators.objects.create(
            device=self.weather, institution=self.institution, hour=_hour(self.test_date, 10),
            avg_irradiance_wm2=450.0, irradiance_energy_kwh_m2=0.45,
            avg_temperature_c=22.5, max_temperature_c=24.0, min_temperature_c=21.0,
            avg_humidity_pct=70.0, avg_wind_speed_kmh=5.0, avg_wind_direction_deg=180.0,
            precipitation_cm=0.0, measurement_count=12,
        )

    # ------------------------------------------------------------------
    # Helpers de invocación directa (sin pasar por urls.py/reverse()).
    # ------------------------------------------------------------------
    def _get_meter(self, params):
        req = self.factory.get('/api/electric-meter-indicators/', params)
        force_authenticate(req, user=self.user)
        view = ElectricMeterIndicatorsViewSet.as_view({'get': 'list'})
        return view(req)

    def _get_inverter(self, params):
        req = self.factory.get('/api/inverter-indicators/', params)
        force_authenticate(req, user=self.user)
        return InverterIndicatorsView.as_view()(req)

    def _get_weather(self, params):
        req = self.factory.get('/api/weather-station-indicators/', params)
        force_authenticate(req, user=self.user)
        return WeatherStationIndicatorsView.as_view()(req)

    @staticmethod
    def _json(resp):
        resp.render() if hasattr(resp, 'render') else None
        return json.loads(resp.content)

    # ------------------------------------------------------------------
    # (a) device_id ausente -> 400 en las 3 vistas.
    # ------------------------------------------------------------------
    def test_meter_hourly_sin_device_id_da_400(self):
        resp = self._get_meter({'time_range': 'hourly', 'date': '2026-07-05'})
        self.assertEqual(resp.status_code, 400)

    def test_inverter_hourly_sin_device_id_da_400(self):
        resp = self._get_inverter({
            'time_range': 'hourly', 'institution_id': str(self.institution.id), 'date': '2026-07-05'})
        self.assertEqual(resp.status_code, 400)

    def test_weather_hourly_sin_device_id_da_400(self):
        resp = self._get_weather({'time_range': 'hourly', 'date': '2026-07-05'})
        self.assertEqual(resp.status_code, 400)

    # ------------------------------------------------------------------
    # (b) rango > 7 días -> 400 (resolve_indicators_hourly_range NO recorta: rechaza).
    # ------------------------------------------------------------------
    def test_meter_hourly_rango_excesivo_da_400(self):
        resp = self._get_meter({
            'time_range': 'hourly', 'device_id': str(self.meter.id),
            'start_date': '2026-07-01', 'end_date': '2026-07-10',  # 10 días > tope de 7
        })
        self.assertEqual(resp.status_code, 400)

    def test_inverter_hourly_rango_excesivo_da_400(self):
        resp = self._get_inverter({
            'time_range': 'hourly', 'institution_id': str(self.institution.id),
            'device_id': str(self.inverter.id),
            'start_date': '2026-07-01', 'end_date': '2026-07-10',
        })
        self.assertEqual(resp.status_code, 400)

    def test_weather_hourly_rango_excesivo_da_400(self):
        resp = self._get_weather({
            'time_range': 'hourly', 'device_id': str(self.weather.id),
            'start_date': '2026-07-01', 'end_date': '2026-07-10',
        })
        self.assertEqual(resp.status_code, 400)

    # ------------------------------------------------------------------
    # (c) respuesta 200 con 'hour' ISO y campos correctos.
    # ------------------------------------------------------------------
    def test_meter_hourly_devuelve_hour_iso_y_campos(self):
        resp = self._get_meter({
            'time_range': 'hourly', 'device_id': str(self.meter.id), 'date': '2026-07-05'})
        self.assertEqual(resp.status_code, 200)
        data = self._json(resp)
        self.assertIn('results', data)
        self.assertIn('summary', data)
        self.assertEqual(len(data['results']), 2)
        row = data['results'][0]
        self.assertIn('hour', row)
        self.assertIn('T', row['hour'])  # ISO-8601
        self.assertNotIn('date', row)
        self.assertNotIn('time_range_display', row)
        for field in ('imported_energy_kwh', 'exported_energy_kwh', 'net_energy_consumption_kwh',
                      'peak_demand_kw', 'avg_demand_kw', 'load_factor_pct', 'avg_power_factor',
                      'measurement_count', 'device_name', 'institution_name'):
            self.assertIn(field, row)

    def test_inverter_hourly_devuelve_hour_iso_y_campos(self):
        resp = self._get_inverter({
            'time_range': 'hourly', 'institution_id': str(self.institution.id),
            'device_id': str(self.inverter.id), 'date': '2026-07-05',
        })
        self.assertEqual(resp.status_code, 200)
        data = self._json(resp)
        self.assertEqual(len(data['results']), 1)
        row = data['results'][0]
        self.assertIn('hour', row)
        self.assertIn('T', row['hour'])
        # Excluidos por diseño (siempre 0 en el inversor, ver HourlyInverterIndicators).
        self.assertNotIn('avg_irradiance_wm2', row)
        self.assertNotIn('avg_temperature_c', row)
        for field in ('energy_ac_kwh', 'energy_dc_kwh', 'dc_ac_efficiency_pct',
                      'avg_power_w', 'max_power_w', 'min_power_w'):
            self.assertIn(field, row)

    def test_weather_hourly_devuelve_hour_iso_y_campos(self):
        resp = self._get_weather({
            'time_range': 'hourly', 'device_id': str(self.weather.id), 'date': '2026-07-05'})
        self.assertEqual(resp.status_code, 200)
        data = self._json(resp)
        self.assertEqual(len(data['results']), 1)
        row = data['results'][0]
        self.assertIn('hour', row)
        self.assertIn('T', row['hour'])
        # Excluidos por diseño (poco significativos a grano horario, ver HourlyWeatherIndicators).
        self.assertNotIn('wind_direction_distribution', row)
        self.assertNotIn('wind_speed_distribution', row)
        for field in ('avg_irradiance_wm2', 'irradiance_energy_kwh_m2', 'avg_temperature_c',
                      'max_temperature_c', 'min_temperature_c', 'avg_humidity_pct',
                      'avg_wind_speed_kmh', 'avg_wind_direction_deg', 'precipitation_cm'):
            self.assertIn(field, row)

    def test_meter_hourly_dia_unico_filtra_solo_esa_hora_no_otros_dias(self):
        # Fila de control en OTRO día: no debe aparecer al pedir self.test_date.
        HourlyMeterIndicators.objects.create(
            device=self.meter, institution=self.institution, hour=_hour(date(2026, 7, 6), 10),
            imported_energy_kwh=99.0, measurement_count=12,
        )
        resp = self._get_meter({
            'time_range': 'hourly', 'device_id': str(self.meter.id), 'date': '2026-07-05'})
        data = self._json(resp)
        self.assertEqual(len(data['results']), 2)

    # ------------------------------------------------------------------
    # (d) daily/monthly de las 3 vistas siguen respondiendo igual (cero regresión).
    # ------------------------------------------------------------------
    def test_meter_daily_sigue_funcionando(self):
        ElectricMeterIndicators.objects.create(
            device=self.meter, institution=self.institution, date=self.test_date, time_range='daily',
            imported_energy_kwh=10.0, exported_energy_kwh=1.0, net_energy_consumption_kwh=9.0,
            peak_demand_kw=5.0, avg_demand_kw=3.0, load_factor_pct=60.0, avg_power_factor=0.95,
        )
        resp = self._get_meter({'institution_id': str(self.institution.id)})
        self.assertEqual(resp.status_code, 200)
        data = self._json(resp)
        self.assertEqual(len(data['results']), 1)
        self.assertIn('date', data['results'][0])
        self.assertIn('time_range_display', data['results'][0])

    def test_meter_monthly_sigue_funcionando(self):
        ElectricMeterIndicators.objects.create(
            device=self.meter, institution=self.institution, date=self.test_date, time_range='monthly',
            imported_energy_kwh=300.0, exported_energy_kwh=10.0, net_energy_consumption_kwh=290.0,
            peak_demand_kw=6.0, avg_demand_kw=3.5, load_factor_pct=55.0, avg_power_factor=0.94,
        )
        resp = self._get_meter({'institution_id': str(self.institution.id), 'time_range': 'monthly'})
        self.assertEqual(resp.status_code, 200)
        data = self._json(resp)
        self.assertEqual(len(data['results']), 1)

    def test_inverter_daily_sigue_funcionando(self):
        InverterIndicators.objects.create(
            device=self.inverter, institution=self.institution, date=self.test_date, time_range='daily',
            dc_ac_efficiency_pct=90.0, energy_ac_daily_kwh=20.0, energy_dc_daily_kwh=22.0,
        )
        resp = self._get_inverter({'institution_id': str(self.institution.id)})
        self.assertEqual(resp.status_code, 200)
        data = self._json(resp)
        self.assertEqual(len(data['results']), 1)
        self.assertIn('date', data['results'][0])

    def test_weather_daily_sigue_funcionando(self):
        WeatherStationIndicators.objects.create(
            device=self.weather, institution=self.institution, date=self.test_date, time_range='daily',
            daily_irradiance_kwh_m2=5.0, avg_temperature_c=22.0,
        )
        resp = self._get_weather({})
        self.assertEqual(resp.status_code, 200)
        data = self._json(resp)
        self.assertEqual(len(data['results']), 1)
        self.assertIn('date', data['results'][0])

    def test_weather_monthly_sigue_funcionando(self):
        WeatherStationIndicators.objects.create(
            device=self.weather, institution=self.institution, date=self.test_date, time_range='monthly',
            daily_irradiance_kwh_m2=150.0, avg_temperature_c=22.0,
        )
        resp = self._get_weather({'time_range': 'monthly'})
        self.assertEqual(resp.status_code, 200)
        data = self._json(resp)
        self.assertEqual(len(data['results']), 1)

    def test_weather_time_range_invalido_sigue_dando_400(self):
        # Regresión explícita: 'hourly' ahora es válido, pero cualquier OTRO valor sigue
        # rechazado (antes solo aceptaba 'daily'/'monthly').
        resp = self._get_weather({'time_range': 'bogus'})
        self.assertEqual(resp.status_code, 400)
