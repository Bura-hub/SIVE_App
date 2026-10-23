"""
Indicadores solares por institución (indicators/services/institution_energy.py y solar_kpis.py).

Casos con datos sintéticos que reproducen lo que se contrastó con el mercado P2P: medidor bruto
(HUDN: toda la FV se autoconsume), medidor neto con exportación (D = medida + FV), «faltante = 0» en la
generación, hora del medidor inválida con menos de 15 muestras, PR solo con días de estación válidos y tarifa
extrapolada cuando el mes no tiene CU publicado.
"""
from datetime import date, datetime, timedelta

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from indicators.institution_config import INSTITUCIONES
from indicators.services import solar_kpis
from indicators.services.date_ranges import COLOMBIA_TZ
from indicators.services.institution_energy import energia_horaria, irradiacion_diaria
from scada_proxy.models import (
    Device, DeviceCategory, Institution, InverterMeasurement, MeterMeasurement, WeatherStationMeasurement,
)

HUDN = '40a047f8-295a-4b8a-8d2c-649ddc18e600'
MARIANA = '0357e3a6-ebdd-45f2-bd1a-0c384c522df3'
UDENAR = '04abaa1c-9f61-4ae4-8b53-44f66cce93c6'
DIA = date(2025, 7, 15)


def _t(dia, hora, minuto=0):
    return COLOMBIA_TZ.localize(datetime(dia.year, dia.month, dia.day, hora, minuto))


class _Base(TestCase):
    def setUp(self):
        cache.clear()   # la energía por institución se guarda en caché por mes
        self.cat_inv = DeviceCategory.objects.create(scada_id='c-inv', name='inverter')
        self.cat_med = DeviceCategory.objects.create(scada_id='c-med', name='electricMeter')
        self.cat_est = DeviceCategory.objects.create(scada_id='c-est', name='weatherStation')

    def _institucion(self, scada_id, nombre):
        inst = Institution.objects.create(scada_id=scada_id, name=nombre)
        cfg = INSTITUCIONES[scada_id]
        devs = {}
        for sid in set(cfg['inversores_generacion']) | set(cfg['inversores_reconstruccion']):
            devs[sid] = Device.objects.create(name=f'inv {sid[:4]}', scada_id=sid, category=self.cat_inv,
                                              institution=inst)
        if cfg.get('respaldo_generacion'):
            sid = cfg['respaldo_generacion']['inversor']
            if sid not in devs:
                devs[sid] = Device.objects.create(name='respaldo', scada_id=sid, category=self.cat_inv,
                                                  institution=inst)
        devs[cfg['medidor_demanda']] = Device.objects.create(
            name='M1', scada_id=cfg['medidor_demanda'], category=self.cat_med, institution=inst)
        devs[cfg['estacion']] = Device.objects.create(
            name='estación', scada_id=cfg['estacion'], category=self.cat_est, institution=inst)
        return inst, devs

    @staticmethod
    def _serie(modelo, device, campo, dia, hora, valor, n=30):
        modelo.objects.bulk_create([
            modelo(device=device, date=_t(dia, hora) + timedelta(minutes=2 * i), **{campo: valor})
            for i in range(n)
        ])


