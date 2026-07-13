"""
Tests del rollup horario (vista horaria, Opción B — Etapa 2).

Cubren:
- Idempotencia de `calculate_hourly_rollup`: correr dos veces sobre la misma hora no
  duplica filas (update_or_create por (device, hour)).
- Mapeo correcto de campos hacia HourlyMeterIndicators/HourlyInverterIndicators
  (incluye el renombrado energy_ac_daily_kwh/energy_dc_daily_kwh -> energy_ac_kwh/
  energy_dc_kwh y el avg_power_w agregado aparte).
- Regresión del bug de `calculate_single_day_weather_chart_data`: antes de la Etapa 2
  la función se invocaba sin estar importada en tasks.py, así que el NameError quedaba
  silenciado por el `except Exception` amplio y WeatherStationChartData nunca se creaba.
"""
from datetime import datetime, time, timedelta

from django.test import TestCase

from indicators.energy import SAMPLE_INTERVAL_HOURS
from indicators.models import (
    HourlyMeterIndicators,
    HourlyInverterIndicators,
    HourlyWeatherIndicators,
    WeatherStationChartData,
)
from indicators.tasks import (
    COLOMBIA_TZ,
    calculate_hourly_rollup,
    calculate_weather_station_indicators,
)
from scada_proxy.models import (
    Device, Institution, DeviceCategory,
    MeterMeasurement, InverterMeasurement, WeatherStationMeasurement,
)


class HourlyRollupMeterTests(TestCase):
    """Idempotencia + mapeo de campos para HourlyMeterIndicators."""

    def setUp(self):
        self.category = DeviceCategory.objects.create(scada_id='CAT_EM', name='electricMeter')
        self.institution = Institution.objects.create(scada_id='INST_EM', name='Test Institution')
        self.meter = Device.objects.create(
            scada_id='EM1', name='Test Meter',
            category=self.category, institution=self.institution, is_active=True,
        )
        # Hora cerrada fija y determinista (muy anterior a "ahora"): sin depender de
        # timezone.now(), evita flakiness por la hora real de ejecución del CI.
        self.hour_start = COLOMBIA_TZ.localize(datetime(2026, 6, 15, 10, 0))

        MeterMeasurement.objects.create(
            device=self.meter, date=self.hour_start + timedelta(minutes=1),
            totalActivePower=100.0, totalPowerFactor=0.90,
        )
        MeterMeasurement.objects.create(
            device=self.meter, date=self.hour_start + timedelta(minutes=10),
            totalActivePower=200.0, totalPowerFactor=0.95,
        )

    def _run(self):
        return calculate_hourly_rollup(
            start_hour_str=self.hour_start.isoformat(),
            end_hour_str=self.hour_start.isoformat(),
        )

    def test_mapea_demanda_y_measurement_count_correctamente(self):
        self._run()
        row = HourlyMeterIndicators.objects.get(device=self.meter, hour=self.hour_start)

        # Solo 2 mediciones (< window_size=7 de la demanda pico), así que
        # peak_demand_kw cae al máximo directo y avg_demand_kw al promedio simple
        # (ver compute_meter_indicators en indicators/services/meter_calc.py).
        self.assertAlmostEqual(row.avg_demand_kw, 150.0)
        self.assertAlmostEqual(row.peak_demand_kw, 200.0)
        self.assertEqual(row.measurement_count, 2)
        self.assertEqual(row.institution_id, self.institution.id)

    def test_idempotente_no_duplica_filas(self):
        self._run()
        first = HourlyMeterIndicators.objects.get(device=self.meter, hour=self.hour_start)

        self._run()
        rows = HourlyMeterIndicators.objects.filter(device=self.meter, hour=self.hour_start)

        self.assertEqual(rows.count(), 1)
        self.assertEqual(rows.first().pk, first.pk)
        self.assertAlmostEqual(rows.first().avg_demand_kw, 150.0)

    def test_hora_sin_mediciones_no_crea_fila(self):
        otra_hora = self.hour_start + timedelta(hours=1)
        calculate_hourly_rollup(
            start_hour_str=otra_hora.isoformat(),
            end_hour_str=otra_hora.isoformat(),
        )
        self.assertFalse(
            HourlyMeterIndicators.objects.filter(device=self.meter, hour=otra_hora).exists()
        )


