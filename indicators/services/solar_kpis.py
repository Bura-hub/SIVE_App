"""
Indicadores del sistema fotovoltaico de una institución (diseño, decisiones D3–D11).

Se calculan bajo demanda a partir de la energía horaria de `institution_energy`, sin tablas propias, para que
siempre reflejen las mediciones que haya en SIVE (incluidas las que llegaron tarde y se reconciliaron).
"""
import csv
import os
from collections import OrderedDict
from datetime import date, timedelta

from indicators.institution_config import (
    ARBOLES_POR_TONELADA_CO2, DISENO_IRRADIACION_KWH_M2_DIA, DISENO_KWH_DIA, DISENO_PERDIDAS,
    FACTOR_CO2_KG_KWH, config_institucion,
)
from indicators.services.formato import coma
from indicators.services.institution_energy import (
    HORA_FIN_DIA_SOLAR, HORA_INICIO_DIA_SOLAR, MUESTRAS_HORA, dias_pr, energia_diaria_para_pr, energia_horaria,
    irradiacion_diaria,
)

GRANULARIDADES = ('day', 'month', 'year')
_RUTA_TARIFAS = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'tarifas_cu.csv')

MOTIVO_EFICIENCIA = ('No disponible: el inversor solo reporta la potencia DC de una entrada MPPT '
                     '(dcPower ≈ 0,55 × acPower), así que P_AC/P_DC no mide la eficiencia.')


def cargar_tarifas():
    """{comercializador: {'YYYY-MM': cu_cop_kwh}} desde indicators/data/tarifas_cu.csv."""
    tarifas = {}
    with open(_RUTA_TARIFAS, encoding='utf-8') as f:
        lineas = (l for l in f if not l.startswith('#'))
        for fila in csv.DictReader(lineas):
            tarifas.setdefault(fila['comercializador'], {})[fila['mes']] = float(fila['cu_cop_kwh'])
    return tarifas


def cu_del_mes(tarifas_com, mes):
    """(cu, extrapolada). Si el mes no tiene tarifa publicada se usa la última anterior; si no hay anterior, la
    primera posterior. Ambas se marcan como extrapoladas."""
    if mes in tarifas_com:
        return tarifas_com[mes], False
    anteriores = sorted(m for m in tarifas_com if m < mes)
    if anteriores:
        return tarifas_com[anteriores[-1]], True
    return tarifas_com[min(tarifas_com)], True


def _clave(dia, granularidad):
    if granularidad == 'day':
        return dia.isoformat()
    if granularidad == 'month':
        return dia.strftime('%Y-%m')
    return str(dia.year)


def _div(a, b):
    return (a / b) if (a is not None and b) else None


def _pct(a, b):
    v = _div(a, b)
    return v * 100.0 if v is not None else None


def _nuevo_acumulador():
    return {
        'dias': set(), 'horas': 0, 'horas_diurnas': 0, 'horas_diurnas_con_dato': 0, 'muestras_g_diurnas': 0,
        'g': 0.0, 'g_horas_con_d': 0.0, 'd': 0.0, 'horas_d': 0, 'pico_d': None,
        'export': 0.0, 'autoconsumo': 0.0, 'g_sin_medidor': 0.0, 'ahorro': 0.0, 'tarifa_extrapolada': False,
        'pr_e': 0.0, 'pr_ref': 0.0, 'pr_dias': 0, 'h_suma': 0.0, 'h_dias': 0, 'pr_motivos': set(),
    }


