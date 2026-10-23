"""
Indicadores de inversor, corrección de octubre de 2026 (frecuencia, FP, PR, gráfica horaria y hora de Bogotá).
"""
from datetime import date, datetime, timedelta

import pytz
from django.test import SimpleTestCase, TestCase

from indicators.models import InverterChartData, InverterIndicators
from indicators.services.date_ranges import COLOMBIA_TZ
from indicators.services.inverter_calc import (
    INVERTER_FIELDS,
    PR_REASON_NO_PLANT,
    PR_REASON_NO_VALID_DAYS,
    compute_inverter_hourly_chart,
    compute_inverter_indicators,
    compute_performance_ratio,
)
from indicators.services.institution_energy import energia_diaria_para_pr, horas_inversor
from indicators.services.weather_calc import daily_irradiation_for_pr
from indicators.tasks import calculate_inverter_indicators
from scada_proxy.models import (
    Device, DeviceCategory, Institution, InverterMeasurement, WeatherStationMeasurement,
)

HUDN = '40a047f8-295a-4b8a-8d2c-649ddc18e600'
HUDN_INV = 'f6893ba9-7175-44ea-8624-a47bf55158c9'
HUDN_EST = '49435c0b-ada3-4ced-ad15-9418013a30d1'
UDENAR = '04abaa1c-9f61-4ae4-8b53-44f66cce93c6'
UDENAR_INV = 'c03a5f4a-f78e-47d7-8818-b50544b3f531'


def _bog(y, m, d, h, mi=0):
    return COLOMBIA_TZ.localize(datetime(y, m, d, h, mi))


def _row(**kw):
    row = {f: None for f in INVERTER_FIELDS}
    row['date'] = _bog(2025, 7, 1, 12)   # la energía se agrupa por hora
    row.update(kw)
    return row


class FrecuenciaYFactorDePotenciaTests(SimpleTestCase):
    """Frecuencia solo generando y FP como media de |FP|/100."""

    def setUp(self):
        # Noche: 0 Hz, acPower 0, FP 0. Día: 60 Hz, FP −98 % y +96 %.
        self.rows = (
            [_row(acPower=0.0, acFrequency=0.0, powerFactor=0.0)] * 10
            + [_row(acPower=5000.0, acFrequency=59.98, powerFactor=-98.0)] * 5
            + [_row(acPower=6000.0, acFrequency=60.02, powerFactor=96.0)] * 5
        )

    def test_frecuencia_solo_mientras_genera(self):
        r = compute_inverter_indicators(self.rows)
        # Antes: (10×0 + 5×59,98 + 5×60,02)/20 = 30,0 Hz.
        self.assertAlmostEqual(r['avg_frequency_hz'], 60.0)

    def test_estabilidad_no_salta_por_la_noche(self):
        r = compute_inverter_indicators(self.rows)
        self.assertGreater(r['frequency_stability_pct'], 99.9)
        self.assertNotIn('frequency_instability', r['anomaly_details'])

    def test_factor_de_potencia_es_media_de_abs_entre_100_mientras_genera(self):
        r = compute_inverter_indicators(self.rows)
        # Antes: media cruda con signo y con las noches = (5×−98 + 5×96)/20 = −0,5.
        self.assertAlmostEqual(r['avg_power_factor'], 0.97)
        self.assertNotIn('avg_power_factor_pct', r)

    def test_sin_generacion_no_hay_frecuencia_ni_fp(self):
        r = compute_inverter_indicators([_row(acPower=0.0, acFrequency=0.0, powerFactor=0.0)] * 3)
        self.assertIsNone(r['avg_frequency_hz'])
        self.assertIsNone(r['frequency_stability_pct'])
        self.assertIsNone(r['avg_power_factor'])

    def test_eficiencia_e_irradiancia_no_disponibles(self):
        r = compute_inverter_indicators(self.rows)
        self.assertIsNone(r['dc_ac_efficiency_pct'])
        self.assertIsNone(r['avg_irradiance_wm2'])
        self.assertIsNone(r['avg_temperature_c'])
        self.assertIsNone(r['performance_ratio_pct'])


