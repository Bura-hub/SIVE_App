"""
Tests del saneamiento anti roll-over de contadores (arreglo de la Ola 1).

_accumulate_register_energy suma solo los incrementos válidos de una serie ORDENADA de
lecturas de un registro acumulado, descartando reinicios del contador (delta<0) y saltos
imposibles (delta>cap por roll-over o glitch). Sin esta cota, una sola lectura corrupta
inflaba ElectricMeterIndicators hasta ~5e8 kWh/día. Función pura -> SimpleTestCase.
"""
from django.test import SimpleTestCase

from indicators.tasks import _accumulate_register_energy, ROLLOVER_CAP_FACTOR


class RolloverSanitizationTests(SimpleTestCase):
    def test_incremento_monotono_normal(self):
        # 10->20->30 con cap holgado: suma de deltas = 20.
        self.assertAlmostEqual(_accumulate_register_energy([10.0, 20.0, 30.0], 100.0), 20.0)

    def test_reset_de_contador_se_descarta(self):
        # 100->110 (=10), 110->5 (negativo: reset, descartado), 5->15 (=10) => 20.
        self.assertAlmostEqual(_accumulate_register_energy([100.0, 110.0, 5.0, 15.0], 100.0), 20.0)

    def test_salto_imposible_por_rollover_se_descarta(self):
        # Glitch enorme (>cap) y su retorno negativo se descartan; solo cuenta 10->20.
        self.assertAlmostEqual(_accumulate_register_energy([10.0, 20.0, 5e8, 30.0], 100.0), 10.0)

    def test_una_sola_lectura_da_cero(self):
        self.assertEqual(_accumulate_register_energy([42.0], 100.0), 0.0)

    def test_serie_vacia_da_cero(self):
        self.assertEqual(_accumulate_register_energy([], 100.0), 0.0)

    def test_delta_en_el_limite_del_cap_se_incluye(self):
        # delta == cap -> incluido (condición es <=).
        self.assertAlmostEqual(_accumulate_register_energy([0.0, 100.0], 100.0), 100.0)

    def test_delta_justo_sobre_el_cap_se_excluye(self):
        self.assertEqual(_accumulate_register_energy([0.0, 100.01], 100.0), 0.0)

    def test_factor_de_cap_es_razonable(self):
        # Contrato: el tope es un múltiplo pequeño de la energía integrada, no ilimitado.
        self.assertGreaterEqual(ROLLOVER_CAP_FACTOR, 1.0)
        self.assertLessEqual(ROLLOVER_CAP_FACTOR, 5.0)
