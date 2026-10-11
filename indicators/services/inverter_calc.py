"""
Cálculo PURO de indicadores de un inversor (Ola 5).

Extraído de la task `calculate_inverter_indicators`: recibe un iterable de filas dict
(`.values(*INVERTER_FIELDS)`) y devuelve el dict de indicadores calculados, sin tocar la
BD ni Celery. La task queda como envoltorio (query + update_or_create de InverterIndicators
y de InverterChartData). `measurement_count`/`last_measurement_date` NO se calculan aquí.
"""
import statistics
from collections import defaultdict

from indicators.energy import SAMPLE_INTERVAL_HOURS
from indicators.services.date_ranges import COLOMBIA_TZ
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

        generating = ac_power is not None and ac_power > 0

        # Factor de potencia (C2/D7): `powerFactor` viene en % con signo (−100..100). Se usa
        # |FP|/100 (escala 0–1) y solo mientras el inversor genera: de noche el FP no significa
        # nada (HUDN: la media cruda daba −41,3).
        power_factor = _row_get(data, 'powerFactor')
        if power_factor is not None and generating:
            power_factor_values.append(abs(power_factor) / 100.0)

        # Frecuencia (C1): solo muestras con acFrequency > 0 y acPower > 0. De noche el inversor
        # reporta 0 Hz y esas muestras hundían la media (HUDN: 54,4 Hz con todas; 59,99 generando).
        frequency = _row_get(data, 'acFrequency')
        if frequency is not None and frequency > 0 and generating:
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

        # La categoría 'inverter' no mide irradiancia ni temperatura: avg_irradiance_wm2 y
        # avg_temperature_c quedan en None (antes se apendaba un 0 por muestra y se mostraba 0).

    # Calcular indicadores

    # Δt (h) de la integración de potencia. Se define SIEMPRE al inicio para que
    # esté disponible aunque solo haya irradiancia (antes se definía dentro del
    # if de ac/dc y provocaba NameError al calcular la irradiancia acumulada).
    delta_t = SAMPLE_INTERVAL_HOURS

    # Energía AC (y DC de la única entrada MPPT medida), Σ P·Δt.
    energy_ac_daily_kwh = sum(ac_power_values) * delta_t / 1000 if ac_power_values else 0.0
    energy_dc_daily_kwh = sum(dc_power_values) * delta_t / 1000 if dc_power_values else 0.0

    # 4.1. Eficiencia de conversión DC-AC (C3/D6): NO se calcula. `dcPower` mide una sola entrada
    # MPPT (tesis H-12; DC/AC ≈ 0,55 en el HUDN, y el cociente se recortaba a 100 %). Queda en None.
    dc_ac_efficiency_pct = None

    # 4.2. Energía Total Generada
    total_generated_energy_kwh = energy_ac_daily_kwh

    # 4.3. Performance Ratio (C4/D5): necesita la irradiación de la estación de la institución,
    # que no está en estas filas. Lo calcula `compute_performance_ratio` en la tarea; aquí None.
    performance_ratio_pct = None
    reference_energy_kwh = None

    # 4.4. Curva de generación: el inversor no mide irradiancia ni temperatura.
    avg_irradiance_wm2 = None
    avg_temperature_c = None
    max_power_w = max(ac_power_values) if ac_power_values else 0
    min_power_w = min(ac_power_values) if ac_power_values else 0

    # 4.5. Factor de Potencia y Calidad de Inyección
    # Sin muestras generando no hay FP ni frecuencia: None (no disponible), nunca 0.
    avg_power_factor = sum(power_factor_values) / len(power_factor_values) if power_factor_values else None
    avg_reactive_power_var = sum(reactive_power_values) / len(reactive_power_values) if reactive_power_values else 0
    avg_apparent_power_va = sum(apparent_power_values) / len(apparent_power_values) if apparent_power_values else 0
    avg_frequency_hz = sum(frequency_values) / len(frequency_values) if frequency_values else None

    # Estabilidad de frecuencia, sobre las mismas muestras (generando, f > 0).
    if len(frequency_values) > 1:
        frequency_std = statistics.stdev(frequency_values)
        frequency_stability_pct = max(0, 100 - (frequency_std / avg_frequency_hz * 100))
    else:
        frequency_stability_pct = None

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
        # Tope defensivo: incluso tras el gate, se acota a 100% en profundidad ante datos anómalos no
        # contemplados. Si todas las muestras del día quedaron excluidas por el gate
        # (inyección nula todo el día), no hay `current_unbalances` y el valor diario
        # queda en 0 (consistente con "sin datos").
        max_current_unbalance_pct = min(max(current_unbalances), 100.0) if current_unbalances else 0

    # 4.7. Análisis de Anomalías Operativas
    anomaly_score = 0
    anomaly_details = {}

    # Detectar anomalías basadas en umbrales. La eficiencia DC-AC ya no entra (C3/D6: no se
    # calcula), y la estabilidad de frecuencia solo cuenta si hubo muestras generando (C1).
    if max_voltage_unbalance_pct > 5:  # Desbalance de tensión alto
        anomaly_score += 15
        anomaly_details['voltage_unbalance'] = f"Desbalance de tensión alto: {max_voltage_unbalance_pct:.1f}%"

    if max_current_unbalance_pct > 10:  # Desbalance de corriente alto
        anomaly_score += 15
        anomaly_details['current_unbalance'] = f"Desbalance de corriente alto: {max_current_unbalance_pct:.1f}%"

    if frequency_stability_pct is not None and frequency_stability_pct < 90:  # Inestabilidad de frecuencia
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
        'avg_power_factor': avg_power_factor,
        'avg_reactive_power_var': avg_reactive_power_var,
        'avg_apparent_power_va': avg_apparent_power_va,
        'avg_frequency_hz': avg_frequency_hz,
        'frequency_stability_pct': frequency_stability_pct,
        'max_voltage_unbalance_pct': max_voltage_unbalance_pct,
        'max_current_unbalance_pct': max_current_unbalance_pct,
        'anomaly_score': anomaly_score,
        'anomaly_details': anomaly_details,
    }