class EnergiaHorariaTests(_Base):
    def test_medidor_bruto_todo_autoconsumo(self):
        inst, devs = self._institucion(HUDN, 'HUDN')
        cfg = INSTITUCIONES[HUDN]
        self._serie(InverterMeasurement, devs[cfg['inversores_generacion'][0]], 'acPower', DIA, 12, 6000.0)
        self._serie(MeterMeasurement, devs[cfg['medidor_demanda']], 'totalActivePower', DIA, 12, 9.0)
        h = next(x for x in energia_horaria(HUDN, DIA, DIA) if x['hora'].hour == 12)
        self.assertAlmostEqual(h['g_kwh'], 6.0)          # 30 × 6 kW × 2 min
        self.assertAlmostEqual(h['d_kwh'], 9.0)          # media de M1 × 1 h
        self.assertEqual(h['export_kwh'], 0.0)
        self.assertAlmostEqual(h['autoconsumo_kwh'], 6.0)

    def test_faltante_cero_en_generacion_y_hora_de_medidor_invalida(self):
        inst, devs = self._institucion(HUDN, 'HUDN')
        cfg = INSTITUCIONES[HUDN]
        self._serie(InverterMeasurement, devs[cfg['inversores_generacion'][0]], 'acPower', DIA, 12, 6000.0, n=10)
        self._serie(InverterMeasurement, devs[cfg['inversores_generacion'][0]], 'acPower', DIA, 13, 6000.0, n=20)
        self._serie(MeterMeasurement, devs[cfg['medidor_demanda']], 'totalActivePower', DIA, 12, 9.0, n=14)
        horas = {x['hora'].hour: x for x in energia_horaria(HUDN, DIA, DIA)}
        self.assertAlmostEqual(horas[12]['g_kwh'], 2.0)  # 10 < 15 lecturas: faltante = 0, no se repone
        self.assertAlmostEqual(horas[13]['g_kwh'], 6.0)  # 20 de 30: se reponen las perdidas con la media
        self.assertIsNone(horas[12]['d_kwh'])            # < 15 muestras: hora del medidor no válida

    def test_medidor_neto_reconstruye_demanda_y_mide_exportacion(self):
        inst, devs = self._institucion(MARIANA, 'Mariana')
        cfg = INSTITUCIONES[MARIANA]
        self._serie(InverterMeasurement, devs[cfg['inversores_generacion'][0]], 'acPower', DIA, 12, 12000.0)
        self._serie(MeterMeasurement, devs[cfg['medidor_demanda']], 'totalActivePower', DIA, 12, -4.0)
        h = next(x for x in energia_horaria(MARIANA, DIA, DIA) if x['hora'].hour == 12)
        self.assertAlmostEqual(h['g_kwh'], 12.0)
        self.assertAlmostEqual(h['d_kwh'], 8.0)          # −4 medidos + 12 de FV aguas abajo
        self.assertAlmostEqual(h['export_kwh'], 4.0)
        self.assertAlmostEqual(h['autoconsumo_kwh'], 8.0)

    def test_respaldo_cal44_y_retiro_de_inversores_en_udenar(self):
        inst, devs = self._institucion(UDENAR, 'Udenar')
        cfg = INSTITUCIONES[UDENAR]
        respaldo = cfg['respaldo_generacion']
        antes = date(2025, 8, 1)
        self._serie(InverterMeasurement, devs[respaldo['inversor']], 'acPower', antes, 12, 1000.0)
        h = next(x for x in energia_horaria(UDENAR, antes, antes) if x['hora'].hour == 12)
        self.assertAlmostEqual(h['g_kwh'], 1.0 * respaldo['factor'])
        # Tras el retiro (2026-04-11) el Fronius 1 ya no cuenta en la reconstrucción de D.
        despues = date(2026, 5, 4)
        self._serie(InverterMeasurement, devs[respaldo['inversor']], 'acPower', despues, 12, 5000.0)
        self._serie(MeterMeasurement, devs[cfg['medidor_demanda']], 'totalActivePower', despues, 12, 3.0)
        h = next(x for x in energia_horaria(UDENAR, despues, despues) if x['hora'].hour == 12)
        self.assertAlmostEqual(h['d_kwh'], 3.0)
        self.assertAlmostEqual(h['g_kwh'], 0.0)


