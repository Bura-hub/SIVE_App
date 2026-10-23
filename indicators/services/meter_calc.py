"""
Cálculo PURO de indicadores de un medidor eléctrico.

Extraído de la task `calculate_electric_meter_indicators`: recibe un iterable de filas
dict (`.values(*METER_FIELDS)`) y devuelve el dict de indicadores calculados, sin tocar
la BD ni Celery. La task queda como envoltorio (query + update_or_create).

`measurement_count` y `last_measurement_date` NO se calculan aquí (dependen del queryset).
"""
from indicators.energy import consumption_energy_kwh
from indicators.services.date_ranges import COLOMBIA_TZ
from indicators.services.rows import _row_get
import math

# Demanda pico: media de cada bloque de reloj de 15 min (00, 15, 30, 45) con al menos estas muestras (de 7–8).
PEAK_BLOCK_MINUTES = 15
PEAK_BLOCK_MIN_SAMPLES = 4

# Umbral mínimo de corriente promedio (A) para evaluar desbalance/THD/TDD de corriente.
# Por debajo de este umbral la carga es despreciable (equivalente a standby/vacío) y la
# fórmula NEMA de desbalance (max_desviación/promedio×100) se dispara sin sentido físico
# porque el denominador tiende a 0: con una fase en 0.0 A el resultado llega a ~200%. En
# producción ~24% de las lecturas tienen alguna fase de corriente en 0.0 A, así que casi
# todos los medidores superaban el 100% de desbalance sin que hubiera un problema real de
# red. Ajustable: 1.0 A es un valor defendible para medidores de baja/media tensión, pero
# puede recalibrarse si el equipo de campo define un umbral distinto por capacidad nominal.
MIN_CURRENT_A_FOR_UNBALANCE = 1.0

# Columnas v2 que consume el cálculo del medidor.
METER_FIELDS = (
    'date',
    'totalActivePower', 'totalPowerFactor',
    'voltagePhaseA', 'voltagePhaseB', 'voltagePhaseC',
    'currentPhaseA', 'currentPhaseB', 'currentPhaseC',
    'voltageTHDPhaseA', 'voltageTHDPhaseB', 'voltageTHDPhaseC',
    'currentTHDPhaseA', 'currentTHDPhaseB', 'currentTHDPhaseC',
    'currentTDDPhaseA', 'currentTDDPhaseB', 'currentTDDPhaseC',
)


