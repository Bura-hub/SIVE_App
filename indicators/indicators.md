# Cálculo de los indicadores energéticos

Este documento describe cómo calcula SIVE cada indicador a partir de las lecturas que llegan cada dos minutos de los
medidores, los inversores y las estaciones meteorológicas de las cinco plantas del proyecto: Udenar, Mariana
(Alvernia), UCC, HUDN y Cesmag. Recoge la corrección de octubre de 2026 (hallazgos C1 a C22 y decisiones D1 a D12).
El detalle de cada hallazgo, con sus cifras de antes y después, está en
`docs/superpowers/specs/2026-10-10-correccion-ingesta-e-indicadores-design.md`.

Cuando este documento y el código no coincidan, manda el código. Los archivos citados están bajo `indicators/`.

---

## 0. Convenciones comunes

- **Paso de integración.** Δt = 2/60 h (2 minutos). Una hora completa tiene 30 lecturas y un día, 720. Energía =
  Σ P·Δt. La potencia del medidor (`totalActivePower`) viene en kW; la del inversor (`acPower`), en W.
- **Hora de Bogotá (C7).** Las horas y los días de gráficas, agregados y rangos se toman en `America/Bogota`, no en
  UTC. Antes había 5 h de desfase y el mensual de clima partía cada día a las 19:00.
- **Un dato que falta no es 0 (C9).** Una columna NULL se descarta del cálculo (`services/rows.py`). Lo que no se pudo
  calcular queda en NULL y la pantalla lo muestra como «No disponible», nunca como 0.
- **Huecos (D3).** Una lectura que no llegó no suma energía. La única reposición es la de C21 para la generación por
  hora (ver §1). La cobertura (lecturas presentes frente a esperadas) se informa junto a la cifra.
- **Configuración de las plantas.** `institution_config.py` dice, por institución, qué medidor da la demanda y de qué
  tipo es, qué inversor da la generación, desde y hasta cuándo cuenta cada inversor, la estación meteorológica, si
  esa estación es apta para el PR, el comercializador y la capacidad (17,55 kWp por planta, D4). Es la misma
  convención de la tesis y del mercado P2P.

---

## 1. Energía horaria por institución

`services/institution_energy.py` construye, para cada hora de Bogotá, la generación G, la demanda D, la exportación y
el autoconsumo de una institución (D2). La usan el inicio (Dashboard), los Indicadores Solares, el ahorro y el PR de
las dos pantallas. La energía de la pantalla Inversores sale de la misma regla por hora (§3).

- **Generación G.** Suma de la energía de los inversores de generación vigentes ese día. Por inversor y hora:
  - E = máx(Σ acPower, 0) × Δt / 1000, en kWh;
  - **C21:** si la hora tiene entre 15 y 29 de sus 30 lecturas, las que faltan se reponen con la media de las
    presentes (E × 30/n), como la tesis. Con menos de 15 rige «faltante = 0», como el mercado P2P. Así una RPi que
    pierde lecturas sueltas no se lee como menos generación;
  - en Udenar, antes del 2025-09-03, G = Fronius 1 × 1,2054 (el Inversor MTE no existía; CAL-44).
- **Demanda D (C10).** Del Medidor 1 de la institución, no de la suma de todos sus medidores (M2 a M5 son circuitos
  parciales que se solapan). La hora vale si el medidor tiene al menos 15 de 30 lecturas; si no, D queda en NULL.
  - Medidor bruto (`gross`: HUDN y Cesmag): D = máx(0, P_M1).
  - Medidor neto (`net` y `net_partial`: Udenar, Mariana y UCC): D = máx(0, P_M1 + Σ inversores aguas abajo).
- **Exportación y autoconsumo (D10).** En medidores netos, exportación = parte negativa de P_M1 y autoconsumo =
  máx(0, G − exportación). En medidores brutos la exportación no se puede medir y se toma 0: todo lo generado se
  autoconsume.

