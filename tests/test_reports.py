"""Tests de la generación de informes (marca/resumen/CSV).

Cubren la lógica pura de `indicators/reports/branding.py` — sobre todo `compute_summary`, que
recupera el float crudo desde las celdas ya formateadas ('98.20%' → 98.2) y agrega por columna
(suma de energía, promedio de %, máx/mín). Antes esta agregación descartaba las columnas con '%'.
"""

import os
import tempfile

from django.test import SimpleTestCase

from indicators.reports import branding


class ToNumberTests(SimpleTestCase):
    def test_parses_percent_and_thousands(self):
        self.assertEqual(branding.to_number('98.20%'), 98.20)
        self.assertEqual(branding.to_number('1,234.50'), 1234.50)
        self.assertEqual(branding.to_number('0.00'), 0.0)
        self.assertEqual(branding.to_number(5), 5.0)

    def test_non_numeric_is_none(self):
        self.assertIsNone(branding.to_number('N/A'))
        self.assertIsNone(branding.to_number(''))
        self.assertIsNone(branding.to_number(None))
        self.assertIsNone(branding.to_number('2026-07-01'))


class HeaderAndPeriodTests(SimpleTestCase):
    def test_pretty_header_known_column(self):
        self.assertEqual(branding.pretty_header('imported_energy_kwh'), 'Energía importada (kWh)')
        self.assertEqual(branding.pretty_header('avg_power_factor'), 'Factor de potencia')  # unidad vacía

    def test_period_label(self):
        ctx = {'start_date': '2026-07-01', 'end_date': '2026-07-10', 'time_range': 'daily'}
        self.assertEqual(branding.period_label(ctx), '2026-07-01 a 2026-07-10 (daily)')
        self.assertEqual(branding.period_label(None), '')


class ComputeSummaryTests(SimpleTestCase):
    def test_empty(self):
        s = branding.compute_summary([])
        self.assertEqual(s['record_count'], 0)
        self.assertEqual(s['metrics'], [])

    def test_aggregations_by_column_semantics(self):
        # Celdas tal como las producen los constructores (strings formateados, algunos con %).
        data = [
            {'name': 'M1', 'date': '2026-07-01', 'imported_energy_kwh': '100.00',
             'net_energy_consumption_kwh': '90.00', 'peak_demand_kw': '50.00', 'avg_power_factor': '0.90%'},
            {'name': 'M1', 'date': '2026-07-02', 'imported_energy_kwh': '200.00',
             'net_energy_consumption_kwh': '180.00', 'peak_demand_kw': '70.00', 'avg_power_factor': '1.00%'},
        ]
        s = branding.compute_summary(data)
        self.assertEqual(s['record_count'], 2)
        by_label = {m['label']: m for m in s['metrics']}

        # Energía → SUMA
        self.assertAlmostEqual(by_label['Energía importada']['value'], 300.0)
        self.assertEqual(by_label['Energía importada']['agg'], 'sum')
        self.assertAlmostEqual(by_label['Consumo neto']['value'], 270.0)
        # Demanda pico → MÁXIMO
        self.assertAlmostEqual(by_label['Demanda pico']['value'], 70.0)
        self.assertEqual(by_label['Demanda pico']['agg'], 'max')
        # Factor de potencia (columna con '%') → PROMEDIO, y NO se descarta
        self.assertIn('Factor de potencia', by_label)
        self.assertAlmostEqual(by_label['Factor de potencia']['value'], 0.95)
        self.assertEqual(by_label['Factor de potencia']['agg'], 'mean')

    def test_excludes_axis_and_non_numeric_columns(self):
        data = [{'name': 'M1', 'date': '2026-07-01', 'imported_energy_kwh': '10.00',
                 'wind_direction_distribution': {'N': 3}}]
        labels = {m['label'] for m in branding.compute_summary(data)['metrics']}
        # name/date/distribuciones no deben aparecer como métricas
        self.assertEqual(labels, {'Energía importada'})


class CsvTests(SimpleTestCase):
    def test_csv_has_utf8_bom(self):
        # Importado aquí para no cargar todo tasks.py si solo se corren los tests de branding.
        from indicators.tasks import generate_csv_file
        data = [{'name': 'Medidor Nariño', 'date': '2026-07-01', 'imported_energy_kwh': '10.00'}]
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'r.csv')
            generate_csv_file(data, path)
            raw = open(path, 'rb').read()
            # BOM UTF-8 para que Excel muestre tildes/ñ correctamente
            self.assertTrue(raw.startswith(b'\xef\xbb\xbf'))
            self.assertIn('Nariño'.encode('utf-8'), raw)
