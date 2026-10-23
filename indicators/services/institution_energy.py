"""
Energía horaria por institución con la misma convención que el mercado P2P.

- G (generación): Σ acPower de los inversores de generación vigentes, en kWh por hora (Δt nominal de 2 min).
  Si la hora tiene ≥ 15 de 30 lecturas, las que faltan se reponen con la media de las presentes (Σ P·Δt × 30/n);
  con menos de 15 (amanecer, atardecer, caídas) rige «faltante = 0», como el mercado P2P. Así una RPi
  que pierde lecturas sueltas (HUDN perdió hasta un 25 % en sep-2026) no se lee como menos generación: con
  «faltante = 0» puro, sep-2026 salía −25 % frente a Solar.web; reponiendo, −16 % (ese mes muchas horas tienen
  menos de 15 lecturas y no se reponen); may–nov 2025 queda a +0,1 %.
- D (demanda del circuito medido): media de totalActivePower del medidor principal (M1) en la hora × 1 h, válida solo
  si la hora tiene ≥ 15 de 30 muestras (como el motor del mercado). En medidores netos se reconstruye
  D = max(0, P_M1 + Σ inversores aguas abajo).
- Exportación: en medidores netos, la parte negativa de P_M1 en la hora. En medidores brutos no se puede medir
  (la FV entra al circuito medido) y se toma 0: todo lo generado se autoconsume.

Unidades: totalActivePower del medidor en kW; acPower del inversor en W.
"""
from collections import defaultdict
from datetime import datetime, timedelta

from django.db.models import Count, Sum
from django.db.models.functions import TruncHour

from indicators.institution_config import config_institucion, inversor_vigente
from indicators.services.date_ranges import COLOMBIA_TZ
from scada_proxy.models import InverterMeasurement, MeterMeasurement, WeatherStationMeasurement

DT_H = 2 / 60                  # Δt nominal entre muestras, en horas
MUESTRAS_HORA = 30
MINIMO_MUESTRAS_MEDIDOR = 15   # hora válida del medidor (motor del mercado: MINIMO_VALIDAS)
HORA_INICIO_DIA_SOLAR = 6      # horas diurnas: 06:00–17:59 de Bogotá
HORA_FIN_DIA_SOLAR = 18
IRRADIANCIA_MAX_WM2 = 1400
IRRADIACION_MAX_DIA_KWH_M2 = 8.0
COBERTURA_MIN_ESTACION = 0.8   # fracción mínima de las 360 muestras diurnas para que el día cuente en el PR


# Performance Ratio (reglas de ee0d286 y contraste con la estación de referencia): un día cuenta solo si la irradiación de la estación es
# válida (ver _irradiacion_diaria_sin_cache) y el inversor tiene lectura en al menos el 80 % de las horas de sol.
FRACCION_MIN_HORAS_SOL_INVERSOR = 0.8
MINIMO_HORAS_SOL_INVERSOR = FRACCION_MIN_HORAS_SOL_INVERSOR * (HORA_FIN_DIA_SOLAR - HORA_INICIO_DIA_SOLAR)
MOTIVO_INVERSOR_SIN_COBERTURA = 'inversor sin lecturas en ≥ 80 % de las horas de sol'


def energia_inversor_hora_kwh(suma_w, n):
    """Energía AC de un inversor en una hora (kWh) a partir de la suma de sus `n` lecturas de acPower (W).

    E = max(Σ P, 0) × Δt / 1000. Si la hora tiene entre 15 y 29 lecturas, las que faltan se reponen con la media de
    las presentes (× 30/n); con menos de 15 rige «faltante = 0». Sin lecturas, 0."""
    if suma_w is None or not n:
        return 0.0
    e = max(suma_w, 0.0) * DT_H / 1000.0
    if MINIMO_MUESTRAS_MEDIDOR <= n < MUESTRAS_HORA:
        e *= MUESTRAS_HORA / n          # repone lecturas perdidas sueltas en una hora casi completa
    return e