La energía de cada mes se guarda en caché (26 h para los meses cerrados, 10 min para el mes en curso). La tarea
`warm_solar_cache` la renueva cada noche y la reconciliación borra la de los meses que ganan lecturas.

---

## 2. Medidores (electricMeter)

`services/meter_calc.py`. Se calculan por día y por mes sobre las lecturas del periodo.

- **Energía importada y exportada (C17).** Integración de la potencia activa:
  E_imp = Σ máx(P, 0)·Δt y E_exp = Σ máx(−P, 0)·Δt, con P = `totalActivePower` en kW. Antes salía de los registros
  acumulados, que en varios medidores están desescalados por la razón del TC (tesis H-16). La energía del mes es la
  suma exacta de la de sus días.
- **Energía neta.** E_neta = E_imp − E_exp.
- **Demanda pico (C18).** La mayor media de los bloques de reloj de 15 min (:00, :15, :30, :45) que tienen al menos
  4 lecturas. Antes era una media móvil de 7 muestras por posición, que a través de un hueco mezclaba lecturas
  separadas por horas.
- **Demanda media y factor de carga.** Demanda media = media de `totalActivePower` del periodo.
  FC = demanda media / demanda pico × 100 %, acotado a 0–100 %.
- **Factor de potencia (C19).** Media de |FP|. El FP del medidor viene con signo (el signo indica el sentido del
  flujo) y promediarlo con signo cancelaba valores.
- **Desbalance de fases.** DU = máx(|X_fase − X_prom|) / X_prom × 100 %, con X tensión o corriente por fase. Se informa
  el máximo del periodo. En corriente solo cuentan las lecturas con corriente media ≥ 1 A (con carga casi nula la
  fórmula llegaba al 200 %) y el resultado se acota a 100 %.
- **THD y TDD.** Máximo del periodo de los valores que da el medidor (`voltageTHDPhaseA/B/C`,
  `currentTHDPhaseA/B/C`, `currentTDDPhaseA/B/C`). El TDD de corriente, solo con corriente media ≥ 1 A. El THD de
  corriente, por fase y solo si la fundamental estimada, I_rms / √(1 + (THD/100)²), llega a 1 A (`31edea7`): con FV detrás
  del medidor la fundamental neta cae casi a cero a mediodía y el THD se disparaba hasta 999,9 %. Aun así sigue por encima
  del 100 % a baja carga neta, por lo que el reporte «Calidad de Potencia» da el TDD (`80535b5`).
- **«Todos» los medidores (C20).** La demanda media del conjunto es la suma de las medias; el pico, la suma de los
  picos de cada medidor (una cota superior, porque los picos no tienen por qué coincidir); el FC, Σ medias / Σ picos.
  Las energías se suman, el FP se promedia y los desbalances, THD y TDD toman el máximo.

---

## 3. Inversores (inverter)

`services/inverter_calc.py` y la tarea `calculate_inverter_indicators`. Se calculan por día y por mes.

- **Energía generada.** Es la misma energía horaria que la generación de Indicadores Solares (§1,
  `energia_inversor_hora_kwh` y `horas_inversor`): por hora de Bogotá, E = máx(Σ acPower, 0) × Δt / 1000, con la
  reposición de C21 si la hora tiene entre 15 y 29 lecturas y «faltante = 0» con menos. La energía del día o del mes
  (`energy_ac_daily_kwh` y `total_generated_energy_kwh`) es la suma de sus horas, y una hora sin lecturas aporta 0,
  como en Indicadores Solares. La energía DC (`energy_dc_daily_kwh`, una sola entrada MPPT) sigue la misma regla.
  Para una planta y un día o mes en que su inversor de generación es el vigente, Inversores e Indicadores Solares dan
  la misma generación (`tests/test_energia_inversor_igual_solar.py`). Hasta el 21-oct-2026 era Σ acPower·Δt / 1000
  de todo el periodo, sin reponer ni recortar las horas negativas.