class IrradiacionYPRTests(_Base):
    # El sesgo mensual de la estación se juzga con ≥ 5 días emparejados con la referencia: las estaciones se
    # cargan 5 días seguidos (DIA y los 4 siguientes); el inversor, solo DIA.
    DIAS_MES = [DIA + timedelta(days=i) for i in range(5)]

    def _referencia(self, wm2=500.0):
        """Estación de referencia (Alvernia, de Mariana) con 5 días completos."""
        inst = Institution.objects.create(scada_id=MARIANA, name='Mariana')
        est = Device.objects.create(name='Alvernia', scada_id=INSTITUCIONES[MARIANA]['estacion'],
                                    category=self.cat_est, institution=inst)
        for dia in self.DIAS_MES:
            for hora in range(6, 18):
                self._serie(WeatherStationMeasurement, est, 'irradiance', dia, hora, wm2)

    def _estacion(self, devs, cfg, wm2=500.0):
        for dia in self.DIAS_MES:
            for hora in range(6, 18):
                self._serie(WeatherStationMeasurement, devs[cfg['estacion']], 'irradiance', dia, hora, wm2)

    def _dia_soleado(self, devs, cfg, dia, wm2=500.0, gen_w=8000.0, ref_wm2=500.0):
        self._referencia(ref_wm2)
        self._estacion(devs, cfg, wm2)
        for hora in range(6, 18):
            self._serie(InverterMeasurement, devs[cfg['inversores_generacion'][0]], 'acPower', dia, hora, gen_w)

    def test_mes_con_pocos_dias_para_contrastar_no_cuenta(self):
        inst, devs = self._institucion(HUDN, 'HUDN')
        cfg = INSTITUCIONES[HUDN]
        self._referencia()
        for hora in range(6, 18):                           # la estación del HUDN solo tiene 1 día
            self._serie(WeatherStationMeasurement, devs[cfg['estacion']], 'irradiance', DIA, hora, 500.0)
            self._serie(InverterMeasurement, devs[cfg['inversores_generacion'][0]], 'acPower', DIA, hora, 8000.0)
        r = solar_kpis.calcular(inst, DIA, DIA, 'day')
        self.assertIsNone(r['total']['performance_ratio'])
        self.assertIn('para contrastar', r['total']['pr_motivo'])

    def test_mes_con_sesgo_sistematico_no_cuenta(self):
        inst, devs = self._institucion(HUDN, 'HUDN')
        self._dia_soleado(devs, INSTITUCIONES[HUDN], DIA, wm2=400.0, ref_wm2=500.0)   # −20 % todo el mes
        r = solar_kpis.calcular(inst, DIA, DIA, 'day')
        self.assertIsNone(r['total']['performance_ratio'])
        self.assertIn('sesgo', r['total']['pr_motivo'])

    def test_dia_que_difiere_de_la_referencia_no_cuenta(self):
        inst, devs = self._institucion(HUDN, 'HUDN')
        self._dia_soleado(devs, INSTITUCIONES[HUDN], DIA, wm2=500.0, ref_wm2=300.0)   # +67 % frente a Alvernia
        r = solar_kpis.calcular(inst, DIA, DIA, 'day')
        self.assertIsNone(r['total']['performance_ratio'])
        self.assertIn('referencia', r['total']['pr_motivo'])

    def test_pr_con_dia_valido(self):
        inst, devs = self._institucion(HUDN, 'HUDN')
        cfg = INSTITUCIONES[HUDN]
        self._dia_soleado(devs, cfg, DIA)
        irr = irradiacion_diaria(HUDN, DIA, DIA)
        self.assertAlmostEqual(irr[DIA]['h_kwh_m2'], 6.0)   # 12 h × 500 W/m²
        self.assertTrue(irr[DIA]['valido'])
        r = solar_kpis.calcular(inst, DIA, DIA, 'day')
        # E = 12 h × 8 kW = 96 kWh; referencia = 6 × 17,55 = 105,3 → PR 0,9117
        self.assertAlmostEqual(r['total']['performance_ratio'], 96.0 / (6.0 * 17.55), places=4)
        self.assertEqual(r['total']['pr_dias_validos'], 1)

    def test_dia_con_poca_cobertura_no_cuenta_en_pr(self):
        inst, devs = self._institucion(HUDN, 'HUDN')
        cfg = INSTITUCIONES[HUDN]
        for hora in range(6, 12):                           # medio día: 50 % de las muestras diurnas
            self._serie(WeatherStationMeasurement, devs[cfg['estacion']], 'irradiance', DIA, hora, 500.0)
        r = solar_kpis.calcular(inst, DIA, DIA, 'day')
        self.assertIsNone(r['total']['performance_ratio'])
        self.assertIn('cobertura diurna', r['total']['pr_motivo'])

    def test_dia_sin_datos_del_inversor_no_cuenta_en_pr(self):
        inst, devs = self._institucion(HUDN, 'HUDN')
        cfg = INSTITUCIONES[HUDN]
        self._referencia()
        self._estacion(devs, cfg)                           # estación completa, inversor sin datos
        r = solar_kpis.calcular(inst, DIA, DIA, 'day')
        self.assertIsNone(r['total']['performance_ratio'])
        self.assertIn('inversor sin lecturas', r['total']['pr_motivo'])

    def test_estacion_no_apta(self):
        inst, devs = self._institucion(UDENAR, 'Udenar')
        cfg = INSTITUCIONES[UDENAR]
        for hora in range(6, 18):
            self._serie(WeatherStationMeasurement, devs[cfg['estacion']], 'irradiance', DIA, hora, 500.0)
        r = solar_kpis.calcular(inst, DIA, DIA, 'day')
        self.assertIsNone(r['total']['performance_ratio'])
        self.assertIn('no apta', r['total']['pr_motivo'])


