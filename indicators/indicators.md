# Cálculo de los indicadores energéticos

Este documento describe cómo calcula SIVE cada indicador a partir de las lecturas que llegan cada dos minutos de los
medidores, los inversores y las estaciones meteorológicas de las cinco plantas del proyecto, en Udenar, Unimar (sede
Alvernia), UCC, HUDN y Unicesmag. Cuando este documento y el código no coincidan, manda el código. Los archivos
citados están bajo `indicators/`.

---

## 0. Convenciones comunes

- **Paso de integración.** Δt = 2/60 h (2 minutos). Una hora completa tiene 30 lecturas y un día, 720. Energía =
  Σ P·Δt. La potencia del medidor (`totalActivePower`) viene en kW y la del inversor (`acPower`), en W.
- **Hora de Bogotá.** Las horas y los días de gráficas, agregados y rangos se toman en `America/Bogota`, no en UTC.
- **Un dato que falta no es 0.** Una columna NULL se descarta del cálculo (`services/rows.py`). Lo que no se pudo
  calcular queda en NULL y la pantalla lo muestra como «No disponible», nunca como 0.
- **Huecos.** Una lectura que no llegó no suma energía. La única reposición es la de las horas casi completas de la
  generación (§1). La cobertura, es decir, las lecturas presentes frente a las esperadas, se informa junto a la cifra.
- **Configuración de las plantas.** `institution_config.py` dice, por institución, qué medidor da la demanda y de qué
  tipo es, qué inversor da la generación, desde y hasta cuándo cuenta cada inversor, la estación meteorológica, si
  esa estación es apta para el PR, el comercializador y la capacidad, de 17,55 kWp por planta.

---

## 1. Energía horaria por institución

`services/institution_energy.py` construye, para cada hora de Bogotá, la generación G, la demanda D, la exportación y
el autoconsumo de una institución. La usan el Dashboard, los Indicadores Solares, el ahorro y el PR de las dos
pantallas. La energía de la pantalla Inversores sale de la misma regla por hora (§3).

- **Generación G.** Suma de la energía de los inversores de generación vigentes ese día. Por inversor y hora:
  - E = máx(Σ acPower, 0) × Δt / 1000, en kWh.
  - Si la hora tiene entre 15 y 29 de sus 30 lecturas, las que faltan se reponen con la media de las presentes
    (E × 30/n). Con menos de 15, lo que falta cuenta como 0. Así una Raspberry Pi que pierde lecturas sueltas no se
    lee como menos generación.
  - En Udenar, antes del 2025-09-03, G = Fronius 1 × 1,2054, porque el inversor del proyecto aún no existía.
- **Demanda D.** Del Medidor 1 de la institución y no de la suma de todos sus medidores, porque M2 a M5 son circuitos
  parciales que se solapan. La hora vale si el medidor tiene al menos 15 de 30 lecturas. Si no, D queda en NULL.
  - Medidor bruto (`gross`, HUDN y Unicesmag): D = máx(0, P_M1).
  - Medidor neto (`net` y `net_partial`, Udenar, Unimar y UCC): D = máx(0, P_M1 + Σ inversores aguas abajo).
- **Exportación y autoconsumo.** En medidores netos, exportación = parte negativa de P_M1 y autoconsumo =
  máx(0, G − exportación). En medidores brutos la exportación no se puede medir y se toma 0, es decir, todo lo
  generado se autoconsume.

La energía de cada mes se guarda en caché, 26 h para los meses cerrados y 10 min para el mes en curso. La tarea
`warm_solar_cache` la renueva cada noche y la reconciliación borra la de los meses que ganan lecturas.

---

## 2. Medidores (electricMeter)

`services/meter_calc.py`. Se calculan por día y por mes sobre las lecturas del periodo.

- **Energía importada y exportada.** Integración de la potencia activa, E_imp = Σ máx(P, 0)·Δt y
  E_exp = Σ máx(−P, 0)·Δt, con P = `totalActivePower` en kW. No se usan los registros acumulados, que en varios
  medidores están desescalados por la razón del transformador de corriente. La energía del mes es la suma exacta de la
  de sus días.