class IrradiacionParaPRTests(SimpleTestCase):
    """H = Σ irradiancia de 06–18 h en [0, 1400] × 2/60 / 1000; día válido con ≥ 288
    muestras diurnas (80 % de 360) y 0 < H ≤ 8 kWh/m²."""

    def _dia(self, n, valor, y=2025, m=7, d=1):
        start = _bog(y, m, d, 6)
        return [{'date': start + timedelta(minutes=2 * i), 'irradiance': valor} for i in range(n)]

    def test_dia_completo(self):
        rows = self._dia(360, 500.0)
        # Lecturas nocturnas y fuera de rango no cuentan.
        rows += [{'date': _bog(2025, 7, 1, 20), 'irradiance': 900.0},
                 {'date': _bog(2025, 7, 1, 12, 1), 'irradiance': 1500.0}]
        h, ok = daily_irradiation_for_pr(rows)[date(2025, 7, 1)]
        self.assertAlmostEqual(h, 360 * 500 * 2 / 60 / 1000)  # 6 kWh/m²
        self.assertTrue(ok)

    def test_cobertura_insuficiente(self):
        h, ok = daily_irradiation_for_pr(self._dia(287, 500.0))[date(2025, 7, 1)]
        self.assertFalse(ok)

    def test_h_mayor_que_8_no_es_valido(self):
        h, ok = daily_irradiation_for_pr(self._dia(360, 700.0))[date(2025, 7, 1)]
        self.assertAlmostEqual(h, 8.4)
        self.assertFalse(ok)

    def test_dia_en_hora_de_bogota(self):
        # 06:00 Bogotá = 11:00 UTC; las filas de Django vienen en UTC.
        rows = [{'date': r['date'].astimezone(pytz.utc), 'irradiance': r['irradiance']}
                for r in self._dia(360, 500.0)]
        self.assertEqual(list(daily_irradiation_for_pr(rows)), [date(2025, 7, 1)])


def _irr(h, valido=True, motivo=None):
    return {'h_kwh_m2': h, 'muestras': 360, 'valido': valido, 'motivo': motivo}


