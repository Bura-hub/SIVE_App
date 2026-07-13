"""
Cálculo PURO de indicadores de un inversor (Ola 5).

Extraído de la task `calculate_inverter_indicators`: recibe un iterable de filas dict
(`.values(*INVERTER_FIELDS)`) y devuelve el dict de indicadores calculados, sin tocar la
BD ni Celery. La task queda como envoltorio (query + update_or_create de InverterIndicators
y de InverterChartData). `measurement_count`/`last_measurement_date` NO se calculan aquí.
"""
import statistics

from indicators.energy import SAMPLE_INTERVAL_HOURS
from indicators.services.rows import _row_get

# Umbral mínimo de corriente promedio (A) para evaluar desbalance de corriente de
# inyección. Por debajo de este umbral la carga/inyección es despreciable (equivalente a
# standby/vacío) y la fórmula NEMA de desbalance (max_desviación/promedio×100) se dispara
# sin sentido físico porque el denominador tiende a 0: con una fase en 0.0 A el resultado
# llega a ~200%. Mismo problema y mismo umbral que en indicators/services/meter_calc.py
# (MIN_CURRENT_A_FOR_UNBALANCE). Ajustable si el equipo de campo define otro valor.
MIN_CURRENT_A_FOR_UNBALANCE = 1.0

# Columnas v2 que consume el cálculo del inversor.
INVERTER_FIELDS = (
    'acPower', 'dcPower', 'reactivePower', 'apparentPower',
    'powerFactor', 'acFrequency',
    'acVoltagePhaseA', 'acVoltagePhaseB', 'acVoltagePhaseC',
    'acCurrentPhaseA', 'acCurrentPhaseB', 'acCurrentPhaseC',
)


