"""
Métricas de un KPI de dashboard (Ola 5).

Dado el valor actual y el del mes anterior (+ flags de tipo de indicador), devuelve el
dict con el valor formateado, el cambio %, el estado y la descripción textual. Extraído
verbatim de ConsumptionSummaryView. Presentación pura: sin BD ni DRF.
"""
from indicators.services.formatting import format_energy_value


def summarize_inverter_status(scada_inverters):
    """Resume el estado de los inversores (listado de la API SCADA) para la tarjeta del
    dashboard: conteo activo/total + estado y descripción. Puro."""
    total = len(scada_inverters)
    active = sum(1 for inv in scada_inverters if inv.get('status') == 'online')
    inactive = total - active
    if total == 0:
        return {'active': 0, 'total': 0, 'status': 'normal',
                'description': 'Sin inversores registrados'}
    if inactive > 0:
        return {'active': active, 'total': total, 'status': 'critico',
                'description': f'{inactive} inactivos'}
    return {'active': active, 'total': total, 'status': 'estable',
            'description': 'Todos activos'}


def calculate_kpi_metrics(current_value, previous_value, title, base_unit_name, is_balance=False, is_average_power=False, is_temperature=False, is_humidity=False, is_wind_speed=False, is_irradiance=False):
    formatted_value, unit = format_energy_value(current_value, base_unit_name)
    change_percentage = 0.0
    status_text = "normal"
    description_text = ""

    if previous_value != 0:
        change_percentage = ((current_value - previous_value) / previous_value) * 100
    elif current_value != 0:
        change_percentage = 100.0 if current_value > 0 else -100.0

    if is_balance:
        if current_value > 0:
            description_text = "Superávit"
            status_text = "positivo"
        elif current_value < 0:
            description_text = "Déficit"
            status_text = "negativo"
        else:
            description_text = "Equilibrio"
            status_text = "normal"
    elif is_average_power:
        if current_value > 0:
            description_text = "Generando"
            status_text = "estable"
        else:
            description_text = "Sin generación"
            status_text = "normal"

        if change_percentage > 0:
            description_text += f" (+{change_percentage:.2f}%)"
        elif change_percentage < 0:
            description_text += f" ({change_percentage:.2f}%)"
    elif is_temperature:
        description_text = "Rango normal"
        status_text = "normal"

        if change_percentage > 0:
            description_text += f" (+{change_percentage:.1f}%)"
        elif change_percentage < 0:
            description_text += f" ({change_percentage:.1f}%)"
    elif is_humidity:
        if 40 <= current_value <= 60:
            description_text = "Óptimo"
            status_text = "optimo"
        elif current_value > 60:
            description_text = "Alta"
            status_text = "critico"
        else:
            description_text = "Baja"
            status_text = "critico"

        if change_percentage > 0:
            description_text += f" (+{change_percentage:.1f}%)"
        elif change_percentage < 0:
            description_text += f" ({change_percentage:.1f}%)"
    elif is_wind_speed:
        if current_value < 10:
            description_text = "Bajo"
            status_text = "normal"
        elif 10 <= current_value <= 30:
            description_text = "Moderado"
            status_text = "moderado"
        else:
            description_text = "Alto"
            status_text = "critico"

        if change_percentage > 0:
            description_text += f" (+{change_percentage:.1f}%)"
        elif change_percentage < 0:
            description_text += f" ({change_percentage:.1f}%)"
    elif is_irradiance:
        if current_value < 200:
            description_text = "Baja"
            status_text = "normal"
        elif 200 <= current_value <= 800:
            description_text = "Moderada"
            status_text = "moderado"
        else:
            description_text = "Alta"
            status_text = "optimo"

        if change_percentage > 0:
            description_text += f" (+{change_percentage:.1f}%)"
        elif change_percentage < 0:
            description_text += f" ({change_percentage:.1f}%)"

    else:  # Para consumo y generación
        if change_percentage > 0:
            status_text = "positivo"
        elif change_percentage < 0:
            status_text = "negativo"
        else:
            status_text = "normal"

        description_text = f"{'+' if change_percentage >= 0 else ''}{change_percentage:.2f}% vs mes pasado"

    change_text = f"{'+' if change_percentage >= 0 else ''}{change_percentage:.2f}% vs mes pasado"

    return {
        "title": title,
        "value": formatted_value,
        "unit": unit,
        "change": change_text,
        "description": description_text,
        "status": status_text,
        "previousMonthValue": previous_value,
        "previousMonthUnit": base_unit_name
    }
