# Plan de auditoría y remediación de KPIs (4 pantallas)

**Fecha:** 2026-07-11 · **Origen:** estudio multiagente (4 inventario + 3 lentes + síntesis).
**Alcance aprobado:** paquete **frontend completo** (bugs + reemplazos + info-al-click + módulo
compartido). Backend queda como backlog documentado. Decisiones de producto aprobadas:
reemplazar tarjetas vacías de Inversores por dato real; fusionar HSP en Irradiancia.

## Principio transversal
**Nunca mostrar un 0 fijo como si fuera una medición.** Si un KPI sale 0: (a) poblar con el
campo existente, (b) reemplazar por un indicador equivalente con dato, o (c) quitar. Distinguir
además "0 real" de "no medido" (N/A) y "0 por error de SCADA" (≠ planta apagada).

## Info-al-click (transversal a las 4 pantallas)
Hoy `getKpiDetailedInfo` es una ficha estática, duplicada en 3 pantallas, **ausente en Inversores**
(→ crash al click), con textos **fácticamente falsos** ("cada 5 minutos", "sensores locales",
temperatura "máx/mín", FP "P/S"). Remediación:
- **Centralizar** en `frontend/src/utils/kpiInfo.js` (un diccionario por pantalla + helper).
- Esquema de bloques: **Definición · Cómo se calcula (fórmula real + unidad) · Unidad ·
  Interpretación/umbral**. El bloque de interpretación/umbral hoy no existe; subir las bandas
  cualitativas que el backend ya calcula (kpi.py: Óptimo/Alto/Bajo; Superávit/Déficit).

## Cambios por pantalla (frontend)

### Inicio (Dashboard.js)
- `averageInstantaneousPower`: **bug** doble división `/1000` en comparativo mes anterior (~1138).
- `irradiance`: **eliminar código muerto** que fuerza `'N/A'` (backend ya la envía; ~245, 436-447).
- Reescribir info-al-click de las 9 tarjetas; rotular Consumo como **NETO**.

### Medidores (ElectricalDetails.js)
- `Demanda Pico`: **bug** usa `results[0]`; cambiar a `Math.max(...results.map(peak_demand_kw))`
  + fecha del máximo.
- `Factor de Carga` / `Factor de Potencia`: recomputar sobre el rango o rotular "último día";
  corregir texto falso del FP.
- Renombrar "Energía Total Consumida" → **"Energía importada de la red"** (BRUTA; distinta del
  Consumo NETO del inicio).

### Inversores (InverterDetails.js)
- **P0:** definir/importar `getKpiDetailedInfo` (hoy `ReferenceError` al click en cualquier tarjeta).
- **Factor de Potencia:** leer `avg_power_factor_pct` (hoy lee `avg_power_factor` → 0). Fix 1 línea.
- **Performance Ratio → "Potencia Máxima"** (`max_power_w`). PR es irreparable (sin irradiancia).
- **THD Voltaje → "Desbalance de Corriente"** (`max_current_unbalance_pct`). THD no existe en el modelo.
- "Estabilidad Frecuencia" → **"Frecuencia Promedio"** (`avg_frequency_hz`) + desviación vs 60 Hz.
- Eficiencia DC/AC: nota de saturación (dcPower<acPower en ~92% de filas).

### Estaciones (WeatherStationDetails.js)
- **Dirección del Viento:** **bug** lee `wind_direction_deg` (inexistente) → siempre "N".
  Usar `wind_direction_distribution` (argmax; "N/A" si vacío).
- **HSP:** fusionar en Irradiancia ("X kWh/m² ≈ X HSP"), liberar slot.
- Potencia FV teórica: unificar fórmula frontend (20%/1.6m²) con backend (17%/1m²).
- Viento/Precipitación: distinguir "0 real" de "sin sensor" (N/A); corregir texto "suma".

## Backlog backend (deprioritizado, alto valor)
- Disponibilidad % de flota (barata: deriva de `summarize_inverter_status`).
- Temperatura ambiente en pantalla de Estaciones (`Avg(temperature)` ya existe en backend).
- Rendimiento específico kWh/kWp, PR real de flota, Factor de planta (requieren P_nominal_kWp + POA).
- Temperatura de módulo (Tmod), THD/reactiva reales (dependen del connector SCADA).
