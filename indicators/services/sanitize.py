"""
Saneamiento de energía por registros acumulados (anti roll-over).

Un incremento entre lecturas consecutivas del registro acumulado no puede ser negativo
(reset del contador) ni superar por un margen amplio la energía integrada del día
(Σ|P|·Δt, fiable). Sin esta cota, un glitch/roll-over de una sola lectura corrompía
ElectricMeterIndicators con hasta ~5e8 kWh/día.
"""

ROLLOVER_CAP_FACTOR = 2.0        # tope = FACTOR * energía_integrada_del_período + MARGEN
ROLLOVER_CAP_MARGIN_KWH = 5.0


def _accumulate_register_energy(totals, cap_kwh):
    """Suma solo los incrementos válidos de una serie ORDENADA de lecturas de un
    registro acumulado (en kWh), descartando reinicios (delta<0) y saltos
    imposibles (delta>cap por roll-over o glitch de lectura)."""
    energy = 0.0
    prev = None
    for cur in totals:
        if prev is not None:
            delta = cur - prev
            if 0.0 <= delta <= cap_kwh:
                energy += delta
        prev = cur
    return energy