def calcular(institution, start_date, end_date, granularidad='month'):
    """Indicadores por periodo y totales del rango para una `scada_proxy.Institution`."""
    if granularidad not in GRANULARIDADES:
        raise ValueError(f'granularidad debe ser una de {GRANULARIDADES}')
    cfg = config_institucion(institution.scada_id)
    if cfg is None:
        raise ValueError(f'«{institution.name}» no tiene sistema fotovoltaico configurado en SIVE.')
    kwp = cfg['kwp']
    tarifas = cargar_tarifas().get(cfg['comercializador'], {})
    if not tarifas:
        raise ValueError(f'No hay tarifas del comercializador «{cfg["comercializador"]}».')

    horas = energia_horaria(institution.scada_id, start_date, end_date)
    irr = irradiacion_diaria(institution.scada_id, start_date, end_date)

    # PR: la clasificación de días es la de institution_energy.dias_pr, la misma que usa el PR de la pantalla
    # Inversores (cobertura y validez de la estación, contraste con la de referencia y cobertura del inversor).
    energia_dia = energia_diaria_para_pr(horas)

    periodos = OrderedDict()
    total = _nuevo_acumulador()
    for h in horas:
        dia = h['hora'].date()
        cu, extrapolada = cu_del_mes(tarifas, dia.strftime('%Y-%m'))
        for acc in (periodos.setdefault(_clave(dia, granularidad), _nuevo_acumulador()), total):
            acc['dias'].add(dia)
            acc['horas'] += 1
            acc['g'] += h['g_kwh']
            if HORA_INICIO_DIA_SOLAR <= h['hora'].hour < HORA_FIN_DIA_SOLAR:
                acc['horas_diurnas'] += 1
                acc['muestras_g_diurnas'] += h['n_g']
                if h['n_g'] > 0:
                    acc['horas_diurnas_con_dato'] += 1
            if h['d_kwh'] is not None:
                acc['d'] += h['d_kwh']
                acc['horas_d'] += 1
                acc['g_horas_con_d'] += h['g_kwh']
                acc['pico_d'] = h['d_kwh'] if acc['pico_d'] is None else max(acc['pico_d'], h['d_kwh'])
                acc['export'] += h['export_kwh']
                acc['autoconsumo'] += h['autoconsumo_kwh']
                acc['ahorro'] += h['autoconsumo_kwh'] * cu
            else:
                # Sin medidor en la hora no se sabe cuánto se exportó: se cuenta aparte y no entra al ahorro.
                acc['g_sin_medidor'] += h['g_kwh']
            acc['tarifa_extrapolada'] |= extrapolada

    for dia, e, h_dia, motivo in dias_pr(energia_dia, irr):
        for acc in ([periodos[_clave(dia, granularidad)]] if _clave(dia, granularidad) in periodos else []) + [total]:
            if motivo:
                acc['pr_motivos'].add(motivo)
            else:
                acc['pr_e'] += e
                acc['pr_ref'] += h_dia * kwp
                acc['pr_dias'] += 1
                acc['h_suma'] += h_dia
                acc['h_dias'] += 1

    acumulada = 0.0
    filas = []
    for clave, acc in periodos.items():
        acumulada += acc['g']
        filas.append(_resumen(clave, acc, kwp, acumulada, cfg))
    resumen_total = _resumen('total', total, kwp, acumulada, cfg)

    cus = [cu_del_mes(tarifas, m) for m in sorted({d.strftime('%Y-%m') for d in total['dias']})]
    return {
        'institucion': {'id': institution.id, 'nombre': institution.name, 'scada_id': institution.scada_id},
        'rango': {'desde': start_date.isoformat(), 'hasta': end_date.isoformat(), 'granularidad': granularidad},
        'periodos': filas,
        'total': resumen_total,
        'parametros': {
            'kwp': kwp,
            'diseno_kwh_dia': DISENO_KWH_DIA,
            'diseno_irradiacion_kwh_m2_dia': DISENO_IRRADIACION_KWH_M2_DIA,
            'diseno_perdidas': DISENO_PERDIDAS,
            'factor_co2_kg_kwh': FACTOR_CO2_KG_KWH,
            'arboles_por_tonelada_co2': ARBOLES_POR_TONELADA_CO2,
            'comercializador': cfg['comercializador'],
            'tipo_medidor': cfg['tipo_medidor'],
            'cu_medio_cop_kwh': (sum(c for c, _ in cus) / len(cus)) if cus else None,
        },
        'supuestos': _supuestos(cfg),
    }


