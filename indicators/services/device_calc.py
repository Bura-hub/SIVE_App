"""
Iteración día-a-día / mes-a-mes de cálculos por dispositivo (Ola 5).

Colapsa los envoltorios `_calculate_{daily,monthly}_{electrical,inverter}_data`, que eran
idénticos salvo la función de cálculo que invocaban. Reciben esa función como parámetro
(`calc_fn(device_id, 'YYYY-MM-DD', granularidad) -> str`) y cuentan creados/actualizados
según el string de resultado. Módulo puro (no importa Celery ni las tareas).

Las estaciones meteorológicas NO usan esto: su cálculo diario/mensual tiene una estructura
distinta (lógica inline), no la delegación (device_id, fecha, granularidad).
"""
import logging
from datetime import timedelta

logger = logging.getLogger(__name__)


def _first_of_next_month(d):
    """Primer día del mes siguiente a d (robusto a fin de mes)."""
    return (d.replace(day=1) + timedelta(days=32)).replace(day=1)


def run_over_days(device, start_date, end_date, calc_fn):
    """Recorre [start_date, end_date] día a día llamando calc_fn(device.id, fecha, 'daily')."""
    records_created = 0
    records_updated = 0
    current_date = start_date
    while current_date <= end_date:
        logger.info(f"  Procesando fecha: {current_date}")
        result = calc_fn(device.id, current_date.strftime('%Y-%m-%d'), 'daily')
        if "creado" in result:
            records_created += 1
        elif "actualizado" in result:
            records_updated += 1
        current_date += timedelta(days=1)
    return records_created, records_updated


def run_over_months(device, start_date, end_date, calc_fn):
    """Recorre los meses de [start_date, end_date] llamando calc_fn(device.id, primer-día-del-mes, 'monthly')."""
    records_created = 0
    records_updated = 0
    current_date = start_date.replace(day=1)
    while current_date <= end_date:
        logger.info(f"  Procesando mes: {current_date.month}/{current_date.year}")
        result = calc_fn(device.id, current_date.strftime('%Y-%m-%d'), 'monthly')
        if "creado" in result:
            records_created += 1
        elif "actualizado" in result:
            records_updated += 1
        current_date = _first_of_next_month(current_date)
    return records_created, records_updated