class IndicadoresTests(_Base):
    def test_totales_ahorro_co2_y_disponibilidad(self):
        inst, devs = self._institucion(HUDN, 'HUDN')
        cfg = INSTITUCIONES[HUDN]
        for hora in range(6, 18):
            self._serie(InverterMeasurement, devs[cfg['inversores_generacion'][0]], 'acPower', DIA, hora, 5000.0)
        for hora in range(24):
            self._serie(MeterMeasurement, devs[cfg['medidor_demanda']], 'totalActivePower', DIA, hora, 10.0)
        t = solar_kpis.calcular(inst, DIA, DIA, 'month')['total']
        self.assertAlmostEqual(t['generacion_kwh'], 60.0)
        self.assertAlmostEqual(t['demanda_kwh'], 240.0)
        self.assertAlmostEqual(t['cobertura_solar_pct'], 25.0)
        self.assertAlmostEqual(t['autoconsumo_pct'], 100.0)
        self.assertAlmostEqual(t['rendimiento_especifico_kwh_kwp'], 60.0 / 17.55)
        self.assertAlmostEqual(t['factor_capacidad'], 60.0 / (17.55 * 24))
        cu, extrapolada = solar_kpis.cu_del_mes(solar_kpis.cargar_tarifas()['asc'], '2025-07')
        self.assertFalse(extrapolada)
        self.assertAlmostEqual(t['ahorro_cop'], 60.0 * cu)
        self.assertAlmostEqual(t['co2_evitado_kg'], 60.0 * 0.112)
        self.assertAlmostEqual(t['disponibilidad_datos_pct'], 100.0)
        self.assertIsNone(t['eficiencia_inversor'])

    def test_institucion_sin_configuracion(self):
        inst = Institution.objects.create(scada_id='30636ba9-aa1c-4321-aa76-445afe8c5924', name='CEDENAR')
        with self.assertRaises(ValueError):
            solar_kpis.calcular(inst, DIA, DIA)


class TarifasTests(SimpleTestCase):
    def test_mes_sin_tarifa_usa_la_ultima_y_se_marca(self):
        asc = solar_kpis.cargar_tarifas()['asc']
        ultimo = max(asc)
        cu, extrapolada = solar_kpis.cu_del_mes(asc, '2099-01')
        self.assertEqual(cu, asc[ultimo])
        self.assertTrue(extrapolada)

    def test_hay_tarifas_de_los_dos_comercializadores(self):
        t = solar_kpis.cargar_tarifas()
        self.assertIn('asc', t)
        self.assertIn('cedenar', t)
        self.assertAlmostEqual(t['asc']['2025-04'], 734.3008)
        self.assertAlmostEqual(t['cedenar']['2025-04'], 794.62)


class EndpointTests(_Base):
    def setUp(self):
        cache.clear()   # la energía por institución se guarda en caché por mes
        super().setUp()
        self.inst, self.devs = self._institucion(HUDN, 'HUDN')
        self.client = APIClient()
        self.client.force_authenticate(User.objects.create_user('u', password='x'))

    def test_respuesta_y_validacion(self):
        url = '/api/solar-indicators/'
        r = self.client.get(url, {'institution_id': self.inst.id, 'start_date': '2025-07-01',
                                  'end_date': '2025-07-31', 'granularity': 'month'})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['periodos'][0]['periodo'], '2025-07')
        self.assertEqual(self.client.get(url, {'institution_id': self.inst.id, 'granularity': 'semana'}).status_code, 400)
        self.assertEqual(self.client.get(url, {'institution_id': 999999}).status_code, 404)
        self.assertEqual(self.client.get(url, {'institution_id': self.inst.id, 'start_date': '2025-08-01',
                                               'end_date': '2025-07-01'}).status_code, 400)

    def test_lista_de_instituciones(self):
        r = self.client.get('/api/solar-indicators/institutions/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual([x['name'] for x in r.json()], ['HUDN'])


class CacheEnergiaTests(_Base):
    def test_cache_por_mes_e_invalidacion_tras_lecturas_tardias(self):
        from indicators.services.institution_energy import invalidar_cache_energia
        inst, devs = self._institucion(HUDN, 'HUDN')
        inv = devs[INSTITUCIONES[HUDN]['inversores_generacion'][0]]
        self._serie(InverterMeasurement, inv, 'acPower', DIA, 12, 6000.0)
        total = lambda: sum(h['g_kwh'] for h in energia_horaria(HUDN, DIA, DIA))
        self.assertAlmostEqual(total(), 6.0)
        self._serie(InverterMeasurement, inv, 'acPower', DIA, 13, 6000.0)   # llega tarde
        self.assertAlmostEqual(total(), 6.0)                                # sigue la caché del mes
        invalidar_cache_energia(HUDN, DIA)                                  # lo hace la reconciliación
        self.assertAlmostEqual(total(), 12.0)