class HourlyRollupInverterTests(TestCase):
    """Mapeo de campos para HourlyInverterIndicators (renombrado *_daily_* -> horario)."""

    def setUp(self):
        self.category = DeviceCategory.objects.create(scada_id='CAT_INV', name='inverter')
        self.institution = Institution.objects.create(scada_id='INST_INV', name='Test Institution')
        self.inverter = Device.objects.create(
            scada_id='INV1', name='Test Inverter',
            category=self.category, institution=self.institution, is_active=True,
        )
        self.hour_start = COLOMBIA_TZ.localize(datetime(2026, 6, 15, 11, 0))

        InverterMeasurement.objects.create(
            device=self.inverter, date=self.hour_start + timedelta(minutes=1),
            acPower=1000.0, dcPower=1200.0,
        )
        InverterMeasurement.objects.create(
            device=self.inverter, date=self.hour_start + timedelta(minutes=10),
            acPower=1000.0, dcPower=1200.0,
        )

    def test_mapea_energia_y_potencia_promedio(self):
        calculate_hourly_rollup(
            start_hour_str=self.hour_start.isoformat(),
            end_hour_str=self.hour_start.isoformat(),
        )
        row = HourlyInverterIndicators.objects.get(device=self.inverter, hour=self.hour_start)

        expected_energy_ac_kwh = (1000.0 + 1000.0) * SAMPLE_INTERVAL_HOURS / 1000
        self.assertAlmostEqual(row.energy_ac_kwh, expected_energy_ac_kwh)
        self.assertAlmostEqual(row.avg_power_w, 1000.0)
        self.assertEqual(row.measurement_count, 2)
        # Campos siempre-0 del inversor, excluidos por diseño (ver HourlyInverterIndicators
        # en indicators/models.py): no deben existir como columnas del modelo.
        self.assertFalse(hasattr(row, 'avg_irradiance_wm2'))
        self.assertFalse(hasattr(row, 'avg_temperature_c'))

    def test_idempotente_no_duplica_filas(self):
        calculate_hourly_rollup(
            start_hour_str=self.hour_start.isoformat(),
            end_hour_str=self.hour_start.isoformat(),
        )
        first = HourlyInverterIndicators.objects.get(device=self.inverter, hour=self.hour_start)

        calculate_hourly_rollup(
            start_hour_str=self.hour_start.isoformat(),
            end_hour_str=self.hour_start.isoformat(),
        )
        rows = HourlyInverterIndicators.objects.filter(device=self.inverter, hour=self.hour_start)

        self.assertEqual(rows.count(), 1)
        self.assertEqual(rows.first().pk, first.pk)


