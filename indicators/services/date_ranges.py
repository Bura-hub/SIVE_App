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