class PerformanceRatioPuroTests(SimpleTestCase):
    """PR del inversor con las reglas de «Indicadores Solares» (institution_energy.dias_pr)."""

    def test_pr_mensual_es_suma_de_e_entre_suma_de_referencia(self):
        energy = {date(2025, 7, 1): (70.0, 12), date(2025, 7, 2): (50.0, 10), date(2025, 7, 3): (99.0, 12)}
        irr = {date(2025, 7, 1): _irr(5.0), date(2025, 7, 2): _irr(4.0),
               date(2025, 7, 3): _irr(6.0, False, 'cobertura diurna 100/360 muestras')}
        r = compute_performance_ratio(energy, irr, 17.55)
        self.assertAlmostEqual(r['performance_ratio_pct'], 120.0 / (9.0 * 17.55) * 100)
        self.assertAlmostEqual(r['reference_energy_kwh'], 9.0 * 17.55)
        self.assertEqual(r['performance_ratio_valid_days'], 2)
        self.assertIsNone(r['performance_ratio_note'])

    def test_dia_con_inversor_en_menos_del_80_por_ciento_de_las_horas_de_sol_no_cuenta(self):
        # 9 de 12 horas de sol con lectura: 75 % < 80 % (regla de ee0d286).
        energy = {date(2025, 7, 1): (70.0, 12), date(2025, 7, 2): (30.0, 9)}
        irr = {date(2025, 7, 1): _irr(5.0), date(2025, 7, 2): _irr(5.0)}
        r = compute_performance_ratio(energy, irr, 17.55)
        self.assertEqual(r['performance_ratio_valid_days'], 1)
        self.assertAlmostEqual(r['performance_ratio_pct'], 70.0 / (5.0 * 17.55) * 100)

    def test_sin_dias_validos_es_null_con_motivo(self):
        r = compute_performance_ratio({date(2025, 7, 1): (70.0, 12)},
                                      {date(2025, 7, 1): _irr(5.0, False, 'x')}, 17.55)
        self.assertIsNone(r['performance_ratio_pct'])
        self.assertEqual(r['performance_ratio_note'], PR_REASON_NO_VALID_DAYS)

    def test_motivo_menciona_la_referencia_y_la_cobertura_del_inversor_y_cabe_en_la_columna(self):
        self.assertIn('referencia (Alvernia)', PR_REASON_NO_VALID_DAYS)
        self.assertIn('lecturas del inversor', PR_REASON_NO_VALID_DAYS)
        self.assertLessEqual(len(PR_REASON_NO_VALID_DAYS), 255)   # InverterIndicators.performance_ratio_note

    def test_energia_horaria_y_diaria_en_hora_de_bogota(self):
        rows = [{'date': _bog(2025, 7, 1, 23, 58).astimezone(pytz.utc), 'acPower': 3000.0},
                {'date': _bog(2025, 7, 2, 0, 0), 'acPower': 6000.0},
                {'date': _bog(2025, 7, 2, 0, 2), 'acPower': None}]
        e = energia_diaria_para_pr(horas_inversor(rows))
        self.assertAlmostEqual(e[date(2025, 7, 1)][0], 0.1)
        self.assertAlmostEqual(e[date(2025, 7, 2)][0], 0.2)
        self.assertEqual(e[date(2025, 7, 2)][1], 0)            # 00:00 no es hora de sol

    def test_reposicion_c21_con_15_o_mas_lecturas(self):
        start = _bog(2025, 7, 1, 10)
        rows = [{'date': start + timedelta(minutes=2 * i), 'acPower': 6000.0} for i in range(20)]
        rows += [{'date': _bog(2025, 7, 1, 11) + timedelta(minutes=2 * i), 'acPower': 6000.0} for i in range(10)]
        horas = {h['hora'].hour: h for h in horas_inversor(rows)}
        self.assertAlmostEqual(horas[10]['g_kwh'], 6.0)   # 20 de 30: se repone a la hora completa
        self.assertAlmostEqual(horas[11]['g_kwh'], 2.0)   # 10 de 30: faltante = 0


class GraficaHorariaTests(SimpleTestCase):
    """Gráfica horaria: energía por hora en hora de Bogotá."""

    def test_generacion_horaria_es_la_energia_de_la_hora_en_hora_de_bogota(self):
        start = _bog(2025, 7, 1, 10)
        rows = [{'date': start + timedelta(minutes=2 * i), 'acPower': 6000.0, 'dcPower': 3300.0}
                for i in range(30)]
        chart = compute_inverter_hourly_chart(rows)
        # 30 muestras × 6000 W × 2/60 h = 6 kWh. Antes: media 6000 × 2/60 / 1000 = 0,2 kWh, en la hora 15 (UTC).
        self.assertAlmostEqual(chart['hourly_generation'][10], 6.0)
        self.assertAlmostEqual(chart['hourly_ac_power'][10], 6000.0)
        self.assertIsNone(chart['hourly_generation'][15])
        self.assertEqual(chart['hourly_efficiency'], [None] * 24)


