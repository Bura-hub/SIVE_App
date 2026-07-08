"""
Fórmula canónica de energía para los indicadores de SIVET.

Módulo PURO (sin dependencias de Django) para poder probar la fórmula con
`python3 -m unittest` sin base de datos. La lógica de negocio (integración de la
potencia en el tiempo) vive aquí una sola vez y se reutiliza en indicators/tasks.py.

Metodología (indicators.md):
    E_kWh = Σ_i (P_i · Δt)      con Δt = 2/60 h  (muestreo cada 2 minutos)

Dos correcciones que esta fórmula encapsula frente al código anterior:

1. INTEGRACIÓN EN EL TIEMPO (Δt): antes se sumaba la potencia instantánea sin
   multiplicar por Δt, por lo que el "consumo" quedaba ~30× inflado (1/Δt = 30).

2. AGREGACIÓN DE FLOTA: la energía de N dispositivos es la SUMA de sus muestras
   por Δt, NO el promedio por muestra × horas. El código de generación dividía por
   el número total de mediciones de la flota, subestimando la generación en un
   factor N (nº de inversores).

UNIDAD DE POTENCIA (W vs kW) — ambigüedad pendiente de datos:
    indicators.md describe P en kW (E = Σ P·Δt, sin dividir por 1000), pero los
    modelos (`help_text="... en Watts"`, `max_power_w`) y el resto del código
    tratan `totalActivePower`/`acPower` como Watts (dividen por 1000). Esta
    discrepancia SOLO se resuelve con datos reales: `scripts/audit_indicators.py`
    compara la energía integrada contra los contadores acumulados
    (ElectricMeterEnergyConsumption, en kWh reales del registro del medidor) y
    reporta el factor empírico. Mientras tanto se mantiene el supuesto Watts
    (÷1000), coherente con el help_text de los modelos y con la energía por
    inversor ya existente. Si la auditoría demuestra que la potencia ya viene en
    kW, basta cambiar WATTS_PER_KILOWATT a 1.0 (un solo punto).
"""

# Intervalo de muestreo en horas (mediciones cada 2 minutos), per indicators.md.
SAMPLE_INTERVAL_HOURS = 2.0 / 60.0

# Factor de conversión de la potencia cruda a kW. 1000 asume que la potencia viene
# en Watts (supuesto actual, a confirmar con scripts/audit_indicators.py).
WATTS_PER_KILOWATT = 1000.0


def energy_kwh_from_power_sum(power_sum, sample_interval_hours=SAMPLE_INTERVAL_HOURS,
                             watts_per_kw=WATTS_PER_KILOWATT):
    """
    Energía en kWh a partir de la SUMA de potencias instantáneas (sobre todas las
    muestras y dispositivos del periodo):

        E_kWh = (Σ P) · Δt / watts_per_kw

    `power_sum` puede ser None (agregación vacía del ORM) -> 0.0.
    """
    if power_sum is None:
        return 0.0
    return power_sum * sample_interval_hours / watts_per_kw


def energy_kwh_from_samples(power_samples, sample_interval_hours=SAMPLE_INTERVAL_HOURS,
                            watts_per_kw=WATTS_PER_KILOWATT):
    """Igual que energy_kwh_from_power_sum pero a partir de un iterable de muestras."""
    total = 0.0
    for value in power_samples:
        if value is not None:
            total += value
    return energy_kwh_from_power_sum(total, sample_interval_hours, watts_per_kw)