def compute_meter_indicators(rows):
    """Indicadores de un medidor a partir de un iterable de filas dict de `.values()`.
    Puro (no toca la BD). Devuelve el dict de campos calculados."""
    total_active_power_values = []
    power_dates = []
    power_factor_values = []
    voltage_phases = []
    current_phases = []
    voltage_thd_values = []
    current_thd_values = []
    current_tdd_values = []

    for data in rows:
        # Potencia activa para demanda pico
        total_active_power = _row_get(data, 'totalActivePower')
        if total_active_power is not None:
            total_active_power_values.append(total_active_power)
            power_dates.append(data.get('date'))

        # Factor de potencia
        power_factor = _row_get(data, 'totalPowerFactor')
        if power_factor is not None:
            power_factor_values.append(power_factor)

        # Voltajes por fase
        voltage_a = _row_get(data, 'voltagePhaseA')
        voltage_b = _row_get(data, 'voltagePhaseB')
        voltage_c = _row_get(data, 'voltagePhaseC')
        if all(v is not None for v in [voltage_a, voltage_b, voltage_c]):
            voltage_phases.append([voltage_a, voltage_b, voltage_c])

        # Corrientes por fase
        current_a = _row_get(data, 'currentPhaseA')
        current_b = _row_get(data, 'currentPhaseB')
        current_c = _row_get(data, 'currentPhaseC')
        if all(c is not None for c in [current_a, current_b, current_c]):
            current_phases.append([current_a, current_b, current_c])

        # THD y TDD
        voltage_thd_a = _row_get(data, 'voltageTHDPhaseA')
        voltage_thd_b = _row_get(data, 'voltageTHDPhaseB')
        voltage_thd_c = _row_get(data, 'voltageTHDPhaseC')
        if all(thd is not None for thd in [voltage_thd_a, voltage_thd_b, voltage_thd_c]):
            voltage_thd_values.extend([voltage_thd_a, voltage_thd_b, voltage_thd_c])

        # GATE de carga mínima (mismo motivo que el desbalance de corriente, ver
        # MIN_CURRENT_A_FOR_UNBALANCE): con la fundamental de corriente ~0 el THD/TDD
        # de corriente es ruido de instrumentación, no una medida significativa.
        row_current_avg = (
            (current_a + current_b + current_c) / 3
            if all(c is not None for c in [current_a, current_b, current_c])
            else 0
        )

        # El THD se mide contra la FUNDAMENTAL, y la corriente que reporta el medidor es RMS (incluye los
        # armónicos). A mediodía la generación FV compensa la carga en el punto del medidor: la fundamental cae
        # casi a cero mientras los armónicos siguen, y el THD se dispara (hasta 999,9 %) aunque la corriente RMS
        # supere el umbral. Por eso el gate se aplica por fase a la fundamental estimada,
        # I_rms / sqrt(1 + (THD/100)^2), con el mismo umbral de carga mínima.
        for phase in 'ABC':
            i_rms = _row_get(data, f'currentPhase{phase}')
            thd = _row_get(data, f'currentTHDPhase{phase}')
            if i_rms is None or thd is None:
                continue
            fundamental = i_rms / math.sqrt(1 + (thd / 100) ** 2)
            if fundamental >= MIN_CURRENT_A_FOR_UNBALANCE:
                current_thd_values.append(thd)

        current_tdd_a = _row_get(data, 'currentTDDPhaseA')
        current_tdd_b = _row_get(data, 'currentTDDPhaseB')
        current_tdd_c = _row_get(data, 'currentTDDPhaseC')
        if (
            row_current_avg >= MIN_CURRENT_A_FOR_UNBALANCE
            and all(tdd is not None for tdd in [current_tdd_a, current_tdd_b, current_tdd_c])
        ):
            current_tdd_values.extend([current_tdd_a, current_tdd_b, current_tdd_c])

    # 3.2. Energía importada y exportada = integración de la potencia activa (como en el mercado P2P):
    # Σ max(P, 0)·Δt y Σ max(−P, 0)·Δt con P = totalActivePower en kW. Antes salía de los registros acumulados
    # importedActivePower*/exportedActivePower*, que en varios medidores están desescalados por la razón del TC
    # (Mariana M1 ×39,5, HUDN M3 ×38,6, Cesmag M1 y M3 ×78,5) y cuyo saneamiento aceptaba picos de ida
    # y vuelta y tenía un tope que crecía con la ventana (el mensual no era la suma de los diarios). Una lectura
    # que no llegó no suma: la energía del mes es la suma exacta de la de sus días y horas.
    imported_energy_kwh = consumption_energy_kwh(sum(p for p in total_active_power_values if p > 0))
    exported_energy_kwh = consumption_energy_kwh(sum(-p for p in total_active_power_values if p < 0))
    net_energy_consumption_kwh = imported_energy_kwh - exported_energy_kwh

    # 3.3. Demanda pico = máxima media de bloques de reloj de 15 min. Antes: media móvil de 7 muestras por
    # POSICIÓN, que a través de un hueco de datos mezclaba lecturas separadas por horas.
    if total_active_power_values:
        bloques = {}
        for i, (p_kw, fecha) in enumerate(zip(total_active_power_values, power_dates)):
            if fecha is not None:
                local = fecha.astimezone(COLOMBIA_TZ)
                clave = (local.date(), local.hour, local.minute // PEAK_BLOCK_MINUTES)
            else:
                clave = i // 7     # filas sin fecha (solo pruebas unitarias antiguas): bloques de 7 muestras
            acc = bloques.setdefault(clave, [0.0, 0])
            acc[0] += p_kw
            acc[1] += 1
        medias = [s_ / n for s_, n in bloques.values() if n >= PEAK_BLOCK_MIN_SAMPLES]
        peak_demand_kw = max(medias) if medias else max(total_active_power_values)
        avg_demand_kw = sum(total_active_power_values) / len(total_active_power_values)
    else:
        peak_demand_kw = 0
        avg_demand_kw = 0

    # 3.4. Factor de Carga = demanda media / demanda pico (misma serie de potencia).
    # Antes se calculaba net_energy(registros) / (pico(potencia)·horas), que mezclaba
    # dos fuentes distintas: un pico diminuto con energía registrada daba factores
    # imposibles (hasta 220.659%). Con media/pico queda acotado a [0,100] por
    # construcción (la media nunca supera el pico) y es la definición canónica.
    if peak_demand_kw > 0:
        load_factor_pct = min(100.0, max(0.0, (avg_demand_kw / peak_demand_kw) * 100))
    else:
        load_factor_pct = 0

    # 3.5. Factor de Potencia Promedio
    # El FP del medidor viene con signo (el signo indica el sentido del flujo, p. ej. −0,955):
    # promediar con signo cancela valores. Se promedia |FP|.
    if power_factor_values:
        avg_power_factor = sum(abs(pf) for pf in power_factor_values) / len(power_factor_values)
    else:
        avg_power_factor = 0

    # 3.6. Desbalance de Fases
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
            # GATE de carga mínima: por debajo de MIN_CURRENT_A_FOR_UNBALANCE la carga es
            # despreciable y el denominador (c_avg) casi 0 dispara la fórmula NEMA sin
            # sentido físico (hasta 200% con una fase en 0.0 A). Se excluye la muestra del
            # cálculo del máximo diario en vez de solo evitar la división por 0.
            if c_avg < MIN_CURRENT_A_FOR_UNBALANCE:
                continue
            max_deviation = max(abs(c - c_avg) for c in c_phases)
            unbalance_pct = (max_deviation / c_avg) * 100
            current_unbalances.append(unbalance_pct)
        # Tope defensivo (mismo estilo que load_factor_pct, ver 3.4): incluso tras el gate,
        # se acota a 100% en profundidad ante datos anómalos no contemplados. Si todas las
        # muestras del día quedaron excluidas por el gate (carga nula todo el día), no hay
        # `current_unbalances` y el valor diario queda en 0 (consistente con "sin datos").
        max_current_unbalance_pct = min(max(current_unbalances), 100.0) if current_unbalances else 0

    # 3.7. THD y TDD
    max_voltage_thd_pct = max(voltage_thd_values) if voltage_thd_values else 0
    max_current_thd_pct = max(current_thd_values) if current_thd_values else 0
    max_current_tdd_pct = max(current_tdd_values) if current_tdd_values else 0

    return {
        'imported_energy_kwh': imported_energy_kwh,
        'exported_energy_kwh': exported_energy_kwh,
        'net_energy_consumption_kwh': net_energy_consumption_kwh,
        'peak_demand_kw': peak_demand_kw,
        'avg_demand_kw': avg_demand_kw,
        'load_factor_pct': load_factor_pct,
        'avg_power_factor': avg_power_factor,
        'max_voltage_unbalance_pct': max_voltage_unbalance_pct,
        'max_current_unbalance_pct': max_current_unbalance_pct,
        'max_voltage_thd_pct': max_voltage_thd_pct,
        'max_current_thd_pct': max_current_thd_pct,
        'max_current_tdd_pct': max_current_tdd_pct,
    }