class PerformanceRatioTareaTests(TestCase):
    """PR de la tarea con la estación de la institución (institution_config)."""

    def setUp(self):
        inv_cat = DeviceCategory.objects.create(scada_id='C_INV', name='inverter')
        ws_cat = DeviceCategory.objects.create(scada_id='C_WS', name='weatherStation')
        self.hudn = Institution.objects.create(scada_id=HUDN, name='HUDN')
        self.inv = Device.objects.create(name='Inversor 1 - HUDN', scada_id=HUDN_INV,
                                         category=inv_cat, institution=self.hudn)
        self.est = Device.objects.create(name='Estación - HUDN', scada_id=HUDN_EST,
                                         category=ws_cat, institution=self.hudn)
        self.udenar = Institution.objects.create(scada_id=UDENAR, name='Udenar')
        self.inv_udenar = Device.objects.create(name='Inversor MTE', scada_id=UDENAR_INV,
                                                category=inv_cat, institution=self.udenar)
        self.otro = Device.objects.create(name='Prueba', scada_id='otro-inversor',
                                          category=inv_cat, institution=self.hudn)
        self.dia = date(2025, 7, 1)
        # 12 h con 6000 W en el inversor (E = 360 × 6000 × 2/60 / 1000 = 72 kWh) y 500 W/m² en la
        # estación (H = 6 kWh/m²): PR = 72 / (6 × 17,55) = 68,4 %.
        start = _bog(2025, 7, 1, 6)
        for dev in (self.inv, self.inv_udenar, self.otro):
            InverterMeasurement.objects.bulk_create([
                InverterMeasurement(device=dev, date=start + timedelta(minutes=2 * i), acPower=6000.0,
                                    acFrequency=60.0, powerFactor=-99.0)
                for i in range(360)])
        # Estaciones con 5 días (el sesgo mensual frente a la referencia se juzga con ≥ 5 días emparejados).
        WeatherStationMeasurement.objects.bulk_create([
            WeatherStationMeasurement(device=self.est, date=start + timedelta(days=d, minutes=2 * i), irradiance=500.0)
            for d in range(5) for i in range(360)])
        # Estación de referencia (Alvernia): el PR solo cuenta días que coinciden con ella a ±25 %.
        from django.core.cache import cache
        from indicators.institution_config import INSTITUCION_REFERENCIA_PR, INSTITUCIONES
        cache.clear()
        mariana = Institution.objects.create(scada_id=INSTITUCION_REFERENCIA_PR, name='Mariana')
        alvernia = Device.objects.create(name='Estación Alvernia', category=ws_cat, institution=mariana,
                                         scada_id=INSTITUCIONES[INSTITUCION_REFERENCIA_PR]['estacion'])
        WeatherStationMeasurement.objects.bulk_create([
            WeatherStationMeasurement(device=alvernia, date=start + timedelta(days=d, minutes=2 * i), irradiance=480.0)
            for d in range(5) for i in range(360)])

    def _ind(self, dev, time_range='daily'):
        calculate_inverter_indicators(dev.id, self.dia.isoformat(), time_range)
        fecha = self.dia if time_range == 'daily' else self.dia.replace(day=1)
        return InverterIndicators.objects.get(device=dev, date=fecha, time_range=time_range)

    def test_pr_diario_del_hudn(self):
        ind = self._ind(self.inv)
        self.assertAlmostEqual(ind.performance_ratio_pct, 72.0 / (6.0 * 17.55) * 100)
        self.assertEqual(ind.performance_ratio_valid_days, 1)
        self.assertAlmostEqual(ind.avg_power_factor, 0.99)
        self.assertAlmostEqual(ind.avg_frequency_hz, 60.0)

    def test_pr_mensual_del_hudn(self):
        ind = self._ind(self.inv, 'monthly')
        self.assertAlmostEqual(ind.performance_ratio_pct, 72.0 / (6.0 * 17.55) * 100)
        self.assertEqual(ind.performance_ratio_valid_days, 1)

    def test_udenar_estacion_no_apta(self):
        ind = self._ind(self.inv_udenar)
        self.assertIsNone(ind.performance_ratio_pct)
        self.assertIn('no es apta', ind.performance_ratio_note)

    def test_inversor_sin_planta(self):
        ind = self._ind(self.otro)
        self.assertIsNone(ind.performance_ratio_pct)
        self.assertEqual(ind.performance_ratio_note, PR_REASON_NO_PLANT)

    def test_mensual_no_pisa_la_grafica_del_dia_1(self):
        self._ind(self.inv)
        diaria = InverterChartData.objects.get(device=self.inv, date=self.dia).hourly_generation
        self._ind(self.inv, 'monthly')
        self.assertEqual(InverterChartData.objects.get(device=self.inv, date=self.dia).hourly_generation, diaria)
        # 30 muestras × 6000 W × 2/60 h = 6 kWh por hora, de 06 a 17 h de Bogotá.
        self.assertAlmostEqual(diaria[6], 6.0)
        self.assertIsNone(diaria[5])
