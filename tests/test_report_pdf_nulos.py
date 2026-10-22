"""PDF de reportes: un dato no disponible (None) sale como celda vacía y la cabecera se reconoce aunque la
primera fila sea nula (antes salía «None» y «Performance ratio pct»)."""
import os
import tempfile
from unittest import mock

from django.test import SimpleTestCase

from indicators import tasks


class PdfDatosNulosTests(SimpleTestCase):
    def _tabla(self, filas):
        from reportlab import platypus
        capturadas = []
        real_table = platypus.Table

        def espia(data, *args, **kwargs):
            capturadas.append(data)
            return real_table(data, *args, **kwargs)

        with tempfile.TemporaryDirectory() as d, mock.patch.object(platypus, 'Table', side_effect=espia):
            tasks.generate_pdf_file(filas, os.path.join(d, 'r.pdf'), 'inverter_performance')
        # La tabla de datos es la que lleva la columna del PR en la cabecera.
        return next(t for t in capturadas if any('erformance' in str(c) for c in t[0]))

    def test_none_es_celda_vacia_y_cabecera_numerica(self):
        filas = [
            {'name': 'Inversor 1', 'date': '2026-10-01', 'performance_ratio_pct': None},
            {'name': 'Inversor 1', 'date': '2026-10-02', 'performance_ratio_pct': 78.5},
        ]
        tabla = self._tabla(filas)
        textos = [str(c) for fila in tabla for c in fila]
        self.assertNotIn('None', textos)
        self.assertNotIn('Performance ratio pct', textos)
        self.assertEqual(tabla[1][2], '')