- **Energía neta.** E_neta = E_imp − E_exp.
- **Demanda pico.** La mayor media de los bloques de reloj de 15 min (:00, :15, :30, :45) que tienen al menos
  4 lecturas.
- **Demanda media y factor de carga.** Demanda media = media de `totalActivePower` del periodo.
  FC = demanda media / demanda pico × 100 %, acotado a 0–100 %.
- **Factor de potencia.** Media de |FP|. El FP del medidor viene con signo, que indica el sentido del flujo, y
  promediarlo con signo cancelaría valores.
- **Desbalance de fases.** DU = máx(|X_fase − X_prom|) / X_prom × 100 %, con X tensión o corriente por fase. Se informa
  el máximo del periodo. En corriente solo cuentan las lecturas con corriente media ≥ 1 A, porque con carga casi nula
  la fórmula llega al 200 %, y el resultado se acota a 100 %.
- **THD y TDD.** Máximo del periodo de los valores que da el medidor (`voltageTHDPhaseA/B/C`,
  `currentTHDPhaseA/B/C`, `currentTDDPhaseA/B/C`). El TDD de corriente, solo con corriente media ≥ 1 A. El THD de
  corriente, por fase y solo si la fundamental estimada, I_rms / √(1 + (THD/100)²), llega a 1 A.
  Con la generación FV detrás del medidor, la fundamental neta es pequeña buena parte del día y el THD de corriente
  supera el 100 % a baja carga neta. Ese valor es real y se guarda tal cual. En septiembre de 2026, de 19 medidores con
  datos, superaban el 100 % el máximo mensual de 15, el percentil 99 de 8, el percentil 95 de 6 y la mediana de 2.
  Para juzgar la calidad de la corriente se usa el TDD, que es el que da el reporte «Calidad de Potencia».
- **«Todos» los medidores.** La demanda media del conjunto es la suma de las medias. El pico es la suma de los picos de
  cada medidor, una cota superior porque los picos no tienen por qué coincidir, y el FC, Σ medias / Σ picos. Las
  energías se suman, el FP se promedia y los desbalances, THD y TDD toman el máximo.

---

## 3. Inversores (inverter)

`services/inverter_calc.py` y la tarea `calculate_inverter_indicators`. Se calculan por día y por mes.

- **Energía generada.** Es la misma energía horaria que la generación de Indicadores Solares (§1,
  `energia_inversor_hora_kwh` y `horas_inversor`). Por hora de Bogotá, E = máx(Σ acPower, 0) × Δt / 1000, con la
  reposición de las horas que tienen entre 15 y 29 lecturas y 0 por lo que falta con menos. La energía del día o del mes
  (`energy_ac_daily_kwh` y `total_generated_energy_kwh`) es la suma de sus horas, y una hora sin lecturas aporta 0. La
  energía DC (`energy_dc_daily_kwh`, de una sola entrada MPPT) sigue la misma regla. Para una planta y un día o mes en
  que su inversor de generación es el vigente, Inversores e Indicadores Solares dan la misma generación
  (`tests/test_energia_inversor_igual_solar.py`).
- **Gráfica horaria.** Energía de cada hora de Bogotá con la misma regla. Su suma es la energía del día. Una hora sin
  lecturas queda en NULL, es decir, no medida. El detalle horario (`HourlyInverterIndicators.energy_ac_kwh`) usa la
  misma regla. La gráfica la escribe solo la corrida diaria.
- **Frecuencia.** Media de `acFrequency` solo con lecturas en que el inversor genera (acFrequency > 0 y acPower > 0).
  De noche el inversor reporta 0 Hz. La estabilidad de frecuencia usa las mismas lecturas.
- **Factor de potencia.** Media de |powerFactor|/100 mientras genera, en escala de 0 a 1. El inversor lo reporta en %
  con signo.
