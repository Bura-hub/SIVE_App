"""
Fórmula canónica de energía para los indicadores de SIVET.

Módulo PURO (sin dependencias de Django) para poder probar la fórmula con
`python3 -m unittest` sin base de datos. La lógica de negocio (integración de la
potencia en el tiempo) vive aquí una sola vez y se reutiliza en indicators/tasks.py.

Metodología (indicators.md):
    E_kWh = Σ_i (P_i · Δt)      con Δt = 2/60 h  (muestreo cada 2 minutos)

Correcciones que esta fórmula encapsula frente al código anterior:

1. INTEGRACIÓN EN EL TIEMPO (Δt): antes se sumaba la potencia instantánea sin
   multiplicar por Δt.

2. AGREGACIÓN DE FLOTA: la energía de N dispositivos es la SUMA de sus muestras
   por Δt, NO el promedio por muestra × horas (el código de generación dividía por
   el número total de mediciones de la flota, subestimando la generación en ~N).

3. UNIDAD DE POTENCIA POR MÉTRICA — confirmado empíricamente con
   scripts/audit_indicators.py (jul-2026, ~8.3M mediciones, Δt medido = 2.00 min):
     - `totalActivePower` (medidores eléctricos): mediana ~0.90, máx ~74  -> kW
     - `acPower`          (inversores):           mediana ~2936, máx ~16266 -> W
   Por eso el factor de conversión a kW es DISTINTO según la métrica: el consumo NO
   se divide por 1000 (ya está en kW) y la generación SÍ (está en W). Usar el factor
   equivocado desplaza el resultado 1000×.
"""

# Intervalo de muestreo en horas (mediciones cada 2 minutos), per indicators.md
# y confirmado por la auditoría (Δt mediano observado = 2.00 min).
SAMPLE_INTERVAL_HOURS = 2.0 / 60.0

# Factores de conversión de la potencia cruda a kW, por métrica (ver docstring):
POWER_UNIT_KW = 1.0          # potencia ya en kW (totalActivePower): NO dividir
POWER_UNIT_WATTS = 1000.0    # potencia en Watts (acPower): dividir por 1000


def energy_kwh_from_power_sum(power_sum, watts_per_kw=POWER_UNIT_WATTS,
                             sample_interval_hours=SAMPLE_INTERVAL_HOURS):
    """
    Energía en kWh a partir de la SUMA de potencias instantáneas (sobre todas las
    muestras y dispositivos del periodo):

        E_kWh = (Σ P) · Δt / watts_per_kw

    `power_sum` puede ser None (agregación vacía del ORM) -> 0.0.
    Preferir los helpers consumption_energy_kwh / generation_energy_kwh, que ya
    fijan la unidad correcta según la métrica.
    """
    if power_sum is None:
        return 0.0
    return power_sum * sample_interval_hours / watts_per_kw


def consumption_energy_kwh(power_sum, sample_interval_hours=SAMPLE_INTERVAL_HOURS):
    """Energía de CONSUMO desde Σ(totalActivePower). `totalActivePower` está en kW,
    así que NO se divide por 1000."""
    return energy_kwh_from_power_sum(power_sum, POWER_UNIT_KW, sample_interval_hours)


def generation_energy_kwh(power_sum, sample_interval_hours=SAMPLE_INTERVAL_HOURS):
    """Energía de GENERACIÓN desde Σ(acPower). `acPower` está en Watts, así que se
    divide por 1000."""
    return energy_kwh_from_power_sum(power_sum, POWER_UNIT_WATTS, sample_interval_hours)


def energy_kwh_from_samples(power_samples, watts_per_kw=POWER_UNIT_WATTS,
                            sample_interval_hours=SAMPLE_INTERVAL_HOURS):
    """Igual que energy_kwh_from_power_sum pero a partir de un iterable de muestras."""
    total = 0.0
    for value in power_samples:
        if value is not None:
            total += value
    return energy_kwh_from_power_sum(total, watts_per_kw, sample_interval_hours)