# ---------------------------------------------------------------------------------------------
# Energía diaria y Performance Ratio (C4/D5, corrección de octubre de 2026)
# ---------------------------------------------------------------------------------------------

PR_REASON_NO_PLANT = (
    'No disponible: el inversor no es la generación de una planta configurada (sin kWp ni '
    'estación asignada).'
)
PR_REASON_STATION_NOT_APT = (
    'No disponible: la estación meteorológica de {institucion} no es apta para el PR '
    '(irradiación diaria físicamente imposible; está descalibrada).'
)
PR_REASON_NO_STATION = 'No disponible: la estación meteorológica de {institucion} no está en SIVE.'
PR_REASON_NO_VALID_DAYS = (
    'No disponible: ningún día con al menos el 80 % de las muestras diurnas de la estación '
    '(06:00–18:00) y una irradiación de hasta 8 kWh/m².'
)


def bogota_day(ts):
    """Día civil de Bogotá de un datetime aware (las filas de Django vienen en UTC)."""
    return ts.astimezone(COLOMBIA_TZ).date()


def daily_ac_energy_kwh(rows):
    """Energía AC por día de Bogotá, E = Σ acPower·Δt / 1000 (kWh), a partir de filas
    `.values('date', 'acPower')`. Los NULL no cuentan (faltante = 0 en G, D3). Solo aparecen
    los días con alguna muestra."""
    energy = defaultdict(float)
    for row in rows:
        day = bogota_day(row['date'])
        ac = row['acPower']
        energy[day] += 0.0 if ac is None else ac * SAMPLE_INTERVAL_HOURS / 1000.0
    return dict(energy)


def compute_performance_ratio(energy_by_day, irradiation_by_day, kwp):
    """Performance Ratio de un periodo (D5).

        PR = Σ E_AC_día / Σ (H_día × kWp / 1 kW/m²)

    sobre los días válidos: con energía del inversor y con H válida de la estación
    (`irradiation_by_day[día]` = (H en kWh/m², válido: bool), ver
    `weather_calc.daily_irradiation_for_pr`). H es irradiancia horizontal (GHI), así que el PR
    resultante es un PR con irradiancia horizontal.

    Devuelve un dict con `performance_ratio_pct` (o None), `reference_energy_kwh` (Σ H×kWp de los
    días válidos, o None), `performance_ratio_valid_days` y `performance_ratio_note` (motivo
    cuando el PR es None)."""
    valid_days = [
        day for day, (h, ok) in irradiation_by_day.items()
        if ok and day in energy_by_day
    ]
    if not valid_days:
        return {
            'performance_ratio_pct': None,
            'reference_energy_kwh': None,
            'performance_ratio_valid_days': 0,
            'performance_ratio_note': PR_REASON_NO_VALID_DAYS,
        }
    energy = sum(energy_by_day[d] for d in valid_days)
    reference = sum(irradiation_by_day[d][0] * kwp for d in valid_days)
    return {
        'performance_ratio_pct': energy / reference * 100.0,
        'reference_energy_kwh': reference,
        'performance_ratio_valid_days': len(valid_days),
        'performance_ratio_note': None,
    }


def pr_unavailable(note):
    """Resultado de PR no disponible con su motivo."""
    return {
        'performance_ratio_pct': None,
        'reference_energy_kwh': None,
        'performance_ratio_valid_days': 0,
        'performance_ratio_note': note,
    }


# ---------------------------------------------------------------------------------------------
# Gráfica horaria del día (InverterChartData), C5 y C7
# ---------------------------------------------------------------------------------------------

def compute_inverter_hourly_chart(rows):
    """Datos por hora de Bogotá para `InverterChartData`, a partir de filas
    `.values('date', 'acPower', 'dcPower')` de UN día.

    - hourly_generation[h] = Σ acPower·Δt / 1000: la energía real de la hora en kWh (C5; antes
      era la media horaria × Δt, la energía de una sola muestra: 30 veces menos).
    - hourly_ac_power / hourly_dc_power: medias horarias en W.
    - Las horas se toman en hora de Bogotá (C7; antes `date.hour` en UTC, 5 h corridas).
    - Una hora sin muestras queda en None (no medida), no en 0.
    - hourly_efficiency: None (C3/D6, `dcPower` mide una sola entrada MPPT).
    - hourly_irradiance / hourly_temperature: None (el inversor no los mide).
    """
    ac_sum = [0.0] * 24
    ac_n = [0] * 24
    dc_sum = [0.0] * 24
    dc_n = [0] * 24
    for row in rows:
        hour = row['date'].astimezone(COLOMBIA_TZ).hour
        if row['acPower'] is not None:
            ac_sum[hour] += row['acPower']
            ac_n[hour] += 1
        if row['dcPower'] is not None:
            dc_sum[hour] += row['dcPower']
            dc_n[hour] += 1

    return {
        'hourly_efficiency': [None] * 24,
        'hourly_generation': [
            ac_sum[h] * SAMPLE_INTERVAL_HOURS / 1000.0 if ac_n[h] else None for h in range(24)
        ],
        'hourly_irradiance': [None] * 24,
        'hourly_temperature': [None] * 24,
        'hourly_dc_power': [dc_sum[h] / dc_n[h] if dc_n[h] else None for h in range(24)],
        'hourly_ac_power': [ac_sum[h] / ac_n[h] if ac_n[h] else None for h in range(24)],
    }
