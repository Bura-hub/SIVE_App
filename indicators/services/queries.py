"""
Helpers de queryset compartidos por las vistas de indicadores (Ola 5).
"""
from django.db.models import Sum, Avg, Max, Min


def apply_device_filter(queryset, device_id):
    """Filtra por dispositivo aceptando tanto el id entero local como el scada_id
    (UUID/string). Duplicado en 3 vistas de indicadores/chart antes de la extracción."""
    if str(device_id).isdigit():
        return queryset.filter(device_id=int(device_id))
    return queryset.filter(device__scada_id=device_id)


def aggregate_indicators_by_period(queryset, *, sum_fields=(), avg_fields=(),
                                   max_fields=(), min_fields=()):
    """Consolida indicadores por periodo (fecha) agregando entre dispositivos.

    Suma energías/contadores, promedia variables continuas y toma max/min según
    corresponda. Devuelve una lista de dicts, uno por (fecha, institución),
    con device_name='Todos'. El alias de anotación usa sufijo '_agg' para no
    colisionar con los campos del modelo.
    """
    annotations = {}
    rename = {}
    for f in sum_fields:
        annotations[f + '_agg'] = Sum(f); rename[f + '_agg'] = f
    for f in avg_fields:
        annotations[f + '_agg'] = Avg(f); rename[f + '_agg'] = f
    for f in max_fields:
        annotations[f + '_agg'] = Max(f); rename[f + '_agg'] = f
    for f in min_fields:
        annotations[f + '_agg'] = Min(f); rename[f + '_agg'] = f

    rows = (queryset
            .values('date', 'time_range', 'institution_id', 'institution__name')
            .annotate(**annotations)
            .order_by('-date'))

    result = []
    for row in rows:
        item = {
            'date': row['date'],
            'time_range': row['time_range'],
            'institution': row['institution_id'],
            'institution_name': row['institution__name'],
            'device': None,
            'device_name': 'Todos',
        }
        for alias, orig in rename.items():
            item[orig] = row[alias]
        result.append(item)
    return result
