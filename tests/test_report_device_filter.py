"""
Exportar Reportes respeta los dispositivos elegidos.

El frontend envía el `scada_id` de cada dispositivo (un UUID). Los generadores hacían `int(device_id)`, que
fallaba, y el `except` quitaba el filtro en silencio: el reporte traía todos los dispositivos de la institución.

Se ejecuta con: python manage.py test tests.test_report_device_filter
"""

from datetime import date

from django.test import TestCase

from scada_proxy.models import Institution, DeviceCategory, Device
from indicators.models import ElectricMeterIndicators, InverterIndicators, WeatherStationIndicators
from indicators.tasks import (
    generate_electric_meter_report, generate_inverter_report, generate_weather_station_report,
)

DIA = date(2025, 8, 1)


class ReportDeviceFilterTests(TestCase):

    def setUp(self):
        self.inst = Institution.objects.create(scada_id='I-HUDN', name='HUDN')
        self.devs = {}
        for cat_name, modelo in (('electricmeter', ElectricMeterIndicators),
                                 ('inverter', InverterIndicators),
                                 ('weatherstation', WeatherStationIndicators)):
            cat = DeviceCategory.objects.create(scada_id=f'C-{cat_name}', name=cat_name)
            pares = []
            for n in (1, 2):
                uuid = f'{n}{len(self.devs)}8cf5fd-e92b-4f4b-b5eb-a62ccb1bdec{n}'
                dev = Device.objects.create(name=f'{cat_name} {n}', scada_id=uuid,
                                            category=cat, institution=self.inst)
                modelo.objects.create(device=dev, institution=self.inst, date=DIA, time_range='daily')
                pares.append(dev)
            self.devs[cat_name] = pares

    def _nombres(self, filas):
        return sorted({f['name'] for f in filas})

    def test_medidores_filtra_por_scada_id(self):
        uno = self.devs['electricmeter'][0]
        filas = generate_electric_meter_report(self.inst.id, [uno.scada_id], 'Resumen de Consumo', 'daily',
                                               '2025-08-01', '2025-08-31')
        self.assertEqual(self._nombres(filas), [uno.name])

    def test_inversores_filtra_por_scada_id(self):
        uno = self.devs['inverter'][1]
        filas = generate_inverter_report(self.inst.id, [uno.scada_id], 'Resumen de Generación', 'daily',
                                         '2025-08-01', '2025-08-31')
        self.assertEqual(self._nombres(filas), [uno.name])

    def test_estaciones_filtra_por_scada_id(self):
        uno = self.devs['weatherstation'][0]
        filas = generate_weather_station_report(self.inst.id, [uno.scada_id], 'Resumen Climático', 'daily',
                                                '2025-08-01', '2025-08-31')
        self.assertEqual(self._nombres(filas), [uno.name])

    def test_ids_enteros_siguen_valiendo(self):
        uno = self.devs['electricmeter'][1]
        filas = generate_electric_meter_report(self.inst.id, [str(uno.id)], 'Resumen de Consumo', 'daily',
                                               '2025-08-01', '2025-08-31')
        self.assertEqual(self._nombres(filas), [uno.name])

    def test_sin_dispositivos_trae_todos(self):
        filas = generate_electric_meter_report(self.inst.id, [], 'Resumen de Consumo', 'daily',
                                               '2025-08-01', '2025-08-31')
        self.assertEqual(len(filas), 2)

    def test_factor_de_potencia_sin_porcentaje(self):
        uno = self.devs['electricmeter'][0]
        ElectricMeterIndicators.objects.filter(device=uno).update(avg_power_factor=0.96, max_voltage_thd_pct=7.8)
        filas = generate_electric_meter_report(self.inst.id, [uno.scada_id], 'Calidad de Potencia', 'daily',
                                               '2025-08-01', '2025-08-31')
        self.assertEqual(filas[0]['avg_power_factor'], '0.96')
        self.assertEqual(filas[0]['max_voltage_thd_pct'], '7.80%')
