"""
Tests del consumo NETO vs BRUTO de los medidores eléctricos.

- NETO  = Σ(totalActivePower)              (incluye inyección negativa; net metering)
- BRUTO = Σ(max(totalActivePower, 0))      (solo energía tomada de la red)

Ambos comparten la misma conversión a kWh (totalActivePower ya está en kW → factor 1)
y la integración Δt de indicators/energy.py.
"""
from datetime import datetime, time

from django.test import TestCase

from scada_proxy.models import Device, Institution, DeviceCategory, Measurement
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
        for i, power in enumerate([150.0, -40.0, 100.0]):
            Measurement.objects.create(
                device=self.device,
                date=base.replace(minute=i * 2),
                data={'totalActivePower': power},
            )

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
        Measurement.objects.all().delete()
        base = COLOMBIA_TZ.localize(datetime.combine(self.date, time(9, 0)))
        for i, power in enumerate([80.0, 120.0]):
            Measurement.objects.create(
                device=self.device,
                date=base.replace(minute=i * 2),
                data={'totalActivePower': power},
            )
        calculate_and_save_daily_data(
            start_date_str=self.date.isoformat(),
            end_date_str=self.date.isoformat(),
        )
        obj = DailyChartData.objects.get(date=self.date)
        self.assertAlmostEqual(obj.daily_gross_consumption, obj.daily_consumption, places=6)