- **Gráfica horaria (C5 y C7).** Energía de cada hora de Bogotá con la misma regla (C21 incluida); su suma es la
  energía del día. Antes era la media horaria × Δt, la energía de una sola lectura: 30 veces menos. Una hora sin
  lecturas queda en NULL (no medida) en la gráfica. La corrida mensual ya no escribe la gráfica (pisaba la del día 1).
  El detalle horario (`HourlyInverterIndicators.energy_ac_kwh`) usa la misma regla.
- **Frecuencia (C1).** Media de `acFrequency` solo con lecturas en que el inversor genera (acFrequency > 0 y
  acPower > 0). De noche reporta 0 Hz y eso hundía la media (HUDN: 54,4 Hz con todas, 59,99 Hz generando). La
  estabilidad de frecuencia usa las mismas lecturas.
- **Factor de potencia (C2 y D7).** Media de |powerFactor|/100 mientras genera, en escala 0 a 1. El inversor lo
  reporta en % con signo.
- **Eficiencia DC/AC (C3 y D6).** No se calcula. `dcPower` mide una sola de las entradas MPPT (DC/AC ≈ 0,55 en el HUDN),
  así que P_AC/P_DC no es la eficiencia. Queda en NULL con su motivo.
- **Desbalance de corriente inyectada.** Igual que en los medidores, con `acCurrentPhaseA/B/C` y la misma condición
  de 1 A.
- **Irradiancia y temperatura.** El inversor no las mide: quedan en NULL.

### 3.1 Performance Ratio (C4, D5, C21, C22)

PR = Σ E_AC_día / Σ (H_día × kWp / 1 kW/m²), sobre los días válidos del periodo.

- **H** es la irradiación diurna de la estación de la institución: lecturas de 06:00 a 17:59 entre 0 y 1400 W/m²,
  × Δt / 1000, en kWh/m². La estación mide en plano horizontal (GHI), así que es un PR con irradiancia horizontal.
- **E_AC_día** es la energía del día con la reposición de C21 (§1).
- **Un día cuenta** si cumple todo esto:
  1. la estación tiene al menos el 80 % de sus 360 lecturas diurnas y H ≤ 8 kWh/m²;
  2. la estación coincide con la de referencia (Alvernia, Mariana) a ±25 % ese día, y la mediana de la razón diaria
     estación/referencia de su mes queda a ±10 %, con al menos 5 días para contrastar (C22). Esto no se aplica a la
     propia estación de referencia;
  3. el inversor tiene lectura en al menos el 80 % de las 12 horas de sol.
- **Sin PR:** si la estación no es apta (Udenar: 7 a 12 kWh/m²/día, está descalibrada, C16), si no está en SIVE, si el
  inversor no es la generación de una planta o si ningún día cumple las condiciones. El motivo queda en
  `performance_ratio_note` y los días usados, en `performance_ratio_valid_days`.

**El PR de Inversores y el de Indicadores Solares son el mismo.** Los dos clasifican los días con
`institution_energy.dias_pr` y usan la misma irradiación (`irradiacion_diaria`) y la misma energía por hora
(`energia_inversor_hora_kwh`). Cada planta tiene un único inversor de generación, así que para la misma planta y el
mismo periodo dan la misma cifra (`tests/test_pr_inversor_igual_solar.py`); la energía también coincide (§3). La pantalla Inversores guarda un PR por
día y uno por mes; Indicadores Solares lo calcula al vuelo para cualquier rango.

---

## 4. Estaciones meteorológicas (weatherStation)

`services/weather_calc.py`. Antes de calcular se descartan las lecturas fuera de rango físico: temperatura de −20 a
60 °C, humedad de 0 a 100 %, viento de 0 a 150 km/h, dirección de 0 a 360° y precipitación no negativa.

- **Irradiación diaria (C6).** Σ irradiancia·Δt / 1000, en kWh/m², con las lecturas de 06:00 a 17:59 entre 0 y
  1100 W/m². Fuera de ese horario, un valor alto es un sensor pegado. (El PR usa un tope de 1400 W/m², §3.1.)
