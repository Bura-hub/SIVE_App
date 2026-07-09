"""
Golden tests de la fórmula canónica de energía (indicators/energy.py).

Son tests PUROS (sin Django/BD): se pueden ejecutar en cualquier host con
    python3 -m unittest tests.unit.test_energy_formula
desde la raíz del proyecto.

Fijan el comportamiento correcto que corrige los bugs C1 (falta Δt / inconsistencia
mensual-vs-diario), C2 (agregación de flota) y la UNIDAD por métrica (consumo en kW,
generación en W) de indicators/tasks.py.
"""
import unittest

from indicators.energy import (
    SAMPLE_INTERVAL_HOURS,
    POWER_UNIT_KW,
    POWER_UNIT_WATTS,
    energy_kwh_from_power_sum,
    energy_kwh_from_samples,
    consumption_energy_kwh,
    generation_energy_kwh,
)


class EnergyFormulaTests(unittest.TestCase):
    def test_interval_is_two_minutes(self):
        # indicators.md + auditoría: Δt = 2/60 h ; 720 muestras/día
        self.assertAlmostEqual(SAMPLE_INTERVAL_HOURS, 2.0 / 60.0, places=12)
        self.assertAlmostEqual(SAMPLE_INTERVAL_HOURS * 720, 24.0, places=9)

    def test_delta_t_is_applied(self):
        # Sin Δt (bug anterior) la suma de 720 muestras de 1000 W daría 720000/1000=720.
        # Con Δt (correcto) da 24. Verificamos que se aplica la integración.
        s = 1000.0 * 720
        self.assertAlmostEqual(energy_kwh_from_power_sum(s), 24.0, places=6)
        self.assertNotAlmostEqual(energy_kwh_from_power_sum(s), 720.0, places=3)

    def test_fleet_energy_sums_devices_not_averages(self):
        # 10 inversores, cada uno 500 W constantes, 720 muestras/día c/u => 7200 muestras.
        # Energía de la flota = 10 * (500 W * 24 h / 1000) = 120 kWh.
        # El bug C2 (dividir por el nº total de mediciones y multiplicar por 24) daba 12 kWh.
        fleet_samples = [500.0] * (10 * 720)
        self.assertAlmostEqual(energy_kwh_from_samples(fleet_samples), 120.0, places=6)

    # ---- Unidad por métrica (confirmada por scripts/audit_indicators.py) ----
    def test_consumption_is_kw_no_division(self):
        # totalActivePower en kW: un medidor a 10 kW constantes durante 1 día.
        # E = 10 kW * 24 h = 240 kWh (NO se divide por 1000).
        power_sum = 10.0 * 720  # Σ de 720 muestras de 10 kW
        self.assertAlmostEqual(consumption_energy_kwh(power_sum), 240.0, places=6)

    def test_generation_is_watts_divide_by_1000(self):
        # acPower en W: un inversor a 3000 W constantes durante 1 día.
        # E = 3000 W * 24 h / 1000 = 72 kWh.
        power_sum = 3000.0 * 720
        self.assertAlmostEqual(generation_energy_kwh(power_sum), 72.0, places=6)

    def test_consumption_and_generation_differ_by_1000(self):
        # Para la MISMA suma de potencia, el consumo (kW) es 1000× la generación (W).
        power_sum = 12345.0
        self.assertAlmostEqual(
            consumption_energy_kwh(power_sum),
            1000.0 * generation_energy_kwh(power_sum),
            places=6,
        )

    def test_unit_constants(self):
        self.assertEqual(POWER_UNIT_KW, 1.0)
        self.assertEqual(POWER_UNIT_WATTS, 1000.0)

    # ---- Robustez ----
    def test_none_and_empty(self):
        self.assertEqual(energy_kwh_from_power_sum(None), 0.0)
        self.assertEqual(consumption_energy_kwh(None), 0.0)
        self.assertEqual(generation_energy_kwh(None), 0.0)
        self.assertEqual(energy_kwh_from_samples([]), 0.0)

    def test_none_samples_ignored(self):
        self.assertAlmostEqual(
            energy_kwh_from_samples([1000.0, None, 1000.0]),
            energy_kwh_from_power_sum(2000.0),
            places=9,
        )


if __name__ == "__main__":
    unittest.main()