def horas_inversor(filas):
    """Energía horaria de UN inversor a partir de filas `.values('date', 'acPower')` (fechas aware).

    Agrupa por hora de Bogotá como `_sumas_horarias` (los NULL no cuentan) y aplica `energia_inversor_hora_kwh`.
    Devuelve [{'hora' (naive, Bogotá), 'g_kwh', 'n_g'}] solo con las horas que tienen lecturas, ordenadas."""
    sumas = defaultdict(lambda: [0.0, 0])
    for fila in filas:
        p = fila['acPower']
        if p is None:
            continue
        hora = fila['date'].astimezone(COLOMBIA_TZ).replace(minute=0, second=0, microsecond=0, tzinfo=None)
        acc = sumas[hora]
        acc[0] += p
        acc[1] += 1
    return [{'hora': h, 'g_kwh': energia_inversor_hora_kwh(s, n), 'n_g': n} for h, (s, n) in sorted(sumas.items())]


def energia_diaria_para_pr(horas):
    """{día: (energía del día en kWh, horas de sol con lectura del inversor)} a partir de horas con 'hora', 'g_kwh'
    y 'n_g' (las de `energia_horaria` o las de `horas_inversor`)."""
    dias = {}
    for h in horas:
        dia = h['hora'].date()
        e, horas_sol = dias.get(dia, (0.0, 0))
        e += h['g_kwh']
        if HORA_INICIO_DIA_SOLAR <= h['hora'].hour < HORA_FIN_DIA_SOLAR and h['n_g'] > 0:
            horas_sol += 1
        dias[dia] = (e, horas_sol)
    return dias


def dias_pr(energia_dia, irradiacion):
    """Clasifica para el PR cada día con dato de la estación. Es la regla única de las dos pantallas (Indicadores
    Solares e Inversores).

    `energia_dia`: salida de `energia_diaria_para_pr`. `irradiacion`: salida de `irradiacion_diaria`.
    Devuelve, por día y en orden, (día, energía kWh, H kWh/m², motivo); motivo None quiere decir que el día cuenta.
    Un día cuenta si la estación es válida (cobertura, tope físico y contraste con la estación de referencia) y
    el inversor tiene lectura en al menos el 80 % de las horas de sol."""
    for dia in sorted(irradiacion):
        d = irradiacion[dia]
        e, horas_sol = energia_dia.get(dia, (0.0, 0))
        if not d['valido']:
            motivo = d['motivo'] or 'estación sin dato válido'
        elif horas_sol < MINIMO_HORAS_SOL_INVERSOR:
            motivo = MOTIVO_INVERSOR_SIN_COBERTURA
        else:
            motivo = None
        yield dia, e, d['h_kwh_m2'], motivo


def _rango_bogota(start_date, end_date):
    inicio = COLOMBIA_TZ.localize(datetime.combine(start_date, datetime.min.time()))
    fin = COLOMBIA_TZ.localize(datetime.combine(end_date + timedelta(days=1), datetime.min.time()))
    return inicio, fin


def _sumas_horarias(modelo, scada_ids, campo, inicio, fin):
    """{(scada_id, hora_local_naive): (suma, n)} de `campo` por dispositivo y hora de Bogotá."""
    if not scada_ids:
        return {}
    filas = (
        modelo.objects
        .filter(device__scada_id__in=list(scada_ids), date__gte=inicio, date__lt=fin, **{f'{campo}__isnull': False})
        .annotate(hora=TruncHour('date', tzinfo=COLOMBIA_TZ))
        .values('device__scada_id', 'hora')
        .annotate(s=Sum(campo), n=Count('id'))
    )
    return {
        (f['device__scada_id'], f['hora'].astimezone(COLOMBIA_TZ).replace(tzinfo=None)): (f['s'], f['n'])
        for f in filas
    }


def _horas(inicio, fin):
    h = inicio.replace(tzinfo=None)
    fin_naive = fin.replace(tzinfo=None)
    while h < fin_naive:
        yield h
        h += timedelta(hours=1)


