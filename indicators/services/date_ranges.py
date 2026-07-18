"""
Helpers de fecha y rango en hora de Colombia (América/Bogotá).

Centraliza COLOMBIA_TZ (antes duplicado en tasks.py y views.py) y la resolución de
rangos de los endpoints de indicadores. Bogotá no tiene DST, así que los rangos son
exactos. Módulo puro (sin Celery ni DRF).
"""
from datetime import datetime, timedelta

import pytz
from django.utils import timezone as django_timezone

# Zona horaria de Colombia.
COLOMBIA_TZ = pytz.timezone('America/Bogota')

# Ventana por defecto y tope de los endpoints de indicadores.
INDICATORS_DEFAULT_RANGE_DAYS = 31
INDICATORS_MAX_RANGE_DAYS = 366

# Tope del rango horario (vista horaria, Opción B): 31 días == 744 horas.
INDICATORS_HOURLY_MAX_RANGE_DAYS = 31
INDICATORS_HOURLY_DEFAULT_RANGE_DAYS = 14


def get_colombia_now():
    """Fecha y hora actual en zona horaria de Colombia."""
    return django_timezone.now().astimezone(COLOMBIA_TZ)


def get_colombia_date():
    """Fecha actual en zona horaria de Colombia."""
    return get_colombia_now().date()


def colombia_day_range(start_date, end_date):
    """Rango datetime aware [start 00:00, end+1día 00:00) en hora de Bogotá.

    Equivalente exacto al lookup `date__date__range=(start, end)` (inclusivo) con
    TIME_ZONE=America/Bogota, pero expresado como comparación de timestamps, que SÍ
    puede usar el índice (device, date).
    """
    start_dt = COLOMBIA_TZ.localize(datetime.combine(start_date, datetime.min.time()))
    end_dt = COLOMBIA_TZ.localize(datetime.combine(end_date + timedelta(days=1), datetime.min.time()))
    return start_dt, end_dt


def colombia_hour_range(hour_start):
    """Rango datetime aware [hour_start, hour_start+1h) en hora de Bogotá.

    Análogo a `colombia_day_range` pero para el grano horario: recibe un datetime
    aware que representa el inicio de la hora (p.ej. 14:00:00-05:00) y devuelve el
    par (start, end) que delimita esa hora exacta. Si `hour_start` no trae tzinfo,
    se asume que ya está en hora de Bogotá y se localiza; si trae otra zona, se
    convierte a Bogotá antes de truncar minutos/segundos/microsegundos.
    """
    if django_timezone.is_naive(hour_start):
        hour_start = COLOMBIA_TZ.localize(hour_start)
    else:
        hour_start = hour_start.astimezone(COLOMBIA_TZ)

    start_dt = hour_start.replace(minute=0, second=0, microsecond=0)
    end_dt = start_dt + timedelta(hours=1)
    return start_dt, end_dt


def resolve_indicators_hourly_range(date_str=None, start_date_str=None, end_date_str=None):
    """Resuelve el rango horario a graficar (vista horaria, Opción B).

    Devuelve (start_date, end_date, error), en las mismas unidades (date, no
    datetime) que `resolve_indicators_date_range`, para reutilizar `colombia_day_range`
    al consultar. Reglas:
    - Si se pasa `date_str`: día único (start_date == end_date == esa fecha).
    - Si no, se resuelve con `start_date_str`/`end_date_str` igual que la vista diaria
      (sin fechas -> últimos INDICATORS_HOURLY_MAX_RANGE_DAYS días; solo una de las dos
      -> se completa la otra).
    - Tope estricto: el rango no puede superar INDICATORS_HOURLY_MAX_RANGE_DAYS días
      (7 días == 168 horas). Si se supera, error 400 en español.
    - Fechas invertidas o formato inválido: error en español.
    """
    if date_str:
        try:
            single_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return None, None, "Formato de fecha inválido. Use YYYY-MM-DD en 'date'."
        return single_date, single_date, None

    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else None
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else None
    except ValueError:
        return None, None, "Formato de fecha inválido. Use YYYY-MM-DD en 'start_date' y 'end_date'."

    if end_date is None:
        end_date = get_colombia_date()
    if start_date is None:
        start_date = end_date - timedelta(days=INDICATORS_HOURLY_DEFAULT_RANGE_DAYS - 1)

    if start_date > end_date:
        return None, None, "La fecha de inicio no puede ser posterior a la fecha de fin."

    # Tope de INDICATORS_HOURLY_MAX_RANGE_DAYS días para la vista horaria: el rango
    # es inclusivo en ambos extremos, así que la ventana de días es (end_date - start_date) + 1.
    if (end_date - start_date).days + 1 > INDICATORS_HOURLY_MAX_RANGE_DAYS:
        return None, None, (
            f"El rango horario solicitado supera el máximo permitido de "
            f"{INDICATORS_HOURLY_MAX_RANGE_DAYS} días ({INDICATORS_HOURLY_MAX_RANGE_DAYS * 24} horas). "
            f"Reduzca el rango e intente de nuevo."
        )

    return start_date, end_date, None


