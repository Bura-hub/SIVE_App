"""
Golden tests de la fórmula canónica de energía (indicators/energy.py).

Son tests PUROS (sin Django/BD): se pueden ejecutar en cualquier host con
    python3 -m unittest tests.unit.test_energy_formula
desde la raíz del proyecto (/proyecto/iteracion2/SIVET_App/SIVET_App).

Fijan el comportamiento correcto que corrige los bugs C1 (falta Δt / inconsistencia
mensual-vs-diario) y C2 (agregación de flota) de indicators/tasks.py.
"""
import unittest

from indicators.energy import (
    SAMPLE_INTERVAL_HOURS,
    WATTS_PER_KILOWATT,
    energy_kwh_from_power_sum,
    energy_kwh_from_samples,
)


class EnergyFormulaTests(unittest.TestCase):
    def test_interval_is_two_minutes(self):
        # indicators.md: Δt = 2/60 h ; 720 muestras/día
        self.assertAlmostEqual(SAMPLE_INTERVAL_HOURS, 2.0 / 60.0, places=12)
        self.assertAlmostEqual(SAMPLE_INTERVAL_HOURS * 720, 24.0, places=9)

    def test_constant_power_one_device_one_day(self):
        # 1000 W constantes, 1 día = 720 muestras de 2 min.
        # E = 1000 W * 24 h / 1000 = 24 kWh
        samples = [1000.0] * 720
        self.assertAlmostEqual(energy_kwh_from_samples(samples), 24.0, places=6)

    def test_delta_t_is_applied(self):
        # Sin Δt (bug anterior) la suma de 720 muestras de 1000 W daría 720000/1000=720.
        # Con Δt (correcto) da 24. Verificamos que NO es 720 (se aplica la integración).
        s = 1000.0 * 720
        self.assertAlmostEqual(energy_kwh_from_power_sum(s), 24.0, places=6)
        self.assertNotAlmostEqual(energy_kwh_from_power_sum(s), 720.0, places=3)

    def test_fleet_energy_sums_devices_not_averages(self):
        # 10 inversores, cada uno 500 W constantes, 720 muestras/día c/u => 7200 muestras.
        # Energía de la flota = 10 * (500 W * 24 h / 1000) = 120 kWh.
        # El bug C2 (dividir por el nº total de mediciones y multiplicar por 24) daba 12 kWh.
        fleet_samples = [500.0] * (10 * 720)
        self.assertAlmostEqual(energy_kwh_from_samples(fleet_samples), 120.0, places=6)

    def test_sum_matches_samples(self):
        samples = [500.0] * 100 + [1500.0] * 50
        self.assertAlmostEqual(
            energy_kwh_from_samples(samples),
            energy_kwh_from_power_sum(sum(samples)),
            places=9,
        )

    def test_none_and_empty(self):
        self.assertEqual(energy_kwh_from_power_sum(None), 0.0)
        self.assertEqual(energy_kwh_from_power_sum(0.0), 0.0)
        self.assertEqual(energy_kwh_from_samples([]), 0.0)

    def test_none_samples_ignored(self):
        self.assertAlmostEqual(
            energy_kwh_from_samples([1000.0, None, 1000.0]),
            energy_kwh_from_power_sum(2000.0),
            places=9,
        )

    def test_watts_assumption_documented(self):
        # El factor de unidad está aislado en una sola constante (a confirmar por auditoría).
        self.assertEqual(WATTS_PER_KILOWATT, 1000.0)


if __name__ == "__main__":
    unittest.main()