def _energia_horaria_sin_cache(institution_scada_id, start_date, end_date):
    """Lista de horas con G, D, exportación y autoconsumo de la institución.

    Cada elemento: {hora (naive, Bogotá), g_kwh, n_g, d_kwh (None si la hora del medidor no es válida), n_m,
    p_m1_kw, export_kwh, autoconsumo_kwh}. Lanza ValueError si la institución no está configurada.
    """
    cfg = config_institucion(institution_scada_id)
    if cfg is None:
        raise ValueError(f'La institución {institution_scada_id} no tiene configuración energética (institution_config).')
    inicio, fin = _rango_bogota(start_date, end_date)

    respaldo = cfg.get('respaldo_generacion')
    inversores = set(cfg['inversores_generacion']) | set(cfg['inversores_reconstruccion'])
    if respaldo:
        inversores.add(respaldo['inversor'])
    inv = _sumas_horarias(InverterMeasurement, inversores, 'acPower', inicio, fin)
    med = _sumas_horarias(MeterMeasurement, [cfg['medidor_demanda']], 'totalActivePower', inicio, fin)
    neto = cfg['tipo_medidor'] in ('net', 'net_partial')

    def kwh(scada_id, hora):
        s, n = inv.get((scada_id, hora), (None, 0))
        return energia_inversor_hora_kwh(s, n), n

    horas = []
    for hora in _horas(inicio, fin):
        dia = hora.date()
        # Generación
        if respaldo and dia < respaldo['desde']:
            e, n_g = kwh(respaldo['inversor'], hora)
            g = e * respaldo['factor']
        else:
            g, n_g = 0.0, 0
            for sid in cfg['inversores_generacion']:
                if inversor_vigente(cfg, sid, dia):
                    e, n = kwh(sid, hora)
                    g += e
                    n_g += n
        # Medidor principal
        s_m, n_m = med.get((cfg['medidor_demanda'], hora), (None, 0))
        p_m1 = (s_m / n_m) if (s_m is not None and n_m >= MINIMO_MUESTRAS_MEDIDOR) else None
        if p_m1 is None:
            d = export = None
        elif neto:
            aguas_abajo = sum(kwh(sid, hora)[0] for sid in cfg['inversores_reconstruccion']
                              if inversor_vigente(cfg, sid, dia))
            d = max(0.0, p_m1 + aguas_abajo)
            export = max(0.0, -p_m1)
        else:
            d = max(0.0, p_m1)
            export = 0.0
        autoconsumo = max(0.0, g - export) if export is not None else None
        horas.append({
            'hora': hora, 'g_kwh': g, 'n_g': n_g, 'd_kwh': d, 'n_m': n_m, 'p_m1_kw': p_m1,
            'export_kwh': export, 'autoconsumo_kwh': autoconsumo,
        })
    return horas


CACHE_MES_CERRADO_S = 26 * 3600  # meses pasados: warm_solar_cache los renueva cada noche y la reconciliación invalida los que ganan lecturas
CACHE_MES_EN_CURSO_S = 10 * 60


def _meses(start_date, end_date):
    d = start_date.replace(day=1)
    while d <= end_date:
        siguiente = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
        yield d, siguiente - timedelta(days=1)
        d = siguiente


def _clave_energia(institution_scada_id, mes):
    return f'energia-horaria:v2:{institution_scada_id}:{mes:%Y-%m}'


def _clave_irradiacion(institution_scada_id, mes):
    return f'irradiacion-diaria:v3:{institution_scada_id}:{mes:%Y-%m}'


def invalidar_cache_energia(institution_scada_id, mes):
    """Borra la caché del mes (date) de la institución: energía horaria e irradiación diaria."""
    from django.core.cache import cache
    mes = mes.replace(day=1)
    cache.delete_many([_clave_energia(institution_scada_id, mes), _clave_irradiacion(institution_scada_id, mes)])


def _por_meses_con_cache(clave_fn, calcular, institution_scada_id, start_date, end_date, forzar=False):
    """Une el resultado de `calcular(scada_id, ini, fin)` mes a mes, guardando cada mes completo en caché."""
    from django.core.cache import cache
    from indicators.services.date_ranges import get_colombia_date
    hoy = get_colombia_date()
    partes = []
    for ini, fin in _meses(start_date, end_date):
        clave = clave_fn(institution_scada_id, ini)
        mes = None if forzar else cache.get(clave)
        if mes is None:
            mes = calcular(institution_scada_id, ini, fin)
            cache.set(clave, mes, CACHE_MES_EN_CURSO_S if ini <= hoy <= fin else CACHE_MES_CERRADO_S)
        partes.append(mes)
    return partes


