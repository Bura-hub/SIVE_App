"""
Tests del clamp de eficiencia DC-AC de inversores (arreglo de la Ola 1).

El dato crudo del connector trae dcPower < acPower en ~92% de las filas (físicamente
imposible: la entrada DC debe superar a la salida AC), lo que producía eficiencias
>100% (hasta 185%). El cálculo acota dc_ac_efficiency_pct a [0,100]. Estos tests
verifican end-to-end que el clamp engancha cuando toca y NO altera los valores normales.
"""
from datetime import datetime, time, timedelta

from django.test import TestCase
from django.utils import timezone

from indicators.models import InverterIndicators
from indicators.tasks import calculate_inverter_indicators
from scada_proxy.models import Device, Institution, DeviceCategory


class InverterEfficiencyClampTests(TestCase):
    def setUp(self):
        self.category = DeviceCategory.objects.create(
            scada_id='CAT_INVERTER', name='inverter', description='Inversor')
        self.institution = Institution.objects.create(scada_id='INST_INV', name='Inst Inv')
        self.device = Device.objects.create(
            name='Test Inverter', scada_id='TEST_INV_001',
            category=self.category, institution=self.institution)
        self.test_date = timezone.now().date()

    def _run(self, ac_power, dc_power):
        from scada_proxy.tasks import upsert_measurements_page
        base = timezone.make_aware(datetime.combine(self.test_date, time(12, 0)))
        upsert_measurements_page(self.device, [
            (base, {'acPower': ac_power, 'dcPower': dc_power}),
            (base + timedelta(minutes=2), {'acPower': ac_power, 'dcPower': dc_power}),
        ])
        calculate_inverter_indicators(self.device.id, self.test_date.strftime('%Y-%m-%d'), 'daily')
        return InverterIndicators.objects.get(
            device=self.device, date=self.test_date, time_range='daily')

    def test_eficiencia_imposible_se_acota_a_100(self):
        # acPower (1000) > dcPower (500): eficiencia cruda = 200% -> debe quedar en 100.
        ind = self._run(ac_power=1000.0, dc_power=500.0)
        self.assertEqual(ind.dc_ac_efficiency_pct, 100.0)

    def test_eficiencia_normal_no_se_altera(self):
        # acPower (400) < dcPower (500): eficiencia = 80% (dentro de rango físico).
        ind = self._run(ac_power=400.0, dc_power=500.0)
        self.assertAlmostEqual(ind.dc_ac_efficiency_pct, 80.0, places=1)