def compute_inverter_indicators(rows):
    """Indicadores de un inversor a partir de un iterable de filas dict de `.values()`.
    Puro (no toca la BD). Devuelve el dict de campos calculados."""
    ac_power_values = []
    dc_power_values = []
    reactive_power_values = []
    apparent_power_values = []
    power_factor_values = []
    frequency_values = []
    voltage_phases = []
    current_phases = []
    irradiance_values = []
    temperature_values = []

    for data in rows:
        # Potencia AC y DC
        ac_power = _row_get(data, 'acPower')
        dc_power = _row_get(data, 'dcPower')
        if ac_power is not None:
            ac_power_values.append(ac_power)
        if dc_power is not None:
            dc_power_values.append(dc_power)

        # Potencia reactiva y aparente
        reactive_power = _row_get(data, 'reactivePower')
        apparent_power = _row_get(data, 'apparentPower')
        if reactive_power is not None:
            reactive_power_values.append(reactive_power)
        if apparent_power is not None:
            apparent_power_values.append(apparent_power)

        # Factor de potencia
        power_factor = _row_get(data, 'powerFactor')
        if power_factor is not None:
            power_factor_values.append(power_factor)

        # Frecuencia
        frequency = _row_get(data, 'acFrequency')
        if frequency is not None:
            frequency_values.append(frequency)

        # Voltajes por fase
        voltage_a = _row_get(data, 'acVoltagePhaseA')
        voltage_b = _row_get(data, 'acVoltagePhaseB')
        voltage_c = _row_get(data, 'acVoltagePhaseC')
        if all(v is not None for v in [voltage_a, voltage_b, voltage_c]):
            voltage_phases.append([voltage_a, voltage_b, voltage_c])

        # Corrientes por fase
        current_a = _row_get(data, 'acCurrentPhaseA')
        current_b = _row_get(data, 'acCurrentPhaseB')
        current_c = _row_get(data, 'acCurrentPhaseC')
        if all(c is not None for c in [current_a, current_b, current_c]):
            current_phases.append([current_a, current_b, current_c])

        # Datos meteorológicos: la categoría 'inverter' NO tiene columnas
        # irradiance/temperature en v2 (esas claves tampoco existían en el
        # jsonb v1, donde data.get(K, 0) devolvía siempre el default 0).
        # Se conserva el comportamiento exacto apendeando 0 por medición.
        irradiance_values.append(0)
        temperature_values.append(0)

    # Calcular indicadores

    # Δt (h) de la integración de potencia. Se define SIEMPRE al inicio para que
    # esté disponible aunque solo haya irradiancia (antes se definía dentro del
    # if de ac/dc y provocaba NameError al calcular la irradiancia acumulada).
    delta_t = SAMPLE_INTERVAL_HOURS

    # 4.1. Eficiencia de Conversión DC-AC
    if ac_power_values and dc_power_values:
        # Calcular energía total (integral de potencia * tiempo)
        energy_ac_daily_kwh = sum(ac_power_values) * delta_t / 1000  # Convertir W*h a kWh
        energy_dc_daily_kwh = sum(dc_power_values) * delta_t / 1000  # Convertir W*h a kWh

        if energy_dc_daily_kwh > 0:
            dc_ac_efficiency_pct = (energy_ac_daily_kwh / energy_dc_daily_kwh) * 100
        else:
            dc_ac_efficiency_pct = 0
        # El dato crudo del connector trae dcPower < acPower en ~92% de las filas
        # (físicamente imposible: la entrada DC debe superar la salida AC), lo que
        # producía eficiencias >100% (hasta 185%). Se acota al rango físico [0,100]
        # hasta confirmar la semántica de dcPower con el equipo del scada-connector.
        # Ver auditoría (calidad-datos, Ola 1).
        dc_ac_efficiency_pct = min(100.0, max(0.0, dc_ac_efficiency_pct))
    else:
        energy_ac_daily_kwh = 0
        energy_dc_daily_kwh = 0
        dc_ac_efficiency_pct = 0

    # 4.2. Energía Total Generada
    total_generated_energy_kwh = energy_ac_daily_kwh

    # 4.3. Performance Ratio (PR)
    # Nota: Se requiere la potencia nominal del sistema (PnomPV) que no está en los datos
    # Por ahora se calcula con un valor estimado o se deja en 0
    pnom_pv_kw = 50.0  # Valor estimado, debería venir de configuración del sistema
    if irradiance_values:
        # Calcular irradiancia acumulada diaria
        irradiance_accumulated = sum(irradiance_values) * delta_t / 1000  # kWh/m²
        reference_energy_kwh = irradiance_accumulated * pnom_pv_kw

        if reference_energy_kwh > 0:
            performance_ratio_pct = (total_generated_energy_kwh / reference_energy_kwh) * 100
        else:
            performance_ratio_pct = 0
    else:
        reference_energy_kwh = 0
        performance_ratio_pct = 0

    # 4.4. Curva de Generación vs. Irradiancia/Temperatura
    avg_irradiance_wm2 = sum(irradiance_values) / len(irradiance_values) if irradiance_values else 0
    avg_temperature_c = sum(temperature_values) / len(temperature_values) if temperature_values else 0
    max_power_w = max(ac_power_values) if ac_power_values else 0
    min_power_w = min(ac_power_values) if ac_power_values else 0

    # 4.5. Factor de Potencia y Calidad de Inyección
    avg_power_factor_pct = sum(power_factor_values) / len(power_factor_values) if power_factor_values else 0
    avg_reactive_power_var = sum(reactive_power_values) / len(reactive_power_values) if reactive_power_values else 0
    avg_apparent_power_va = sum(apparent_power_values) / len(apparent_power_values) if apparent_power_values else 0
    avg_frequency_hz = sum(frequency_values) / len(frequency_values) if frequency_values else 0

    # Calcular estabilidad de frecuencia
    if len(frequency_values) > 1:
        frequency_std = statistics.stdev(frequency_values)
        frequency_stability_pct = max(0, 100 - (frequency_std / avg_frequency_hz * 100)) if avg_frequency_hz > 0 else 0
    else:
        frequency_stability_pct = 0

    # 4.6. Desbalance de Fases en Inyección
    max_voltage_unbalance_pct = 0
    max_current_unbalance_pct = 0

    if voltage_phases:
        voltage_unbalances = []
        for v_phases in voltage_phases:
            v_avg = sum(v_phases) / 3
            max_deviation = max(abs(v - v_avg) for v in v_phases)
            unbalance_pct = (max_deviation / v_avg) * 100 if v_avg > 0 else 0
            voltage_unbalances.append(unbalance_pct)
        max_voltage_unbalance_pct = max(voltage_unbalances) if voltage_unbalances else 0

    if current_phases:
        current_unbalances = []
        for c_phases in current_phases:
            c_avg = sum(c_phases) / 3
            # GATE de carga mínima: por debajo de MIN_CURRENT_A_FOR_UNBALANCE la
            # inyección es despreciable y el denominador (c_avg) casi 0 dispara la
            # fórmula NEMA sin sentido físico (hasta 200% con una fase en 0.0 A). Se
            # excluye la muestra del cálculo del máximo diario en vez de solo evitar
            # la división por 0.
            if c_avg < MIN_CURRENT_A_FOR_UNBALANCE:
                continue
            max_deviation = max(abs(c - c_avg) for c in c_phases)
            unbalance_pct = (max_deviation / c_avg) * 100
            current_unbalances.append(unbalance_pct)
        # Tope defensivo (mismo estilo que el clamp de dc_ac_efficiency_pct, ver 4.1):
        # incluso tras el gate, se acota a 100% en profundidad ante datos anómalos no
        # contemplados. Si todas las muestras del día quedaron excluidas por el gate
        # (inyección nula todo el día), no hay `current_unbalances` y el valor diario
        # queda en 0 (consistente con "sin datos").
        max_current_unbalance_pct = min(max(current_unbalances), 100.0) if current_unbalances else 0

    # 4.7. Análisis de Anomalías Operativas
    anomaly_score = 0
    anomaly_details = {}

    # Detectar anomalías basadas en umbrales
    if dc_ac_efficiency_pct < 80:  # Eficiencia muy baja
        anomaly_score += 20
        anomaly_details['low_efficiency'] = f"Eficiencia DC-AC muy baja: {dc_ac_efficiency_pct:.1f}%"

    if max_voltage_unbalance_pct > 5:  # Desbalance de tensión alto
        anomaly_score += 15
        anomaly_details['voltage_unbalance'] = f"Desbalance de tensión alto: {max_voltage_unbalance_pct:.1f}%"

    if max_current_unbalance_pct > 10:  # Desbalance de corriente alto
        anomaly_score += 15
        anomaly_details['current_unbalance'] = f"Desbalance de corriente alto: {max_current_unbalance_pct:.1f}%"

    if frequency_stability_pct < 90:  # Inestabilidad de frecuencia
        anomaly_score += 10
        anomaly_details['frequency_instability'] = f"Baja estabilidad de frecuencia: {frequency_stability_pct:.1f}%"

    # Normalizar puntuación de anomalías a 0-100
    anomaly_score = min(100, anomaly_score)

    return {
        'dc_ac_efficiency_pct': dc_ac_efficiency_pct,
        'energy_ac_daily_kwh': energy_ac_daily_kwh,
        'energy_dc_daily_kwh': energy_dc_daily_kwh,
        'total_generated_energy_kwh': total_generated_energy_kwh,
        'performance_ratio_pct': performance_ratio_pct,
        'reference_energy_kwh': reference_energy_kwh,
        'avg_irradiance_wm2': avg_irradiance_wm2,
        'avg_temperature_c': avg_temperature_c,
        'max_power_w': max_power_w,
        'min_power_w': min_power_w,
        'avg_power_factor_pct': avg_power_factor_pct,
        'avg_reactive_power_var': avg_reactive_power_var,
        'avg_apparent_power_va': avg_apparent_power_va,
        'avg_frequency_hz': avg_frequency_hz,
        'frequency_stability_pct': frequency_stability_pct,
        'max_voltage_unbalance_pct': max_voltage_unbalance_pct,
        'max_current_unbalance_pct': max_current_unbalance_pct,
        'anomaly_score': anomaly_score,
        'anomaly_details': anomaly_details,
    }