def resolve_indicators_hourly_datetime_range(start_datetime_str, end_datetime_str):
    """Resuelve un rango horario con precisión de hora/minuto.

    Acepta ISO 'YYYY-MM-DDTHH:MM' o 'YYYY-MM-DDTHH:MM:SS'. Devuelve
    (start_dt, end_dt, error) con datetimes aware en zona Colombia.
    """
    def _parse(value):
        for fmt in ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M'):
            try:
                return datetime.strptime(value, fmt)
            except (ValueError, TypeError):
                continue
        return None

    if not start_datetime_str or not end_datetime_str:
        return None, None, "Se requieren 'start_datetime' y 'end_datetime' (YYYY-MM-DDTHH:MM)."

    start_naive = _parse(start_datetime_str)
    end_naive = _parse(end_datetime_str)
    if start_naive is None or end_naive is None:
        return None, None, "Formato de fecha/hora inválido. Use YYYY-MM-DDTHH:MM."

    start_dt = COLOMBIA_TZ.localize(start_naive)
    end_dt = COLOMBIA_TZ.localize(end_naive)

    if start_dt > end_dt:
        return None, None, "La fecha/hora de inicio no puede ser posterior a la de fin."

    if (end_dt - start_dt).days + 1 > INDICATORS_HOURLY_MAX_RANGE_DAYS:
        return None, None, (
            f"El rango horario solicitado supera el máximo permitido de "
            f"{INDICATORS_HOURLY_MAX_RANGE_DAYS} días. Reduzca el rango e intente de nuevo."
        )

    return start_dt, end_dt, None


def resolve_indicators_date_range(start_date_str, end_date_str):
    """Resuelve el rango efectivo de los endpoints de indicadores.

    Devuelve (start_date, end_date, error):
    - Sin fechas: últimos INDICATORS_DEFAULT_RANGE_DAYS días.
    - Solo end_date: ventana por defecto hacia atrás; solo start_date: end = hoy.
    - Formato inválido, fechas invertidas o rango > INDICATORS_MAX_RANGE_DAYS: error
      con mensaje en español (la vista debe responder 400).
    """
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else None
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else None
    except ValueError:
        return None, None, "Formato de fecha inválido. Use YYYY-MM-DD en 'start_date' y 'end_date'."

    if end_date is None:
        end_date = get_colombia_date()
    if start_date is None:
        start_date = end_date - timedelta(days=INDICATORS_DEFAULT_RANGE_DAYS)

    if start_date > end_date:
        return None, None, "La fecha de inicio no puede ser posterior a la fecha de fin."

    if (end_date - start_date).days > INDICATORS_MAX_RANGE_DAYS:
        return None, None, (
            f"El rango de fechas solicitado supera el máximo permitido de "
            f"{INDICATORS_MAX_RANGE_DAYS} días. Reduzca el rango e intente de nuevo."
        )

    return start_date, end_date, None
