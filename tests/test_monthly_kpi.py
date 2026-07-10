"""
Tests del KPI mensual de consumo (calculate_monthly_consumption_kpi).

Agrega MeterMeasurement crudo del mes en curso: consumo NETO = Σ(totalActivePower) y
BRUTO = Σ(max(totalActivePower, 0)) (Greatest clampa los negativos en la BD), ambos
integrados a kWh. Guarda un singleton MonthlyConsumptionKPI (pk=1). Las mediciones se
fechan en el momento actual para caer siempre dentro de la ventana del mes en curso.
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from indicators.energy import SAMPLE_INTERVAL_HOURS
from indicators.models import MonthlyConsumptionKPI
from indicators.tasks import calculate_monthly_consumption_kpi
from scada_proxy.models import Device, Institution, DeviceCategory
from scada_proxy.tasks import upsert_measurements_page


class MonthlyKpiTests(TestCase):
    def setUp(self):
        self.category = DeviceCategory.objects.create(scada_id='CAT_EM', name='electricMeter')
        self.institution = Institution.objects.create(scada_id='INST', name='Test')
        self.device = Device.objects.create(
            scada_id='EM1', name='Meter',
            category=self.category, institution=self.institution, is_active=True)

    def test_consumo_mensual_neto_y_bruto(self):
        # -10 min desde ahora: dentro del mes en curso y en el pasado.
        base = timezone.now() - timedelta(minutes=10)
        # kW: +100, -50 (inyección), +200 -> Neto=250, Bruto=300 (el -50 cuenta 0).
        upsert_measurements_page(self.device, [
            (base, {'totalActivePower': 100.0}),
            (base + timedelta(minutes=2), {'totalActivePower': -50.0}),
            (base + timedelta(minutes=4), {'totalActivePower': 200.0}),
        ])
        calculate_monthly_consumption_kpi.apply()
        kpi = MonthlyConsumptionKPI.objects.get(pk=1)
        dt = SAMPLE_INTERVAL_HOURS
        self.assertAlmostEqual(kpi.total_consumption_current_month, 250.0 * dt, places=6)
        self.assertAlmostEqual(kpi.total_gross_consumption_current_month, 300.0 * dt, places=6)
        # Con exportación, el bruto supera al neto.
        self.assertGreater(kpi.total_gross_consumption_current_month,
                           kpi.total_consumption_current_month)
