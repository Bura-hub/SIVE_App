"""
Medidores (diseño, C17–C19): energía por integración de la potencia, demanda pico por bloques de reloj de 15 min y
factor de potencia con |FP|.
"""
from datetime import datetime, timedelta

from django.test import SimpleTestCase

from indicators.energy import SAMPLE_INTERVAL_HOURS
from indicators.services.date_ranges import COLOMBIA_TZ
from indicators.services.meter_calc import METER_FIELDS, compute_meter_indicators

T0 = COLOMBIA_TZ.localize(datetime(2026, 7, 15, 10, 0))


def _fila(minuto, p, **extra):
    row = {k: None for k in METER_FIELDS}
    row.update(date=T0 + timedelta(minutes=minuto), totalActivePower=p, **extra)
    return row


class MedidorTests(SimpleTestCase):
    def test_energia_integrada_de_la_potencia_no_de_los_registros(self):
        rows = [_fila(2 * i, p) for i, p in enumerate([10.0, -4.0, 6.0])]
        r = compute_meter_indicators(rows)
        self.assertAlmostEqual(r['imported_energy_kwh'], 16.0 * SAMPLE_INTERVAL_HOURS)
        self.assertAlmostEqual(r['exported_energy_kwh'], 4.0 * SAMPLE_INTERVAL_HOURS)
        self.assertAlmostEqual(r['net_energy_consumption_kwh'], 12.0 * SAMPLE_INTERVAL_HOURS)

    def test_mensual_es_la_suma_de_los_diarios(self):
        dia1 = [_fila(2 * i, 5.0) for i in range(30)]
        dia2 = [_fila(24 * 60 + 2 * i, 7.0) for i in range(30)]
        total = compute_meter_indicators(dia1 + dia2)['imported_energy_kwh']
        partes = compute_meter_indicators(dia1)['imported_energy_kwh'] + compute_meter_indicators(dia2)['imported_energy_kwh']
        self.assertAlmostEqual(total, partes)

    def test_pico_por_bloques_de_15_min_no_cruza_huecos(self):
        # 3 lecturas altas antes de un hueco de 3 h y 4 después: con la media móvil por posición se mezclaban.
        rows = [_fila(2 * i, 30.0) for i in range(3)] + [_fila(180 + 2 * i, 10.0) for i in range(8)]
        r = compute_meter_indicators(rows)
        self.assertAlmostEqual(r['peak_demand_kw'], 10.0)    # el bloque de 3 muestras no llega al mínimo

    def test_pico_es_la_media_del_bloque(self):
        rows = [_fila(2 * i, p) for i, p in enumerate([10, 20, 30, 40, 50, 60, 70, 80])]  # 10:00–10:14
        self.assertAlmostEqual(compute_meter_indicators(rows)['peak_demand_kw'], 45.0)

    def test_factor_de_potencia_con_signo(self):
        rows = [_fila(0, 5.0, totalPowerFactor=-0.95), _fila(2, 5.0, totalPowerFactor=0.95)]
        self.assertAlmostEqual(compute_meter_indicators(rows)['avg_power_factor'], 0.95)
