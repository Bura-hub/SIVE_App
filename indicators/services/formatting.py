"""
Formateo y escalado de unidades de energía (kWh/MWh/GWh) para las respuestas de la API.
Presentación pura: sin BD ni DRF.
"""


def auto_energy_unit(max_value):
    """Dada la magnitud máxima de una serie en kWh, devuelve (unidad, divisor) para
    escalarla a GWh/MWh/kWh de forma legible."""
    if max_value >= 1_000_000:
        return "GWh", 1_000_000
    if max_value >= 1_000:
        return "MWh", 1_000
    return "kWh", 1


def format_energy_value(value_base_unit, base_unit_name="kWh"):
    """Formatea un valor a string con su unidad, escalando por magnitud y conservando
    el signo. kWh -> MWh/GWh; W -> kW/MW; °C, %RH, km/h y W/m² con 1 decimal."""
    is_negative = value_base_unit < 0
    abs_value = abs(value_base_unit)

    if base_unit_name == "kWh":
        if abs_value >= 1_000_000:
            formatted_value = abs_value / 1_000_000
            unit = "GWh"
        elif abs_value >= 1_000:
            formatted_value = abs_value / 1_000
            unit = "MWh"
        else:
            formatted_value = abs_value
            unit = "kWh"

        if is_negative:
            return f"-{formatted_value:.2f}", unit
        return f"{formatted_value:.2f}", unit
    elif base_unit_name == "W":
        if abs_value >= 1_000_000:
            formatted_value = abs_value / 1_000_000
            unit = "MW"
        elif abs_value >= 1_000:
            formatted_value = abs_value / 1_000
            unit = "kW"
        else:
            formatted_value = abs_value
            unit = "W"

        if is_negative:
            return f"-{formatted_value:.2f}", unit
        return f"{formatted_value:.2f}", unit
    elif base_unit_name == "°C":
        return f"{value_base_unit:.1f}", "°C"
    elif base_unit_name == "%RH":
        return f"{value_base_unit:.1f}", "%"
    elif base_unit_name == "km/h":
        return f"{value_base_unit:.1f}", "km/h"
    elif base_unit_name == "W/m²":
        return f"{value_base_unit:.1f}", "W/m²"
    return f"{value_base_unit:.2f}", base_unit_name
