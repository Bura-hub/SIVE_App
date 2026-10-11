# Corrección de ingesta e indicadores de SIVE — octubre de 2026

**Rama:** `correccion-indicadores-2026-10` · **Inicio:** 2026-10-10 · **Plazo de las cifras del HUDN:** 2026-10-12
(visita ICONTEC del 13-oct).

Este documento es la referencia común de las correcciones: qué estaba mal, con qué se contrastó, qué se decide y
dónde queda cada cambio. Cada cambio que mueva una cifra deja aquí su **antes y después**.

## 1. Con qué se contrastó

- **`mte3`**, la base del conector SCADA (la misma que usa el Control Panel MTE), leída en solo lectura.
- **La tesis del autor** (`sistemabl`): construcción de D y G horarias, hallazgos H-7, H-12, H-16, H-27, H-36 y H-67, y
  tarifas `tarifas_asc_mensual.csv` y `tarifas_cedenar_mensual.csv`.
- **El módulo de mercado P2P con blockchain** (`mercado-p2p`): `semillas/agentes.json` (medidor de demanda por
  institución y su tipo), regla de inversores y defectos de datos documentados (repetidas, horas tardías, cortes de UCC).
- **Fronius Solar.web** para el inversor del HUDN (cifras mensuales de referencia de la sesión del HUDN).
- Una copia del respaldo de SIVE del 2026-10-10 02:30, restaurada en un Postgres desechable, y el código en `0fc41a9`.

## 2. Hallazgos

### 2.1 Datos crudos: correctos donde están completos

HUDN, del 2025-04-04 al 2025-12-16, comparado con la tesis:
- inversor: 12 913,9 kWh frente a 12 930,2 (−0,13 %); el pico de 15 144 W es idéntico;
- M1: 54 766 kWh frente a 55 840,8. La diferencia son 88 h sin dato, que la tesis interpola.

Generación mensual del HUDN frente a Solar.web (meses completos de 2025): may 1523,6 frente a 1524,4; jul 1615,2 frente a
1615,3; oct 1476,4 frente a 1474,3; nov 1408,0 frente a 1417,4. No hay duplicados: la clave única `(device, date)` lo
impide.

### 2.2 Ingesta: se pierden las lecturas que llegan tarde

La ingesta pide solo las **últimas 3 h** cada hora y vuelve a pedir **el día anterior** a la 01:30. Las RPi guardan en
cola cuando pierden conexión: UCC corta internet de noche y los fines de semana, y HUDN y UCC enviaron por tandas con días
de retraso hasta el 26-sep-2026. Esas lecturas entran a `mte3` después y **SIVE nunca las pide**.

Filas que faltaban en SIVE frente a `mte3` (2026-10-10):

| Institución | Meses | Faltante |
|---|---|---|
| UCC | jun–sep 2026 | 64–72 % |
| HUDN | jul–sep 2026 | 43–55 % |
| Udenar | ago 2026 | 17 % |
| Mariana | ago 2026 | 4 % |
| Cesmag | sep 2026 | 1,7 % |

Hasta mayo de 2026 coinciden fila a fila, con diferencias de ±10 filas.

Efecto en el HUDN: el inversor marcaba 564, 584 y 492 kWh en jul, ago y sep de 2026, cuando `mte3` tiene 960, 1076 y 875.
Septiembre sigue por debajo de Solar.web porque `mte3` tampoco tiene el 4–17-sep: es un hueco permanente.

### 2.3 Cálculos incorrectos (código en `0fc41a9`)

