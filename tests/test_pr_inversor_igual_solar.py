"""
El PR de la pantalla Inversores (InverterIndicators, tarea calculate_inverter_indicators) es el mismo que el de
Indicadores Solares (solar_kpis.calcular) para la misma planta y el mismo rango (decisión del autor, oct-2026).

Las dos rutas usan institution_energy.dias_pr: estación válida (cobertura, tope físico y contraste con la estación
de referencia), inversor con lecturas en ≥ 80 % de las horas de sol (ee0d286) y energía horaria con reposición
de lecturas sueltas en horas con ≥ 15 de 30 lecturas.
"""
from datetime import date, timedelta

from indicators.institution_config import INSTITUCIONES, KWP_POR_PLANTA
from indicators.models import InverterIndicators
from indicators.services import solar_kpis
from indicators.services.inverter_calc import PR_REASON_NO_VALID_DAYS
from indicators.tasks import calculate_inverter_indicators
from scada_proxy.models import Device, Institution, InverterMeasurement, WeatherStationMeasurement
from tests.test_solar_indicators import HUDN, MARIANA, _Base

D0 = date(2025, 7, 15)
DIAS = [D0 + timedelta(days=i) for i in range(5)]
REF = 6.0 * KWP_POR_PLANTA        # 12 h × 500 W/m² = 6 kWh/m² por día


class PRInversorIgualSolarTests(_Base):
    def setUp(self):
        super().setUp()
        self.inst, devs = self._institucion(HUDN, 'HUDN')
        cfg = INSTITUCIONES[HUDN]
        self.inv = devs[cfg['inversores_generacion'][0]]
        est = devs[cfg['estacion']]
        mariana = Institution.objects.create(scada_id=MARIANA, name='Mariana')
        alvernia = Device.objects.create(name='Alvernia', scada_id=INSTITUCIONES[MARIANA]['estacion'],
                                         category=self.cat_est, institution=mariana)
        for i, dia in enumerate(DIAS):
            for hora in range(6, 18):
                self._serie(WeatherStationMeasurement, alvernia, 'irradiance', dia, hora, 500.0)
                # Día 3: la estación del HUDN marca 300 W/m², −40 % frente a Alvernia: no cuenta.
                self._serie(WeatherStationMeasurement, est, 'irradiance', dia, hora, 300.0 if i == 3 else 500.0)
        g = lambda dia, hora, w, n=30: self._serie(InverterMeasurement, self.inv, 'acPower', dia, hora, w, n=n)
        for hora in range(6, 18):
            g(DIAS[0], hora, 8000.0)                       # 96 kWh, día completo
            g(DIAS[1], hora, 8000.0, n=20)                 # 20 de 30 lecturas por hora: se repone → 96 kWh
            if hora < 15:
                g(DIAS[2], hora, 8000.0)                   # 9 de 12 horas de sol (75 %): no cuenta
            g(DIAS[3], hora, 8000.0)                       # la estación no coincide con la referencia
            g(DIAS[4], hora, 6000.0, n=10 if hora in (6, 17) else 30)   # 10 h × 6 + 2 h × 2 (sin reponer) = 64
        self.pr_esperado = (96.0 + 96.0 + 64.0) / (3 * REF)

    def _inversor(self, dia, time_range):
        calculate_inverter_indicators(self.inv.id, dia.isoformat(), time_range)
        fecha = dia if time_range == 'daily' else dia.replace(day=1)
        return InverterIndicators.objects.get(device=self.inv, date=fecha, time_range=time_range)

    def test_pr_mensual_coincide(self):
        solar = solar_kpis.calcular(self.inst, date(2025, 7, 1), date(2025, 7, 31), 'month')['total']
        inv = self._inversor(date(2025, 7, 1), 'monthly')   # la corrida mensual se lanza con el día 1
        self.assertAlmostEqual(solar['performance_ratio'], self.pr_esperado, places=9)
        self.assertAlmostEqual(inv.performance_ratio_pct, solar['performance_ratio'] * 100.0, places=9)
        self.assertEqual(inv.performance_ratio_valid_days, solar['pr_dias_validos'])
        self.assertEqual(inv.performance_ratio_valid_days, 3)

    def test_pr_diario_coincide_dia_a_dia(self):
        solar = {p['periodo']: p for p in solar_kpis.calcular(self.inst, DIAS[0], DIAS[-1], 'day')['periodos']}
        for dia in DIAS:
            s = solar[dia.isoformat()]
            inv = self._inversor(dia, 'daily')
            if s['performance_ratio'] is None:
                self.assertIsNone(inv.performance_ratio_pct, dia)
                self.assertEqual(inv.performance_ratio_note, PR_REASON_NO_VALID_DAYS, dia)
            else:
                self.assertAlmostEqual(inv.performance_ratio_pct, s['performance_ratio'] * 100.0, places=9)
            self.assertEqual(inv.performance_ratio_valid_days, s['pr_dias_validos'], dia)
        self.assertIn('inversor sin lecturas', solar[DIAS[2].isoformat()]['pr_motivo'])
        self.assertIn('referencia', solar[DIAS[3].isoformat()]['pr_motivo'])
