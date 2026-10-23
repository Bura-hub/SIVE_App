"""
La energía de la pantalla Inversores (InverterIndicators, InverterChartData y HourlyInverterIndicators) es la misma
que la generación de Indicadores Solares (institution_energy.energia_horaria) para la misma planta, día y mes
(decisión del autor, oct-2026).

Las dos salen de institution_energy.energia_inversor_hora_kwh: por hora de Bogotá, max(Σ P, 0)·Δt, con reposición
de lecturas sueltas si la hora tiene 15–29 lecturas y «faltante = 0» con menos. Una hora sin lecturas aporta 0.
"""
from datetime import date, timedelta

from indicators.institution_config import INSTITUCIONES
from indicators.models import HourlyInverterIndicators, InverterChartData, InverterIndicators
from indicators.services import solar_kpis
from indicators.services.institution_energy import energia_horaria
from indicators.tasks import calculate_hourly_rollup, calculate_inverter_indicators
from scada_proxy.models import InverterMeasurement
from tests.test_solar_indicators import HUDN, _Base, _t

D0 = date(2025, 7, 15)
DIAS = [D0, D0 + timedelta(days=1)]


class EnergiaInversorIgualSolarTests(_Base):
    def setUp(self):
        super().setUp()
        self.inst, devs = self._institucion(HUDN, 'HUDN')
        self.inv = devs[INSTITUCIONES[HUDN]['inversores_generacion'][0]]
        g = lambda dia, hora, w, n=30: self._serie(InverterMeasurement, self.inv, 'acPower', dia, hora, w, n=n)
        # Día 1: horas completas, horas con 20 de 30 lecturas (se repone), con 10 (no repone) y noche con consumo.
        for hora in range(6, 18):
            n = 20 if hora in (9, 10) else 10 if hora in (6, 17) else 30
            g(DIAS[0], hora, 7000.0, n=n)
        g(DIAS[0], 2, -15.0)                       # consumo nocturno: max(Σ P, 0) = 0
        # Día 2: solo algunas horas (las demás, sin lecturas) y una con 15 lecturas exactas.
        g(DIAS[1], 11, 5000.0, n=15)
        g(DIAS[1], 12, 5000.0, n=29)
        g(DIAS[1], 13, 5000.0, n=14)
        # Lecturas en NULL: no cuentan como lectura.
        InverterMeasurement.objects.create(device=self.inv, date=_t(DIAS[1], 12, 59), acPower=None)

        e = 7000.0 * 2 / 60 / 1000                 # kWh por lectura
        self.dia1 = 8 * 30 * e + 2 * 30 * e + 2 * 10 * e
        e2 = 5000.0 * 2 / 60 / 1000
        self.dia2 = 30 * e2 + 30 * e2 + 14 * e2

    def _inversor(self, dia, time_range):
        calculate_inverter_indicators(self.inv.id, dia.isoformat(), time_range)
        fecha = dia if time_range == 'daily' else dia.replace(day=1)
        return InverterIndicators.objects.get(device=self.inv, date=fecha, time_range=time_range)

    def test_energia_diaria_coincide(self):
        solar = {p['periodo']: p for p in solar_kpis.calcular(self.inst, DIAS[0], DIAS[-1], 'day')['periodos']}
        for dia, esperado in zip(DIAS, (self.dia1, self.dia2)):
            inv = self._inversor(dia, 'daily')
            s = solar[dia.isoformat()]['generacion_kwh']
            self.assertAlmostEqual(s, esperado, places=9)
            self.assertAlmostEqual(inv.energy_ac_daily_kwh, s, places=9)
            self.assertAlmostEqual(inv.total_generated_energy_kwh, s, places=9)

    def test_energia_mensual_coincide(self):
        solar = solar_kpis.calcular(self.inst, date(2025, 7, 1), date(2025, 7, 31), 'month')['total']
        inv = self._inversor(date(2025, 7, 1), 'monthly')   # la corrida mensual se lanza con el día 1
        self.assertAlmostEqual(solar['generacion_kwh'], self.dia1 + self.dia2, places=9)
        self.assertAlmostEqual(inv.energy_ac_daily_kwh, solar['generacion_kwh'], places=9)
        self.assertAlmostEqual(inv.total_generated_energy_kwh, solar['generacion_kwh'], places=9)

    def test_grafica_del_dia_hora_a_hora_y_su_suma(self):
        for dia in DIAS:
            self._inversor(dia, 'daily')
            chart = InverterChartData.objects.get(device=self.inv, date=dia).hourly_generation
            solar = {h['hora'].hour: h for h in energia_horaria(HUDN, dia, dia)}
            for hora in range(24):
                if chart[hora] is None:                       # hora sin lecturas: ausente en la gráfica, 0 en Solares
                    self.assertEqual(solar[hora]['g_kwh'], 0.0, (dia, hora))
                    self.assertEqual(solar[hora]['n_g'], 0, (dia, hora))
                else:
                    self.assertAlmostEqual(chart[hora], solar[hora]['g_kwh'], places=9, msg=(dia, hora))
            total = InverterIndicators.objects.get(device=self.inv, date=dia, time_range='daily')
            self.assertAlmostEqual(sum(v for v in chart if v is not None), total.energy_ac_daily_kwh, places=9)

    def test_rollup_horario_coincide(self):
        dia = DIAS[0]
        calculate_hourly_rollup(start_hour_str=_t(dia, 0).isoformat(), end_hour_str=_t(dia, 23).isoformat(),
                                device_id=self.inv.scada_id)
        filas = {f.hour.astimezone(_t(dia, 0).tzinfo).hour: f
                 for f in HourlyInverterIndicators.objects.filter(device=self.inv)}
        for h in energia_horaria(HUDN, dia, dia):
            fila = filas.get(h['hora'].hour)
            if fila is None:
                self.assertEqual(h['n_g'], 0, h['hora'])
            else:
                self.assertAlmostEqual(fila.energy_ac_kwh, h['g_kwh'], places=9, msg=h['hora'])
        self.assertAlmostEqual(filas[9].energy_ac_kwh, 7.0)    # 20 de 30 lecturas: se repone a la hora completa
        self.assertAlmostEqual(filas[6].energy_ac_kwh, 7.0 / 3)  # 10 de 30: faltante = 0
        self.assertEqual(filas[2].energy_ac_kwh, 0.0)          # consumo nocturno: max(Σ P, 0)
