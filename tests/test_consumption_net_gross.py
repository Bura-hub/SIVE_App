"""
Tests de la gráfica diaria del inicio (DailyChartData) con la convención de la tesis y del mercado P2P
(diseño, C10 y D2):

- daily_consumption        = demanda D de los circuitos del Medidor 1 de cada institución. En medidores netos
                             (Mariana, UCC, Udenar) se reconstruye: D = max(0, P_M1 + FV aguas abajo).
- daily_gross_consumption  = energía tomada de la red = D − autoconsumo.
- daily_generation         = generación del inversor de la institución.
- daily_balance            = generación − demanda.

Antes se sumaban todos los medidores de todas las sedes con su signo (C10).
"""
from datetime import datetime, time, timedelta

from django.test import TestCase

from indicators.institution_config import INSTITUCIONES
from indicators.models import DailyChartData
from indicators.tasks import COLOMBIA_TZ, calculate_and_save_daily_data
from scada_proxy.models import Device, DeviceCategory, Institution
from scada_proxy.tasks import upsert_measurements_page

MARIANA = '0357e3a6-ebdd-45f2-bd1a-0c384c522df3'


class DailyChartPlantasTests(TestCase):
    def setUp(self):
        cat_med = DeviceCategory.objects.create(scada_id='CAT_EM', name='electricMeter')
        cat_inv = DeviceCategory.objects.create(scada_id='CAT_INV', name='inverter')
        inst = Institution.objects.create(scada_id=MARIANA, name='Mariana')
        cfg = INSTITUCIONES[MARIANA]
        self.m1 = Device.objects.create(scada_id=cfg['medidor_demanda'], name='M1', category=cat_med,
                                        institution=inst)
        self.m2 = Device.objects.create(scada_id='otro', name='M2', category=cat_med, institution=inst)
        self.inv = Device.objects.create(scada_id=cfg['inversores_generacion'][0], name='Fronius',
                                         category=cat_inv, institution=inst)
        self.date = datetime(2026, 6, 15).date()

    def _hora(self, device, hora, campo, valor):
        base = COLOMBIA_TZ.localize(datetime.combine(self.date, time(hora, 0)))
        upsert_measurements_page(device, [(base + timedelta(minutes=2 * i), {campo: valor}) for i in range(30)])

    def _calcular(self):
        calculate_and_save_daily_data(start_date_str=self.date.isoformat(), end_date_str=self.date.isoformat())
        return DailyChartData.objects.get(date=self.date)

    def test_medidor_neto_con_exportacion(self):
        # Mediodía: la FV da 12 kW y el M1 (punto de conexión) marca −4 kW: se exportan 4 y la carga es 8.
        self._hora(self.inv, 12, 'acPower', 12000.0)
        self._hora(self.m1, 12, 'totalActivePower', -4.0)
        # Noche: sin FV, el M1 importa 5 kW.
        self._hora(self.m1, 20, 'totalActivePower', 5.0)
        self._hora(self.m2, 20, 'totalActivePower', 50.0)       # otro circuito: no entra
        obj = self._calcular()
        self.assertAlmostEqual(obj.daily_generation, 12.0)
        self.assertAlmostEqual(obj.daily_consumption, 8.0 + 5.0)
        self.assertAlmostEqual(obj.daily_gross_consumption, 5.0)   # de la red solo la noche
        self.assertAlmostEqual(obj.daily_balance, 12.0 - 13.0)

    def test_hora_de_medidor_incompleta_no_suma_demanda(self):
        base = COLOMBIA_TZ.localize(datetime.combine(self.date, time(9, 0)))
        upsert_measurements_page(self.m1, [(base + timedelta(minutes=2 * i), {'totalActivePower': 7.0})
                                           for i in range(10)])  # 10 < 15 muestras
        obj = self._calcular()
        self.assertAlmostEqual(obj.daily_consumption, 0.0)
        self.assertAlmostEqual(obj.daily_gross_consumption, 0.0)