class HourlyRollupWeatherTests(TestCase):
    """Mapeo de campos para HourlyWeatherIndicators (fuente:
    calculate_single_hour_weather_indicators)."""

    def setUp(self):
        self.category = DeviceCategory.objects.create(scada_id='CAT_WS', name='weatherStation')
        self.institution = Institution.objects.create(scada_id='INST_WS', name='Test Institution')
        self.station = Device.objects.create(
            scada_id='WS1', name='Test Station',
            category=self.category, institution=self.institution, is_active=True,
        )
        # Hora dentro de la ventana de luz (06-18h) para que la irradiancia no se
        # descarte por el filtro horario de calculate_single_hour_weather_indicators.
        self.hour_start = COLOMBIA_TZ.localize(datetime(2026, 6, 15, 12, 0))

        WeatherStationMeasurement.objects.create(
            device=self.station, date=self.hour_start + timedelta(minutes=1),
            irradiance=500.0, temperature=25.0, humidity=60.0,
            windSpeed=10.0, windDirection=180.0, precipitation=0.2,
        )
        WeatherStationMeasurement.objects.create(
            device=self.station, date=self.hour_start + timedelta(minutes=10),
            irradiance=600.0, temperature=27.0, humidity=62.0,
            windSpeed=12.0, windDirection=190.0, precipitation=0.3,
        )

    def test_mapea_irradiancia_y_temperatura(self):
        calculate_hourly_rollup(
            start_hour_str=self.hour_start.isoformat(),
            end_hour_str=self.hour_start.isoformat(),
        )
        row = HourlyWeatherIndicators.objects.get(device=self.station, hour=self.hour_start)

        self.assertAlmostEqual(row.avg_irradiance_wm2, 550.0)
        self.assertAlmostEqual(row.avg_temperature_c, 26.0)
        self.assertAlmostEqual(row.max_temperature_c, 27.0)
        self.assertAlmostEqual(row.min_temperature_c, 25.0)
        # Último valor de la hora (acumulador), no promedio ni suma.
        self.assertAlmostEqual(row.precipitation_cm, 0.3)
        self.assertEqual(row.measurement_count, 2)

    def test_idempotente_no_duplica_filas(self):
        calculate_hourly_rollup(
            start_hour_str=self.hour_start.isoformat(),
            end_hour_str=self.hour_start.isoformat(),
        )
        first = HourlyWeatherIndicators.objects.get(device=self.station, hour=self.hour_start)

        calculate_hourly_rollup(
            start_hour_str=self.hour_start.isoformat(),
            end_hour_str=self.hour_start.isoformat(),
        )
        rows = HourlyWeatherIndicators.objects.filter(device=self.station, hour=self.hour_start)

        self.assertEqual(rows.count(), 1)
        self.assertEqual(rows.first().pk, first.pk)


class WeatherDailyChartDataNameErrorRegressionTests(TestCase):
    """Regresión del bug pre-existente: `calculate_single_day_weather_chart_data` se
    invocaba en tasks.py sin estar importada. El NameError quedaba silenciado por el
    `except Exception` amplio de `_calculate_daily_weather_station_data`, así que
    WeatherStationChartData NUNCA se creaba (aunque WeatherStationIndicators sí, porque
    se guarda ANTES de llegar al chart). Con el import corregido, ambos deben crearse."""

    def setUp(self):
        self.category = DeviceCategory.objects.create(scada_id='CAT_WS2', name='weatherStation')
        self.institution = Institution.objects.create(scada_id='INST_WS2', name='Test Institution')
        self.station = Device.objects.create(
            scada_id='WS2', name='Test Station 2',
            category=self.category, institution=self.institution, is_active=True,
        )
        self.test_date = datetime(2026, 6, 15).date()
        base = COLOMBIA_TZ.localize(datetime.combine(self.test_date, time(10, 0)))
        WeatherStationMeasurement.objects.create(
            device=self.station, date=base,
            irradiance=500.0, temperature=25.0, humidity=60.0,
            windSpeed=10.0, windDirection=180.0, precipitation=0.1,
        )
        WeatherStationMeasurement.objects.create(
            device=self.station, date=base + timedelta(minutes=2),
            irradiance=600.0, temperature=26.0, humidity=62.0,
            windSpeed=12.0, windDirection=190.0, precipitation=0.2,
        )

    def test_chart_data_diario_se_crea_sin_nameerror(self):
        calculate_weather_station_indicators(
            time_range='daily',
            start_date_str=self.test_date.isoformat(),
            end_date_str=self.test_date.isoformat(),
            device_id=self.station.scada_id,
        )

        # Antes del fix, esta fila JAMÁS se creaba (NameError silenciado).
        chart = WeatherStationChartData.objects.get(device=self.station, date=self.test_date)
        self.assertEqual(len(chart.hourly_irradiance), 24)
        # `calculate_single_day_weather_chart_data` agrupa por `data['date'].hour` SIN
        # convertir a Bogotá (defecto preexistente, fuera de alcance de esta corrección:
        # solo ataja el NameError de la llamada faltante de import). Django devuelve los
        # datetimes ya-aware en UTC, así que 10:00 Bogotá (UTC-5) cae en el bucket UTC 15,
        # no en el 10. Promedio de las dos lecturas: (500 + 600) / 2 = 550.
        self.assertAlmostEqual(chart.hourly_irradiance[15], 550.0)
        self.assertGreater(chart.daily_irradiance_kwh_m2, 0.0)
