"""
Los textos que el backend arma para la pantalla usan coma decimal (es-CO), como el resto de la interfaz:
el cambio porcentual de las tarjetas del Dashboard, los supuestos de «Indicadores Solares» y el tamaño de
los reportes. Los valores numéricos que el frontend vuelve a leer (value) siguen con punto.
"""
import re

from django.test import SimpleTestCase

from indicators.institution_config import INSTITUCIONES
from indicators.services.formato import coma
from indicators.services.kpi import calculate_kpi_metrics
from indicators.services.solar_kpis import _supuestos
from indicators.tasks import format_file_size

PUNTO_DECIMAL = re.compile(r'\d\.\d')


class ComaDecimalTests(SimpleTestCase):
    def test_coma(self):
        self.assertEqual(coma(17.55), '17,55')
        self.assertEqual(coma(-3.912, 2), '-3,91')
        self.assertEqual(coma(4, 1), '4,0')

    def test_cambio_de_las_tarjetas(self):
        k = calculate_kpi_metrics(29240.0, 30430.0, 'Generación', 'Wh')
        self.assertNotRegex(k['change'], PUNTO_DECIMAL)
        self.assertNotRegex(k['description'], PUNTO_DECIMAL)
        self.assertIn('%', k['change'])
        float(k['value'])  # el valor sigue siendo legible como número

    def test_supuestos_de_indicadores_solares(self):
        cfg = next(iter(INSTITUCIONES.values()))
        for s in _supuestos(cfg):
            self.assertNotRegex(s, PUNTO_DECIMAL, s)

    def test_tamano_de_reporte(self):
        self.assertEqual(format_file_size(1536), '1,5 KB')
        self.assertEqual(format_file_size(0), '0 B')