- **Horas solares pico.** HSP = irradiación diaria / 1 kW/m² (1 HSP = 1 kWh/m²).
- **Potencia FV teórica.** Irradiancia media del día × 0,17: lo que daría 1 m² de módulo con 17 % de eficiencia, en W.
- **Viento.** Velocidad media del periodo y rosa de los vientos. En la vista horaria, la dirección es la media
  circular (350° y 10° dan 0°, no 180°).
- **Precipitación.** El sensor la acumula por día: el valor diario es la última lectura del día y el mensual, la suma
  de los diarios.
- **Mensual.** Media de los valores diarios para irradiación, HSP, viento, temperatura y humedad; suma para la
  precipitación; máximo y mínimo para la temperatura.
- **«Todas» las estaciones (C8).** La irradiación, las HSP y la precipitación se promedian entre estaciones (antes se
  sumaban).
- **Estación de Udenar (C16).** Descalibrada: se muestra con aviso y no se usa para el PR ni para la irradiancia del
  inicio.

---

## 5. Indicadores Solares por institución

`services/solar_kpis.py`, endpoint `GET /api/solar-indicators/`. Se calculan al vuelo desde la energía horaria (§1),
por día, mes o año, y para el total del rango.

- **Generación** y **generación acumulada** (kWh).
- **Rendimiento específico** = G / kWp, en kWh/kWp.
- **Factor de capacidad** = G / (kWp × horas del periodo).
- **Frente al diseño** = G / (59,4 kWh/día × días). El diseño supone 4,5 kWh/m²/día y 20 % de pérdidas (D11).
- **Performance Ratio:** §3.1.
- **Demanda, demanda media y pico horario** del circuito del Medidor 1, solo en las horas válidas del medidor.
- **Cobertura solar** = G de las horas con medidor válido / D.
- **Autoconsumo y exportación** (D10). La generación de las horas sin medidor válido se informa aparte.
- **Ahorro (D8 y C13)** = energía autoconsumida × CU mensual del comercializador (ASC nivel 2 para Udenar, Mariana,
  UCC y HUDN; Cedenar nivel 2 para Cesmag; `data/tarifas_cu.csv`). Un mes sin tarifa publicada usa la última
  anterior y se marca como tarifa extrapolada.
- **CO₂ evitado (D9)** = G × 0,112 kgCO₂/kWh (factor del SIN, UPME Res. 0705/2024). Árboles equivalentes: 545 por cada
  12 t.
- **Disponibilidad de datos** = horas de sol con lectura del inversor / horas de sol. **Cobertura de lecturas** =
  lecturas diurnas presentes / esperadas.

El ahorro diario de la pantalla de datos externos (`external_energy/tasks.py`, `calculate_energy_savings`) usa la misma
energía y las mismas tarifas, suma las instituciones y recalcula los últimos 40 días en cada corrida.

---

## 6. Inicio (Dashboard)

La tarea `calculate_monthly_consumption_kpi` guarda los valores en `MonthlyConsumptionKPI`, y
`GET /api/dashboard/summary/` los sirve.

- **Ventanas (C11).** El mes en curso va del día 1 a las 00:00 hasta ahora; el mes anterior, del día 1 a las 00:00
  hasta el mismo tiempo transcurrido. Antes se comparaba con el mes anterior hasta el mismo día completo y la
  comparación salía sesgada a la baja.
- **Demanda de los circuitos medidos** = Σ D de las plantas (§1), solo en horas válidas del medidor.
- **Energía tomada de la red** = Σ (D − autoconsumo).
- **Generación de las plantas** = Σ G.
- **Balance** = generación − demanda.
- **Potencia media de la flota** = G × 1000 / horas transcurridas, en W, noches incluidas.
- **Clima.** Medias de todas las estaciones con rangos físicos: temperatura de −10 a 45 °C, humedad de 0 a 100 % y
  viento de 0 a 150 km/h. La irradiancia es la media diurna (06:00 a 17:59, 0 a 1400 W/m²) de las estaciones aptas.
