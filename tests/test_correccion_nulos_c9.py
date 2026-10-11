"""
C9 (corrección de octubre de 2026): una columna NULL es un dato no medido, no un 0.

Antes `_row_get` devolvía 0 para NULL: una fase en NULL entraba al desbalance como 0 V y daba
un desbalance enorme, y un NULL contaba como 0 en los promedios.
"""
from django.test import SimpleTestCase

from indicators.services.meter_calc import METER_FIELDS, compute_meter_indicators
from indicators.services.rows import _row_get




def _meter_row(**kw):
    row = {k: None for k in METER_FIELDS}
    row.update(kw)
    return row


class RowGetNullTests(SimpleTestCase):
    def test_null_devuelve_none(self):
        self.assertIsNone(_row_get({'x': None}, 'x'))

    def test_valor_real_se_conserva_incluido_el_cero(self):
        self.assertEqual(_row_get({'x': 0.0}, 'x'), 0.0)
        self.assertEqual(_row_get({'x': 5.5}, 'x'), 5.5)


class MeterNullPhaseTests(SimpleTestCase):
    def test_fase_null_descarta_la_muestra_del_desbalance(self):
        rows = [
            # Antes: (230, 230, 0) -> desbalance del 100 %.
            _meter_row(voltagePhaseA=230.0, voltagePhaseB=230.0, voltagePhaseC=None),
            _meter_row(voltagePhaseA=228.0, voltagePhaseB=230.0, voltagePhaseC=232.0),
        ]
        result = compute_meter_indicators(rows)
        self.assertAlmostEqual(result['max_voltage_unbalance_pct'], 2 / 230 * 100)

    def test_factor_de_potencia_null_no_baja_la_media(self):
        rows = [_meter_row(totalPowerFactor=0.9), _meter_row(totalPowerFactor=None)]
        self.assertAlmostEqual(compute_meter_indicators(rows)['avg_power_factor'], 0.9)