| # | Indicador | Qué pasa | Evidencia |
|---|---|---|---|
| C1 | Frecuencia media del inversor | Promedia las muestras nocturnas en 0 Hz. | HUDN: 54,4 Hz con todas las muestras; 59,99 Hz mientras genera (16 641 muestras en 0). |
| C2 | Factor de potencia del inversor | `powerFactor` viene en % con signo (de −100 a 100) y se promedia tal cual; la pantalla lo trata como si estuviera entre 0 y 1. | Media del HUDN: −41,3. |
| C3 | Eficiencia DC/AC | `dcPower` cubre **una sola entrada MPPT** (H-12): DC/AC ≈ 0,55. El valor se recorta a 100 %. | No se puede calcular con estos datos. |
| C4 | Performance Ratio | La lista de irradiancias va siempre en 0, y `pnom` es 50 kW fijo. | Siempre 0. |
| C5 | Generación horaria (`InverterChartData`) | Usa media horaria × 2/60: da la energía de una muestra, **30 veces menos**. | `tasks.py` (`_calculate_hourly_inverter_data`). |
| C6 | Irradiación de `WeatherStationChartData` | Suma de medias horarias × 2/60: **30 veces menos**. | `weather_calc.py`. |
| C7 | Horas y días de gráficas y agregados | `row['date'].hour` y `.date()` en **UTC** (5 h de desfase); el mensual de clima agrupa por día UTC. | `tasks.py` y `weather_calc.py`. |
| C8 | Agregado «Todos» de estaciones | **Suma** irradiación, HSP y precipitación entre estaciones. | `views.py`. |
| C9 | NULL → 0 | `_row_get` devuelve 0 si el valor es NULL; entra a promedios y desbalances. | `services/rows.py`. |
| C10 | Consumo y equilibrio del inicio | Suma **todos** los medidores (M1–M4 de cada sede, circuitos parciales que pueden solaparse, H-7 y H-36) y resta a la generación de todas las sedes. Los medidores netos ya descuentan la FV. | «Equilibrio energético −4,56 MWh». |
| C11 | Comparación con el mes anterior | Mes en curso hasta ahora frente al mes anterior hasta el **mismo día completo**. | Sesgo de −3 % a −10 % sin cambio real. |
| C12 | Inversores activos | Cuenta el `status` del conector e incluye los de prueba y los Fronius de Udenar retirados el 2026-04-11. | «4/10». |
| C13 | Ahorro | min(gen, consumo) × **precio de bolsa**. Debería ser la tarifa al usuario (CU del comercializador). Los días calculados no se recalculan nunca. | `external_energy/tasks.py`. |
| C14 | Unidades de XM en pantalla | `Gene` y `DemaCome` vienen en kWh por hora y se muestran como MW; las exportaciones e importaciones se escalan dos veces. | `ExternalEnergyData.js`. |
| C15 | Indicadores de ayer | Solo se recalcula el día de hoy; el diario de ayer queda con la corrida de las 23:10. | `scada_proxy/tasks.py`. |
| C16 | Estación de Udenar | Irradiación diaria de 7 a 12 kWh/m²/día, físicamente imposible: está descalibrada. | Hay que marcarla y no usarla para el PR. |

### 2.4 Caída de la generación del HUDN en 2026: es del sistema, no del clima

- El HUDN genera entre **21 y 37 % menos** que en 2025 **todos los meses**, de abril a octubre.
- Mariana, una planta idéntica de 17,55 kWp a pocos kilómetros, varía entre −18 y +9 % y queda casi igual en abr–jun y
  en oct.
- La irradiación de la estación de Alvernia en abr–jun de 2026 fue **mayor** que en 2025.
- Al mediodía, el HUDN tocaba el techo del inversor (15,13 kW, percentil 99) en 2025. Desde mayo de 2026 se queda en
  13,0–13,8 kW. Mariana sigue tocándolo.
- La corriente DC del MPPT medido baja de unos 6,0 A a unos 4,5 A (−25 %), en la misma proporción que la energía. Esto
  apunta a una **pérdida uniforme del arreglo** (suciedad o sombra) más que a un *string* desconectado, aunque el segundo
  MPPT no se mide.
- La estación del HUDN no tiene datos desde marzo de 2026, así que el PR de 2026 no se puede calcular con ella.

## 3. Decisiones

**D1. Ingesta con reconciliación diaria.** Cada noche se comparan, por dispositivo y día, los conteos de SIVE con los del
conector (`meta.total`) en una ventana de 35 días. Los días distintos se vuelven a descargar con upsert y se recalculan sus
indicadores diarios, los mensuales de los meses tocados, el gráfico diario y el rollup horario. Cada 6 h se hace lo mismo
con los últimos 2 días. Así llega a SIVE todo lo que llega a `mte3`, igual que en el Control Panel.

**D2. Energía por institución como en la tesis y el mercado P2P.**
- Demanda D del **medidor principal (M1)** de cada institución, según `agentes.json` del mercado:
  - `gross` (HUDN, Cesmag): D = máx(0, P_M1);
  - `net` y `net_partial` (Udenar, Mariana, UCC): D = máx(0, P_M1 + Σ inversores de la sede).