- **Eficiencia DC/AC.** No se calcula. `dcPower` mide una sola de las entradas MPPT (DC/AC ≈ 0,55 en el HUDN), así que
  P_AC/P_DC no es la eficiencia. Queda en NULL con su motivo.
- **Desbalance de corriente inyectada.** Igual que en los medidores, con `acCurrentPhaseA/B/C` y la misma condición
  de 1 A.
- **Irradiancia y temperatura.** El inversor no las mide y quedan en NULL.

### 3.1 Performance Ratio

PR = Σ E_AC_día / Σ (H_día × kWp / 1 kW/m²), sobre los días válidos del periodo.

- **H** es la irradiación diurna de la estación de la institución, con las lecturas de 06:00 a 17:59 entre 0 y
  1400 W/m², × Δt / 1000, en kWh/m². La estación mide en plano horizontal (GHI), así que es un PR con irradiancia
  horizontal.
- **E_AC_día** es la energía del día con la reposición de las horas casi completas (§1).
- **Un día cuenta** si cumple estas tres condiciones:
  1. la estación tiene al menos el 80 % de sus 360 lecturas diurnas y H ≤ 8 kWh/m²,
  2. la estación coincide con la de referencia, la de Unimar en la sede Alvernia, a ±25 % ese día, y la mediana de la
     razón diaria estación/referencia de su mes queda a ±10 %, con al menos 5 días para contrastar, condición que no
     se aplica a la propia estación de referencia,
  3. el inversor tiene lectura en al menos el 80 % de las 12 horas de sol.
- **Sin PR.** No hay PR si la estación no es apta (la de Udenar da de 7 a 12 kWh/m²/día y está descalibrada), si no
  está en SIVE, si el inversor no es la generación de una planta o si ningún día cumple las condiciones. El motivo
  queda en `performance_ratio_note` y los días usados, en `performance_ratio_valid_days`.

**El PR de Inversores y el de Indicadores Solares son el mismo.** Los dos clasifican los días con
`institution_energy.dias_pr` y usan la misma irradiación (`irradiacion_diaria`) y la misma energía por hora
(`energia_inversor_hora_kwh`). Cada planta tiene un único inversor de generación, así que para la misma planta y el
mismo periodo dan la misma cifra (`tests/test_pr_inversor_igual_solar.py`). La pantalla Inversores guarda un PR por
día y uno por mes. Indicadores Solares lo calcula al vuelo para cualquier rango.

---

## 4. Estaciones meteorológicas (weatherStation)

`services/weather_calc.py`. Antes de calcular se descartan las lecturas fuera de rango físico, es decir, temperatura
de −20 a 60 °C, humedad de 0 a 100 %, viento de 0 a 150 km/h, dirección de 0 a 360° y precipitación negativa.

- **Irradiación diaria.** Σ irradiancia·Δt / 1000, en kWh/m², con las lecturas de 06:00 a 17:59 entre 0 y
  1100 W/m². Fuera de ese horario, un valor alto es un sensor pegado. El PR usa un tope de 1400 W/m² (§3.1).
- **Horas solares pico.** HSP = irradiación diaria / 1 kW/m² (1 HSP = 1 kWh/m²).
- **Potencia FV teórica.** Irradiancia media del día × 0,17, es decir, lo que daría 1 m² de módulo con 17 % de
  eficiencia, en W.
- **Viento.** Velocidad media del periodo y rosa de los vientos. En la vista horaria, la dirección es la media
  circular (350° y 10° dan 0°, no 180°).
- **Precipitación.** El sensor la acumula por día. El valor diario es la última lectura del día y el mensual, la suma
  de los diarios.
- **Mensual.** Media de los valores diarios para irradiación, HSP, viento, temperatura y humedad, suma para la
  precipitación y máximo y mínimo para la temperatura.
- **«Todas» las estaciones.** La irradiación, las HSP y la precipitación se promedian entre estaciones.
- **Estación de Udenar.** Está descalibrada. Se muestra con aviso y no se usa para el PR ni para la irradiancia del
  Dashboard.

---

## 5. Indicadores Solares por institución

