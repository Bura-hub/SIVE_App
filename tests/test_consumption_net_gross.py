"""
Tests del consumo NETO vs BRUTO de los medidores eléctricos.

- NETO  = Σ(totalActivePower)              (incluye inyección negativa; net metering)
- BRUTO = Σ(max(totalActivePower, 0))      (solo energía tomada de la red)

Ambos comparten la misma conversión a kWh (totalActivePower ya está en kW → factor 1)
y la integración Δt de indicators/energy.py.
"""
from datetime import datetime, time

from django.test import TestCase

from scada_proxy.models import Device, Institution, DeviceCategory, MeterMeasurement
from scada_proxy.tasks import upsert_measurements_page
from indicators.models import DailyChartData
from indicators.energy import SAMPLE_INTERVAL_HOURS
from indicators.tasks import calculate_and_save_daily_data, COLOMBIA_TZ


class ConsumptionNetGrossTests(TestCase):
    def setUp(self):
        self.category = DeviceCategory.objects.create(scada_id='CAT_EM', name='electricMeter')
        self.institution = Institution.objects.create(scada_id='INST', name='Test')
        self.device = Device.objects.create(
            scada_id='EM1', name='Meter',
            category=self.category, institution=self.institution, is_active=True,
        )
        # Fecha fija (sin now(): determinista). Mediodía Bogotá → mismo día calendario en UTC y Bogotá.
        self.date = datetime(2026, 6, 15).date()
        base = COLOMBIA_TZ.localize(datetime.combine(self.date, time(12, 0)))
        # totalActivePower en kW: +150 (importa), -40 (inyecta/exporta), +100 (importa)
        # Insertadas por el helper real de ingesta (dual-write v1+v2): las
        # tareas migradas leen las tablas tipadas v2.
        upsert_measurements_page(self.device, [
            (base.replace(minute=i * 2), {'totalActivePower': power})
            for i, power in enumerate([150.0, -40.0, 100.0])
        ])

    def test_daily_net_and_gross_consumption(self):
        calculate_and_save_daily_data(
            start_date_str=self.date.isoformat(),
            end_date_str=self.date.isoformat(),
        )
        obj = DailyChartData.objects.get(date=self.date)

        dt = SAMPLE_INTERVAL_HOURS
        # NETO = (150 - 40 + 100) · Δt = 210 · Δt ; BRUTO = (150 + 100) · Δt = 250 · Δt
        self.assertAlmostEqual(obj.daily_consumption, 210.0 * dt, places=6)
        self.assertAlmostEqual(obj.daily_gross_consumption, 250.0 * dt, places=6)
        # El bruto ignora la inyección, así que siempre es ≥ neto cuando hay exportación.
        self.assertGreater(obj.daily_gross_consumption, obj.daily_consumption)

    def test_gross_equals_net_without_export(self):
        # Sin valores negativos, neto y bruto coinciden.
        MeterMeasurement.objects.all().delete()
        base = COLOMBIA_TZ.localize(datetime.combine(self.date, time(9, 0)))
        upsert_measurements_page(self.device, [
            (base.replace(minute=i * 2), {'totalActivePower': power})
            for i, power in enumerate([80.0, 120.0])
        ])
        calculate_and_save_daily_data(
            start_date_str=self.date.isoformat(),
            end_date_str=self.date.isoformat(),
        )
        obj = DailyChartData.objects.get(date=self.date)
        self.assertAlmostEqual(obj.daily_gross_consumption, obj.daily_consumption, places=6)

    def test_net_negativo_por_exceso_de_exportacion(self):
        # Se exporta más de lo que se importa: el NETO puede ser negativo (net metering),
        # el BRUTO solo cuenta lo tomado de la red.
        MeterMeasurement.objects.all().delete()
        base = COLOMBIA_TZ.localize(datetime.combine(self.date, time(9, 0)))
        upsert_measurements_page(self.device, [
            (base.replace(minute=i * 2), {'totalActivePower': power})
            for i, power in enumerate([100.0, -150.0, 20.0])
        ])
        calculate_and_save_daily_data(
            start_date_str=self.date.isoformat(), end_date_str=self.date.isoformat())
        obj = DailyChartData.objects.get(date=self.date)
        dt = SAMPLE_INTERVAL_HOURS
        # NETO = (100 - 150 + 20)·dt = -30·dt ; BRUTO = (100 + 20)·dt = 120·dt
        self.assertAlmostEqual(obj.daily_consumption, -30.0 * dt, places=6)
        self.assertAlmostEqual(obj.daily_gross_consumption, 120.0 * dt, places=6)

    def test_solo_exportacion_bruto_es_cero(self):
        # Todas las lecturas negativas (solo inyección): BRUTO = 0, NETO < 0.
        MeterMeasurement.objects.all().delete()
        base = COLOMBIA_TZ.localize(datetime.combine(self.date, time(9, 0)))
        upsert_measurements_page(self.device, [
            (base.replace(minute=i * 2), {'totalActivePower': power})
            for i, power in enumerate([-50.0, -30.0])
        ])
        calculate_and_save_daily_data(
            start_date_str=self.date.isoformat(), end_date_str=self.date.isoformat())
        obj = DailyChartData.objects.get(date=self.date)
        dt = SAMPLE_INTERVAL_HOURS
        self.assertAlmostEqual(obj.daily_gross_consumption, 0.0, places=6)
        self.assertAlmostEqual(obj.daily_consumption, -80.0 * dt, places=6)