def _resumen(clave, acc, kwp, acumulada, cfg):
    dias = len(acc['dias'])
    disponibilidad = _pct(acc['horas_diurnas_con_dato'], acc['horas_diurnas'])
    return {
        'periodo': clave,
        'dias': dias,
        'generacion_kwh': acc['g'],
        'generacion_acumulada_kwh': acumulada,
        'rendimiento_especifico_kwh_kwp': acc['g'] / kwp,
        'factor_capacidad': _div(acc['g'], kwp * acc['horas']),
        'diseno_kwh': DISENO_KWH_DIA * dias,
        'produccion_vs_diseno_pct': _pct(acc['g'], DISENO_KWH_DIA * dias),
        'performance_ratio': _div(acc['pr_e'], acc['pr_ref']),
        'pr_dias_validos': acc['pr_dias'],
        'pr_motivo': (None if acc['pr_dias'] else
                      ('; '.join(sorted(m for m in acc['pr_motivos'] if m)) or 'sin datos de la estación')),
        'irradiacion_media_kwh_m2_dia': _div(acc['h_suma'], acc['h_dias']),
        'eficiencia_inversor': None,
        'eficiencia_inversor_motivo': MOTIVO_EFICIENCIA,
        'demanda_kwh': acc['d'] if acc['horas_d'] else None,
        'demanda_media_kw': _div(acc['d'], acc['horas_d']),
        'demanda_pico_horaria_kw': acc['pico_d'],
        'horas_con_medidor': acc['horas_d'],
        'cobertura_solar_pct': _pct(acc['g_horas_con_d'], acc['d']),
        'autoconsumo_kwh': acc['autoconsumo'] if acc['horas_d'] else None,
        'autoconsumo_pct': _pct(acc['autoconsumo'], acc['g_horas_con_d']),
        'exportada_kwh': acc['export'] if acc['horas_d'] else None,
        'generacion_sin_medidor_kwh': acc['g_sin_medidor'],
        'ahorro_cop': acc['ahorro'] if acc['horas_d'] else None,
        'tarifa_extrapolada': acc['tarifa_extrapolada'],
        'co2_evitado_kg': acc['g'] * FACTOR_CO2_KG_KWH,
        'arboles_equivalentes': acc['g'] * FACTOR_CO2_KG_KWH / 1000.0 * ARBOLES_POR_TONELADA_CO2,
        'disponibilidad_datos_pct': disponibilidad,
        'cobertura_muestras_pct': _pct(acc['muestras_g_diurnas'], acc['horas_diurnas'] * MUESTRAS_HORA),
    }


def _supuestos(cfg):
    s = [
        f'Capacidad instalada: {coma(cfg["kwp"])} kWp (30 módulos de 585 Wp).',
        'Energía de cada hora = Σ potencia × 2 min. Si la hora tiene al menos 15 de sus 30 lecturas, las que faltan '
        'se reponen con la media de las presentes; con menos (amanecer, caídas de datos) no se repone nada. La '
        'disponibilidad y la cobertura de lecturas dicen cuánto falta.',
        'Demanda: circuito medido por el Medidor 1 de la institución, no el consumo total de la institución.',
        'Performance Ratio con la irradiancia de la estación meteorológica de la institución, medida en plano '
        'horizontal (no en el plano de los módulos). Solo cuentan los días con ≥ 80 % de lecturas diurnas de la '
        'estación y del inversor, y cuya irradiación queda a ±25 % de la de la estación de referencia (Alvernia).',
        MOTIVO_EFICIENCIA,
        f'Ahorro = energía autoconsumida × CU mensual de {cfg["comercializador"].upper()} (nivel de tensión 2, sin '
        'contribución). Los meses sin tarifa publicada usan la última disponible (marcados como extrapolados).',
        f'CO₂ evitado = generación × {coma(FACTOR_CO2_KG_KWH)} kgCO₂/kWh (factor del SIN, UPME Res. 0705/2024); '
        'árboles: 545 por cada 12 t (Informe Técnico 2).',
        f'Producción esperada según el diseño: {coma(DISENO_KWH_DIA)} kWh/día por sistema '
        f'({coma(DISENO_IRRADIACION_KWH_M2_DIA)} kWh/m²/día de irradiación y {int(DISENO_PERDIDAS * 100)} % de pérdidas; '
        'Informe Técnico 2). «Frente a lo esperado» = generación / producción esperada.',
    ]
    if cfg['tipo_medidor'] == 'gross':
        s.append('El Medidor 1 mide la carga del circuito donde se inyecta la FV: toda la generación se consume en '
                 'sitio (autoconsumo 100 %, exportación 0) mientras el medidor marque importación.')
    else:
        s.append('Exportación: horas en que el Medidor 1 (en el punto de conexión) marca potencia negativa; '
                 'demanda = medida + generación aguas abajo.')
    return s


def rango_por_defecto(hoy):
    return date(2025, 4, 4), hoy


def validar_rango(start_date, end_date, max_dias=800):
    if start_date > end_date:
        raise ValueError('start_date debe ser anterior o igual a end_date.')
    if (end_date - start_date) > timedelta(days=max_dias):
        raise ValueError(f'El rango no puede superar {max_dias} días.')
