"""
Energía horaria por institución con la convención de la tesis y del mercado P2P (diseño, decisiones D2 y D3).

- G (generación): Σ acPower de los inversores de generación vigentes, en kWh por hora, con «faltante = 0»: la
  energía de la hora es Σ P·Δt con Δt nominal de 2 min. Una muestra que no llegó no suma; no se rellena.
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


def energia_horaria(institution_scada_id, start_date, end_date):
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
        return (max(s, 0.0) * DT_H / 1000.0 if s is not None else 0.0), n

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


def irradiacion_diaria(institution_scada_id, start_date, end_date):
    """{día: {'h_kwh_m2', 'muestras', 'valido', 'motivo'}} de la estación de la institución (decisión D5).

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
    resultado = {}
    for dia, (s, n) in por_dia.items():
        h_dia = s * DT_H / 1000.0
        if not cfg.get('estacion_apta_pr', True):
            valido, motivo = False, 'estación no apta (lecturas físicamente imposibles)'
        elif n < COBERTURA_MIN_ESTACION * esperadas:
            valido, motivo = False, f'cobertura diurna {n}/{esperadas} muestras'
        elif h_dia > IRRADIACION_MAX_DIA_KWH_M2:
            valido, motivo = False, f'irradiación {h_dia:.2f} kWh/m² > {IRRADIACION_MAX_DIA_KWH_M2}'
        else:
            valido, motivo = True, None
        resultado[dia] = {'h_kwh_m2': h_dia, 'muestras': n, 'valido': valido, 'motivo': motivo}
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