def energia_horaria(institution_scada_id, start_date, end_date, forzar=False):
    """Energía horaria de la institución (ver _energia_horaria_sin_cache), con caché por mes completo.

    Calcular un rango largo cuesta varios segundos (agregación horaria de cientos de miles de lecturas); con la
    caché por mes, cualquier rango que reutilice meses ya calculados responde en milisegundos. La tarea
    warm_solar_cache la rellena cada noche tras la reconciliación.
    """
    horas = []
    for mes in _por_meses_con_cache(_clave_energia, _energia_horaria_sin_cache, institution_scada_id,
                                    start_date, end_date, forzar):
        horas.extend(h for h in mes if start_date <= h['hora'].date() <= end_date)
    return horas


def _irradiacion_diaria_sin_cache(institution_scada_id, start_date, end_date):
    """{día: {'h_kwh_m2', 'muestras', 'valido', 'motivo'}} de la estación de la institución.

    H = Σ irradiancia de 06:00 a 17:59 (Bogotá) en [0, 1400] W/m² × Δt. Un día vale para el PR si tiene ≥ 80 % de
    las 360 muestras diurnas y H ≤ 8 kWh/m². Devuelve {} si la institución no tiene estación.
    """
    cfg = config_institucion(institution_scada_id)
    if cfg is None or not cfg.get('estacion'):
        return {}
    inicio, fin = _rango_bogota(start_date, end_date)
    por_dia = defaultdict(lambda: [0.0, 0])
    filas = (
        WeatherStationMeasurement.objects
        .filter(device__scada_id=cfg['estacion'], date__gte=inicio, date__lt=fin,
                irradiance__gte=0, irradiance__lte=IRRADIANCIA_MAX_WM2)
        .annotate(hora=TruncHour('date', tzinfo=COLOMBIA_TZ))
        .values('hora')
        .annotate(s=Sum('irradiance'), n=Count('id'))
    )
    for f in filas:
        h = f['hora'].astimezone(COLOMBIA_TZ)
        if HORA_INICIO_DIA_SOLAR <= h.hour < HORA_FIN_DIA_SOLAR:
            acc = por_dia[h.date()]
            acc[0] += f['s']
            acc[1] += f['n']
    esperadas = (HORA_FIN_DIA_SOLAR - HORA_INICIO_DIA_SOLAR) * MUESTRAS_HORA
    # Validación cruzada con la estación de referencia (institution_config.INSTITUCION_REFERENCIA_PR).
    from statistics import median
    from indicators.institution_config import (
        INSTITUCION_REFERENCIA_PR, MIN_DIAS_SESGO_MENSUAL_PR, TOLERANCIA_REFERENCIA_PR, TOLERANCIA_SESGO_MENSUAL_PR,
    )
    referencia = None
    sesgo_mes = {}   # 'YYYY-MM' -> (mediana de la razón estación/referencia o None, días emparejados)
    if str(institution_scada_id) != INSTITUCION_REFERENCIA_PR:
        referencia = _irradiacion_diaria_sin_cache(INSTITUCION_REFERENCIA_PR, start_date, end_date)
        razones = defaultdict(list)
        for dia, (s_, n_) in por_dia.items():
            ref = referencia.get(dia)
            h_ = s_ * DT_H / 1000.0
            if (ref and ref['valido'] and ref['h_kwh_m2'] > 0 and n_ >= COBERTURA_MIN_ESTACION * esperadas
                    and h_ <= IRRADIACION_MAX_DIA_KWH_M2):
                razones[dia.strftime('%Y-%m')].append(h_ / ref['h_kwh_m2'])
        sesgo_mes = {m: (median(v) if len(v) >= MIN_DIAS_SESGO_MENSUAL_PR else None, len(v))
                     for m, v in razones.items()}
    resultado = {}
    for dia, (s, n) in por_dia.items():
        h_dia = s * DT_H / 1000.0
        if not cfg.get('estacion_apta_pr', True):
            valido, motivo = False, 'estación no apta (lecturas físicamente imposibles)'
        elif n < COBERTURA_MIN_ESTACION * esperadas:
            valido, motivo = False, f'cobertura diurna {n}/{esperadas} muestras'
        elif h_dia > IRRADIACION_MAX_DIA_KWH_M2:
            valido, motivo = False, f'irradiación {h_dia:.2f} kWh/m² > {IRRADIACION_MAX_DIA_KWH_M2}'
        elif referencia is not None:
            ref = referencia.get(dia)
            mediana, n_pares = sesgo_mes.get(dia.strftime('%Y-%m'), (None, 0))
            if mediana is None:
                valido, motivo = False, (f'solo {n_pares} días del mes para contrastar la estación con la de '
                                         f'referencia (Alvernia); hacen falta {MIN_DIAS_SESGO_MENSUAL_PR}')
            elif abs(mediana - 1) > TOLERANCIA_SESGO_MENSUAL_PR:
                valido, motivo = False, (f'en este mes la estación marca {mediana:.2f} veces la de referencia '
                                         f'(Alvernia): sesgo mayor de {int(TOLERANCIA_SESGO_MENSUAL_PR * 100)} %')
            elif ref is None or not ref['valido']:
                valido, motivo = False, 'sin dato válido de la estación de referencia (Alvernia) para contrastar'
            elif abs(h_dia / ref['h_kwh_m2'] - 1) > TOLERANCIA_REFERENCIA_PR:
                valido = False
                motivo = (f'la estación difiere más de {int(TOLERANCIA_REFERENCIA_PR * 100)} % de la de referencia '
                          f'(Alvernia) ese día')
            else:
                valido, motivo = True, None
        else:
            valido, motivo = True, None
        resultado[dia] = {'h_kwh_m2': h_dia, 'muestras': n, 'valido': valido, 'motivo': motivo}
    return resultado