`services/solar_kpis.py`, endpoint `GET /api/solar-indicators/`. Se calculan al vuelo desde la energía horaria (§1),
por día, mes o año, y para el total del rango.

- **Generación** y **generación acumulada** (kWh).
- **Rendimiento específico** = G / kWp, en kWh/kWp.
- **Factor de capacidad** = G / (kWp × horas del periodo).
- **Frente al diseño** = G / (59,4 kWh/día × días). El diseño supone 4,5 kWh/m²/día y 20 % de pérdidas.
- **Performance Ratio**, como en §3.1.
- **Demanda, demanda media y pico horario** del circuito del Medidor 1, solo en las horas válidas del medidor.
- **Cobertura solar** = G de las horas con medidor válido / D.
- **Autoconsumo y exportación**, como en §1. La generación de las horas sin medidor válido se informa aparte.
- **Ahorro** = energía autoconsumida × CU mensual del comercializador de la institución, en nivel de tensión 2 y sin
  contribución (`data/tarifas_cu.csv`). Un mes sin tarifa publicada usa la última anterior y se marca como tarifa
  extrapolada.
- **CO₂ evitado** = G × 0,112 kgCO₂/kWh, el factor del SIN de la Resolución UPME 0705 de 2024. Árboles equivalentes,
  545 por cada 12 t.
- **Disponibilidad de datos** = horas de sol con lectura del inversor / horas de sol. **Cobertura de lecturas** =
  lecturas diurnas presentes / esperadas.

El ahorro diario de la pantalla Datos Externos (`external_energy/tasks.py`, `calculate_energy_savings`) usa la misma
energía y las mismas tarifas, suma las instituciones y recalcula los últimos 40 días en cada corrida.

---

## 6. Dashboard

La tarea `calculate_monthly_consumption_kpi` guarda los valores en `MonthlyConsumptionKPI` y
`GET /api/dashboard/summary/` los sirve.

- **Ventanas.** El mes en curso va del día 1 a las 00:00 hasta ahora. El mes anterior va del día 1 a las 00:00 hasta el
  mismo tiempo transcurrido, para que la comparación sea pareja.
- **Demanda de los circuitos medidos** = Σ D de las plantas (§1), solo en horas válidas del medidor.
- **Energía tomada de la red** = Σ (D − autoconsumo).
- **Generación de las plantas** = Σ G.
- **Balance** = generación − demanda.
- **Potencia media de la flota** = G × 1000 / horas transcurridas, en W, noches incluidas.
- **Clima.** Medias de todas las estaciones con rangos físicos, es decir, temperatura de −10 a 45 °C, humedad de 0 a
  100 % y viento de 0 a 150 km/h. La irradiancia es la media diurna (06:00 a 17:59, 0 a 1400 W/m²) de las estaciones
  aptas.
- **Inversores con datos.** Inversores de generación vigentes con lecturas en SIVE en las últimas 24 h, sobre el total
  de inversores vigentes. No cuenta los de prueba ni los Fronius de Udenar retirados el 2026-04-11, y no es un dato en
  vivo del conector.

---

## 7. Ingesta y recálculo

- Cada hora se descargan las últimas 3 h y se recalculan los indicadores del día y del mes en curso y el *rollup*
  horario.
- **Reconciliación.** Cada noche se comparan, por dispositivo y día, los conteos de SIVE con los del conector en una
  ventana de 35 días, y cada 6 h, los de los últimos 2 días. Los días distintos se vuelven a descargar y se recalculan
  sus indicadores diarios, los mensuales de sus meses, la gráfica diaria, el *rollup* horario y el KPI mensual. Así
  entran las lecturas que las Raspberry Pi de las sedes envían con retraso.
- **Ayer completo.** A las 00:40 se recalcula siempre el día anterior completo para todos los dispositivos.
- Todos los cálculos son idempotentes (`update_or_create`). Para recalcular un histórico tras un cambio de fórmula
  están `scripts/recalcular_historico.sh DESDE HASTA` y los comandos `calculate_historical_*` de
  `indicators/management/commands/`.
