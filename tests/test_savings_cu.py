"""
Ahorro diario con la tarifa al usuario (external_energy.tasks.calculate_energy_savings, diseño C13 y D8):
energía autoconsumida × CU mensual del comercializador, recalculando los días recientes.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase

from external_energy.models import EnergySavings
from external_energy.tasks import calculate_energy_savings
from indicators.institution_config import INSTITUCIONES
from indicators.services.date_ranges import COLOMBIA_TZ
from indicators.services.solar_kpis import cargar_tarifas
from scada_proxy.models import Device, DeviceCategory, Institution
from scada_proxy.tasks import upsert_measurements_page

MARIANA = '0357e3a6-ebdd-45f2-bd1a-0c384c522df3'
DIA = date(2025, 7, 15)


class AhorroConCUTests(TestCase):
    def setUp(self):
        cache.clear()   # la energía por institución se guarda en caché por mes
        cat_med = DeviceCategory.objects.create(scada_id='c-med', name='electricMeter')
        cat_inv = DeviceCategory.objects.create(scada_id='c-inv', name='inverter')
        inst = Institution.objects.create(scada_id=MARIANA, name='Mariana')
        cfg = INSTITUCIONES[MARIANA]
        self.m1 = Device.objects.create(scada_id=cfg['medidor_demanda'], name='M1', category=cat_med,
                                        institution=inst)
        self.inv = Device.objects.create(scada_id=cfg['inversores_generacion'][0], name='Fronius',
                                         category=cat_inv, institution=inst)

    def _hora(self, device, hora, campo, valor):
        base = COLOMBIA_TZ.localize(datetime(DIA.year, DIA.month, DIA.day, hora))
        upsert_measurements_page(device, [(base + timedelta(minutes=2 * i), {campo: valor}) for i in range(30)])

    def test_autoconsumo_por_cu_y_exportacion(self):
        self._hora(self.inv, 12, 'acPower', 12000.0)            # 12 kWh generados
        self._hora(self.m1, 12, 'totalActivePower', -4.0)       # 4 kWh exportados → autoconsumo 8
        self._hora(self.m1, 20, 'totalActivePower', 5.0)        # 5 kWh de noche
        calculate_energy_savings(start_date_str=DIA.isoformat(), end_date_str=DIA.isoformat())
        s = EnergySavings.objects.get(date=DIA)
        cu = cargar_tarifas()['asc']['2025-07']
        self.assertEqual(s.total_generated_kwh, Decimal('12.00'))
        self.assertEqual(s.total_consumed_kwh, Decimal('13.00'))
        self.assertEqual(s.excess_energy_kwh, Decimal('4.00'))
        self.assertAlmostEqual(float(s.total_savings_cop), 8.0 * cu, places=1)
        self.assertAlmostEqual(float(s.average_price_kwh), cu, places=3)
        self.assertAlmostEqual(float(s.self_consumption_percentage), 100 * 8 / 12, places=1)

    def test_recalcula_un_dia_existente(self):
        EnergySavings.objects.create(date=DIA, total_consumed_kwh=1, total_generated_kwh=1, average_price_kwh=1,
                                     total_savings_cop=1, savings_percentage=1, self_consumption_percentage=1,
                                     excess_energy_kwh=0)
        self._hora(self.inv, 12, 'acPower', 6000.0)
        self._hora(self.m1, 12, 'totalActivePower', 2.0)
        r = calculate_energy_savings(start_date_str=DIA.isoformat(), end_date_str=DIA.isoformat())
        self.assertEqual(r['updated'], 1)
        self.assertEqual(EnergySavings.objects.get(date=DIA).total_generated_kwh, Decimal('6.00'))
