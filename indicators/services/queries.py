"""
Helpers de queryset compartidos por las vistas de indicadores (Ola 5).
"""


def apply_device_filter(queryset, device_id):
    """Filtra por dispositivo aceptando tanto el id entero local como el scada_id
    (UUID/string). Duplicado en 3 vistas de indicadores/chart antes de la extracción."""
    if str(device_id).isdigit():
        return queryset.filter(device_id=int(device_id))
    return queryset.filter(device__scada_id=device_id)
