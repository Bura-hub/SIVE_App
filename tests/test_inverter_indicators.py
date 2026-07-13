"""
Tests del clamp de eficiencia DC-AC de inversores (arreglo de la Ola 1).

El dato crudo del connector trae dcPower < acPower en ~92% de las filas (físicamente
imposible: la entrada DC debe superar a la salida AC), lo que producía eficiencias
>100% (hasta 185%). El cálculo acota dc_ac_efficiency_pct a [0,100]. Estos tests
verifican end-to-end que el clamp engancha cuando toca y NO altera los valores normales.
"""
from datetime import datetime, time, timedelta

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from indicators.models import InverterIndicators
from indicators.services.inverter_calc import (
    INVERTER_FIELDS,
    MIN_CURRENT_A_FOR_UNBALANCE,
    compute_inverter_indicators,
)
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


def _inverter_row(**overrides):
    """Fila mínima válida para `compute_inverter_indicators` (todas las columnas de
    INVERTER_FIELDS presentes, en None salvo lo que se sobreescriba)."""
    row = {field: None for field in INVERTER_FIELDS}
    row.update(overrides)
    return row


class InverterCurrentUnbalanceGateTests(SimpleTestCase):
    """Tests del gate de carga mínima + tope defensivo del desbalance de corriente de
    inyección (mismo artefacto de la fórmula NEMA que en meter_calc.py, ver
    MIN_CURRENT_A_FOR_UNBALANCE en indicators/services/inverter_calc.py)."""

    def test_desbalance_con_inyeccion_real_se_calcula_normalmente(self):
        # avg = 10 A (>= umbral), max_deviation = 2 A -> 20% de desbalance real.
        rows = [_inverter_row(acCurrentPhaseA=8.0, acCurrentPhaseB=10.0, acCurrentPhaseC=12.0)]
        result = compute_inverter_indicators(rows)
        self.assertAlmostEqual(result['max_current_unbalance_pct'], 20.0)

    def test_inyeccion_casi_nula_con_fase_en_cero_queda_excluida(self):
        # avg = 0.2 A (< MIN_CURRENT_A_FOR_UNBALANCE): sin el gate, esta muestra
        # daría max_deviation(0.4)/avg(0.2)*100 = 200%, el artefacto reportado.
        self.assertLess(0.2, MIN_CURRENT_A_FOR_UNBALANCE)
        rows = [_inverter_row(acCurrentPhaseA=0.0, acCurrentPhaseB=0.0, acCurrentPhaseC=0.6)]
        result = compute_inverter_indicators(rows)
        # Única muestra del día excluida por el gate -> sin datos válidos -> 0.
        self.assertEqual(result['max_current_unbalance_pct'], 0)

    def test_desbalance_extremo_con_inyeccion_real_se_acota_a_100(self):
        # avg = 10.1667 A (>= umbral, inyección real), pero max_deviation/avg ~ 195%:
        # el tope defensivo debe acotarlo a 100%.
        rows = [_inverter_row(acCurrentPhaseA=0.0, acCurrentPhaseB=0.5, acCurrentPhaseC=30.0)]
        result = compute_inverter_indicators(rows)
        self.assertGreaterEqual((0.0 + 0.5 + 30.0) / 3, MIN_CURRENT_A_FOR_UNBALANCE)
        self.assertEqual(result['max_current_unbalance_pct'], 100.0)

    def test_desbalance_de_voltaje_no_se_altera_por_el_gate(self):
        # El gate/cap es exclusivo de corriente; el voltaje conserva su fórmula original.
        rows = [_inverter_row(
            acCurrentPhaseA=0.0, acCurrentPhaseB=0.0, acCurrentPhaseC=0.0,
            acVoltagePhaseA=210.0, acVoltagePhaseB=220.0, acVoltagePhaseC=230.0,
        )]
        result = compute_inverter_indicators(rows)
        self.assertAlmostEqual(result['max_voltage_unbalance_pct'], (10 / 220) * 100)
        self.assertEqual(result['max_current_unbalance_pct'], 0)