def irradiacion_diaria(institution_scada_id, start_date, end_date, forzar=False):
    """Irradiación diaria de la estación de la institución (ver _irradiacion_diaria_sin_cache), con caché por mes."""
    resultado = {}
    for mes in _por_meses_con_cache(_clave_irradiacion, _irradiacion_diaria_sin_cache, institution_scada_id,
                                    start_date, end_date, forzar):
        resultado.update({d: v for d, v in mes.items() if start_date <= d <= end_date})
    return resultado


def totales_plantas(inicio_dt, fin_dt):
    """Totales de las plantas del proyecto en [inicio_dt, fin_dt) (datetimes aware), sumando las instituciones
    configuradas: generación G, demanda D de los circuitos medidos (solo horas válidas del medidor), energía tomada
    de la red (D − autoconsumo), horas transcurridas y horas con medidor válido. Se usa en el inicio (Dashboard)."""
    from indicators.institution_config import INSTITUCIONES
    inicio_local = inicio_dt.astimezone(COLOMBIA_TZ).replace(tzinfo=None)
    fin_local = fin_dt.astimezone(COLOMBIA_TZ).replace(tzinfo=None)
    tot = {'g_kwh': 0.0, 'd_kwh': 0.0, 'red_kwh': 0.0, 'horas': 0, 'horas_medidor': 0, 'horas_medidor_posibles': 0}
    for scada_id in INSTITUCIONES:
        for h in energia_horaria(scada_id, inicio_local.date(), fin_local.date()):
            if not (inicio_local <= h['hora'] < fin_local):
                continue
            tot['g_kwh'] += h['g_kwh']
            tot['horas_medidor_posibles'] += 1
            if h['d_kwh'] is not None:
                tot['d_kwh'] += h['d_kwh']
                tot['red_kwh'] += h['d_kwh'] - h['autoconsumo_kwh']
                tot['horas_medidor'] += 1
    horas = (fin_dt - inicio_dt).total_seconds() / 3600.0
    tot['horas'] = max(horas, 0.0)
    return tot