- **Inversores con datos (C12).** Inversores de generación vigentes con lecturas en SIVE en las últimas 24 h, sobre el
  total de inversores vigentes. No cuenta los de prueba ni los Fronius de Udenar retirados el 2026-04-11, y no es un
  dato en vivo del conector.

---

## 7. Ingesta y recálculo (D1 y C15)

- Cada hora se descargan las últimas 3 h y se recalculan los indicadores del día y del mes en curso y el rollup
  horario.
- **Reconciliación (D1).** Cada noche se comparan, por dispositivo y día, los conteos de SIVE con los del conector en
  una ventana de 35 días; cada 6 h, los de los últimos 2 días. Los días distintos se vuelven a descargar y se
  recalculan sus indicadores diarios, los mensuales de sus meses, la gráfica diaria, el rollup horario y el KPI
  mensual. Así entran las lecturas que las RPi envían con retraso.
- **Ayer completo (C15).** A las 00:40 se recalcula siempre el día anterior completo para todos los dispositivos.
- Todos los cálculos son idempotentes (`update_or_create`). Para recalcular un histórico tras un cambio de fórmula,
  `scripts/recalcular_historico.sh DESDE HASTA` o los comandos `calculate_historical_*` de
  `indicators/management/commands/`.

---

## 8. Índice de la corrección de octubre de 2026

| Código | Qué corrige | Dónde |
|---|---|---|
| C1 | Frecuencia del inversor solo mientras genera | `services/inverter_calc.py` |
| C2, D7 | FP del inversor como media de \|FP\|/100 mientras genera | `services/inverter_calc.py` |
| C3, D6 | Eficiencia DC/AC no disponible | `services/inverter_calc.py` |
| C4, D5 | Performance Ratio con la estación de la institución | `services/institution_energy.py`, `tasks.py` |
| C5 | Energía horaria de la gráfica del inversor | `services/inverter_calc.py` |
| C6 | Irradiación de la gráfica diaria de la estación | `services/weather_calc.py` |
| C7 | Horas y días en hora de Bogotá | `services/inverter_calc.py`, `services/weather_calc.py` |
| C8 | «Todas» las estaciones promedian, no suman | `views.py` |
| C9 | NULL ya no es 0 | `services/rows.py` |
| C10, D2 | Demanda del Medidor 1 por institución | `services/institution_energy.py` |
| C11 | Ventanas con el mismo tiempo transcurrido | `tasks.py` |
| C12 | Inversores con datos en las últimas 24 h | `services/kpi.py`, `views.py` |
| C13, D8 | Ahorro con el CU del comercializador | `services/solar_kpis.py`, `external_energy/tasks.py` |
| C14 | Unidades de XM en pantalla | frontend |
| C15, D1 | Reconciliación y recálculo del día anterior | `scada_proxy/tasks.py` |
| C16 | Estación de Udenar no apta | `institution_config.py` |
| C17 | Energía del medidor por integración de la potencia | `services/meter_calc.py` |
| C18 | Demanda pico por bloques de reloj de 15 min | `services/meter_calc.py` |
| C19 | FP del medidor como media de \|FP\| | `services/meter_calc.py` |
| C20 | «Todos» los medidores: suma de medias y de picos | `views.py` |
| C21 | Reposición de lecturas sueltas en horas casi completas | `services/institution_energy.py` |
| C22 | Contraste de la estación con la de referencia | `services/institution_energy.py`, `institution_config.py` |
| D3 | Faltante = 0 y cobertura declarada | `services/institution_energy.py` |
| D4, D9, D11 | Capacidad, factor de CO₂ y diseño | `institution_config.py` |
| D10 | Autoconsumo y exportación por tipo de medidor | `services/institution_energy.py` |
| D12 | Lectura pública (modo invitado) | `core/permissions.py`, `core/throttling.py` |
