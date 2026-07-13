"""
Cálculo PURO de indicadores de un medidor eléctrico (Ola 5).

Extraído de la task `calculate_electric_meter_indicators`: recibe un iterable de filas
dict (`.values(*METER_FIELDS)`) y devuelve el dict de indicadores calculados, sin tocar
la BD ni Celery. La task queda como envoltorio (query + update_or_create).

`measurement_count` y `last_measurement_date` NO se calculan aquí (dependen del queryset).
"""
from indicators.energy import consumption_energy_kwh
from indicators.services.rows import _row_get
from indicators.services.sanitize import (
    ROLLOVER_CAP_FACTOR,
    ROLLOVER_CAP_MARGIN_KWH,
    _accumulate_register_energy,
)

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
    'importedActivePowerLow', 'importedActivePowerHigh',
    'exportedActivePowerLow', 'exportedActivePowerHigh',
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
    # Energía acumulada (primer/último): heredado; hoy no interviene en el resultado
    # (la energía sale del saneamiento de la serie de registros), se conserva verbatim.
    imported_energy_low_start = None
    imported_energy_high_start = None
    exported_energy_low_start = None
    exported_energy_high_start = None

    imported_energy_low_end = None
    imported_energy_high_end = None
    exported_energy_low_end = None
    exported_energy_high_end = None

    total_active_power_values = []
    # Series ordenadas de los registros acumulados (para el saneamiento anti roll-over)
    import_register_totals = []
    export_register_totals = []
    power_factor_values = []
    voltage_phases = []
    current_phases = []
    voltage_thd_values = []
    current_thd_values = []
    current_tdd_values = []

    for data in rows:
        # Energía acumulada (primer y último valor)
        if imported_energy_low_start is None:
            imported_energy_low_start = _row_get(data, 'importedActivePowerLow')
            imported_energy_high_start = _row_get(data, 'importedActivePowerHigh')
            exported_energy_low_start = _row_get(data, 'exportedActivePowerLow')
            exported_energy_high_start = _row_get(data, 'exportedActivePowerHigh')

        imported_energy_low_end = _row_get(data, 'importedActivePowerLow')
        imported_energy_high_end = _row_get(data, 'importedActivePowerHigh')
        exported_energy_low_end = _row_get(data, 'exportedActivePowerLow')
        exported_energy_high_end = _row_get(data, 'exportedActivePowerHigh')

        # Serie ordenada de registros acumulados para el saneamiento (solo
        # lecturas con valor real; NULL se omite para no fabricar deltas falsos).
        imp_high, imp_low = data['importedActivePowerHigh'], data['importedActivePowerLow']
        if imp_high is not None and imp_low is not None:
            import_register_totals.append(imp_high * 1000 + imp_low)
        exp_high, exp_low = data['exportedActivePowerHigh'], data['exportedActivePowerLow']
        if exp_high is not None and exp_low is not None:
            export_register_totals.append(exp_high * 1000 + exp_low)

        # Potencia activa para demanda pico
        total_active_power = _row_get(data, 'totalActivePower')
        if total_active_power is not None:
            total_active_power_values.append(total_active_power)

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

        current_thd_a = _row_get(data, 'currentTHDPhaseA')
        current_thd_b = _row_get(data, 'currentTHDPhaseB')
        current_thd_c = _row_get(data, 'currentTHDPhaseC')
        if (
            row_current_avg >= MIN_CURRENT_A_FOR_UNBALANCE
            and all(thd is not None for thd in [current_thd_a, current_thd_b, current_thd_c])
        ):
            current_thd_values.extend([current_thd_a, current_thd_b, current_thd_c])

        current_tdd_a = _row_get(data, 'currentTDDPhaseA')
        current_tdd_b = _row_get(data, 'currentTDDPhaseB')
        current_tdd_c = _row_get(data, 'currentTDDPhaseC')
        if (
            row_current_avg >= MIN_CURRENT_A_FOR_UNBALANCE
            and all(tdd is not None for tdd in [current_tdd_a, current_tdd_b, current_tdd_c])
        ):
            current_tdd_values.extend([current_tdd_a, current_tdd_b, current_tdd_c])

    # 3.2. Energía Consumida Acumulada (SANEADA contra roll-over/reset del contador).
    # La energía integrada de la potencia (Σ|P|·Δt) es fiable y acota los saltos:
    # un incremento de registro que la supere ampliamente es un glitch, no consumo.
    pos_power_sum = sum(p for p in total_active_power_values if p and p > 0)
    neg_power_sum = sum(-p for p in total_active_power_values if p and p < 0)
    integrated_import_kwh = consumption_energy_kwh(pos_power_sum)
    integrated_export_kwh = consumption_energy_kwh(neg_power_sum)
    import_cap = ROLLOVER_CAP_FACTOR * integrated_import_kwh + ROLLOVER_CAP_MARGIN_KWH
    export_cap = ROLLOVER_CAP_FACTOR * integrated_export_kwh + ROLLOVER_CAP_MARGIN_KWH

    imported_energy_kwh = _accumulate_register_energy(import_register_totals, import_cap)
    exported_energy_kwh = _accumulate_register_energy(export_register_totals, export_cap)
    net_energy_consumption_kwh = imported_energy_kwh - exported_energy_kwh

    # 3.3. Demanda Pico
    if total_active_power_values:
        # Calcular demanda pico usando promedio móvil de 15 minutos
        # Como tenemos datos cada 2 minutos, 15 minutos = 7-8 mediciones
        window_size = 7
        moving_averages = []
        for i in range(len(total_active_power_values) - window_size + 1):
            window_avg = sum(total_active_power_values[i:i+window_size]) / window_size
            moving_averages.append(window_avg)

        peak_demand_kw = max(moving_averages) if moving_averages else max(total_active_power_values)
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
    if power_factor_values:
        avg_power_factor = sum(power_factor_values) / len(power_factor_values)
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