- G es el inversor de la institución. Los inversores retirados se cuentan solo hasta la fecha de retiro.
- La configuración vive en un archivo versionado de SIVE.
- Los medidores M2–M5 se siguen viendo en su pantalla, pero no se suman al consumo de la institución.

**D3. Integración.** Energía = Σ P·Δt con Δt nominal de 2 min (720 muestras al día), igual que hoy. Además se informa la
**cobertura** (muestras presentes / esperadas) y no se rellenan huecos sin marca. Para las cifras oficiales se usa
«faltante = 0» en G, como el mercado, y se declara la cobertura junto a la cifra.

**D4. Capacidad FV:** 17,55 kWp por institución (30 módulos Jinko de 585 Wp; tesis H-67). Se configura por institución.

**D5. Performance Ratio:** PR = E_AC / (H × P_kWp / 1 kW/m²).
- H es la irradiación diurna de la estación de la institución: muestras entre 06:00 y 18:00, en 0–1400 W/m².
- Solo cuentan los días con ≥ 80 % de las muestras diurnas y H ≤ 8 kWh/m²/día. Una estación que no lo cumpla se marca
  «no apta» (por ejemplo, la de Udenar).
- La estación mide en **plano horizontal (GHI)**, no en el plano de los módulos. Así se declara: el PR resultante es un PR
  con irradiancia horizontal.

**D6. Eficiencia del inversor:** **no se calcula**. Se muestra «no disponible: `dcPower` mide una sola entrada MPPT»,
nunca un 100 % ni un 0.

**D7. Factor de potencia del inversor:** media de |FP|/100 mientras genera (acPower > 0), en escala 0–1.

**D8. Ahorro:** kWh autoconsumidos × CU mensual del comercializador.
- ASC nivel 2 «oficial» para Udenar, Mariana, UCC y HUDN; Cedenar nivel 2 «oficial» para Cesmag (`tarifas_*_mensual.csv`
  de la tesis).
- Los meses sin tarifa publicada usan la última disponible y se marcan «tarifa extrapolada».
- El supuesto se muestra en pantalla.

**D9. CO₂ evitado:** 0,112 kgCO₂/kWh (factor del SIN, UPME, Res. 0705/2024). Equivalencia en árboles: 545 árboles por
12 t (Informe Técnico 2).

**D10. Autoconsumo y exportación.**
- Medidor neto: horas con P_M1 < 0 → exportación = −P_M1; autoconsumo = G − exportación.
- Medidor bruto: la G entra al circuito medido. Si M1 importa todas las horas (HUDN: mínimo +5,3 kW), autoconsumo = 100 %.

**D11. Diseño:** 59,4 kWh/día por sistema; 4,5 kWh/m²/día; 20 % de pérdidas (Informe Técnico 2).

**D12. Invitados:** cualquiera ve en solo lectura todas las pantallas de datos sin iniciar sesión. Exportar reportes,
recalcular y administrar piden sesión.

## 4. Registro de cambios (antes → después)

Se completa con cada commit de la rama.

**D1 — Reconciliación de mediciones** (`17b82c3`; `scada_proxy/tasks.py`, `core/settings.py`, comando
`reconcile_measurements`, `tests/test_reconcile_measurements.py`).
- Antes: la ingesta pedía las últimas 3 h cada hora y `refetch_and_verify_yesterday` re-descargaba solo ayer a la 01:30;
  lo que las RPi enviaban con más retraso no entraba nunca (§2.2).
- Después: `reconcile_measurements` compara por dispositivo y día de Bogotá el conteo de SIVE con `meta.total` del
  conector y re-descarga con upsert solo los días distintos; la diferencia que persiste se registra y alerta, y sigue.
  Recalcula solo lo que ganó filas: diarios y rollup horario por dispositivo y rango de días, chart diario, mensuales
  de los meses tocados y el KPI mensual una vez. En el beat, `reconcile-measurements-daily` (01:30, hoy y 35 días atrás)
  y `reconcile-measurements-6h` (cada 6 h en :40, hoy y 2 días atrás); `refetch_and_verify_yesterday` queda como alias y
  su entrada del beat, deshabilitada desde `settings` (el `DatabaseScheduler` la desactiva al arrancar). **No cierra
  C15**: las filas de ayer que la ingesta horaria trae después de las 23:10 dejan los conteos iguales y no disparan
  recálculo.
