/**
 * Información detallada (info-al-click) de las tarjetas KPI, centralizada para las 4 pantallas
 * (Inicio / Medidores / Inversores / Estaciones). Antes estaba duplicada en 3 componentes y
 * ausente en Inversores (causaba ReferenceError al abrir el overlay).
 *
 * Cada entrada usa el esquema profesional de bloques:
 *   title           — nombre de la tarjeta
 *   description     — Definición (1 frase)
 *   calculation     — Cómo se calcula (fórmula real + campo backend)
 *   dataSource      — Fuente del dato
 *   units           — Unidad
 *   frequency       — Muestreo y agregación reales
 *   interpretation  — Interpretación / umbral (qué es bueno/malo)
 *
 * Nota de exactitud: el conector SCADA muestrea ~cada 2 min (no "cada 5 min") y los KPIs del
 * Inicio son agregaciones MENSUALES recalculadas por tarea programada; "Inversores con datos" cuenta
 * lecturas guardadas en SIVE en las últimas 24 h, no es tiempo real. Los detalles
 * (Medidores/Inversores/Estaciones) agregan sobre el rango de fechas. Las fórmulas, tras la corrección de octubre de 2026,
 * están en indicators/indicators.md.
 */

export const DASHBOARD_KPI_INFO = {
  totalConsumption: {
    title: "Demanda de los circuitos medidos",
    description: "Energía demandada en el mes por los circuitos del Medidor 1 de cada institución (Udenar, Mariana, UCC, HUDN y Cesmag). No es el consumo total de cada institución: el Medidor 1 mide un circuito o bloque.",
    calculation: "Por institución y hora: media de totalActivePower del Medidor 1 (horas con ≥ 15 de 30 lecturas). En los medidores en el punto de conexión (Udenar, Mariana, UCC) se suma la generación aguas abajo: D = máx(0, P_M1 + FV).",
    dataSource: "Medidor 1 de cada institución (conector SCADA, reconciliado a diario).",
    units: "kWh (se muestra en MWh según magnitud).",
    frequency: "Muestreo ~2 min; el mes en curso se compara con el anterior con el MISMO tiempo transcurrido.",
    interpretation: "Léase junto a la generación: la cobertura solar es Generación / Demanda.",
  },
  totalGeneration: {
    title: "Generación de las plantas FV",
    description: "Energía AC entregada en el mes por los inversores de las cinco plantas del proyecto (17,55 kWp cada una).",
    calculation: "Σ acPower × 2 min / 1000 de cada inversor de planta, por hora. Si la hora tiene ≥ 15 de 30 lecturas, las que faltan se reponen con la media de las presentes; con menos, una lectura que no llegó no suma. Udenar antes del 2025-09-03: Fronius 1 × 1,2054.",
    dataSource: "Inversores de las plantas (conector SCADA). No incluye equipos de prueba ni inversores retirados.",
    units: "kWh (se muestra en MWh según magnitud).",
    frequency: "Muestreo ~2 min; comparación con el mismo tiempo transcurrido del mes anterior.",
    interpretation: "Caídas con irradiancia estable indican suciedad, sombra o fallas en planta. El detalle por institución está en «Indicadores Solares».",
  },
  energyBalance: {
    title: "Balance generación − demanda",
    description: "Generación de las plantas menos la demanda de los circuitos medidos en el mes.",
    calculation: "Balance = Generación (plantas) − Demanda (circuitos del Medidor 1).",
    dataSource: "Derivado de los dos KPIs anteriores.",
    units: "kWh (se muestra en MWh según magnitud).",
    frequency: "Mensual, derivado.",
    interpretation: "Negativo = la demanda de los circuitos medidos supera la generación (se completa con la red); positivo = excedente. No describe la institución completa, solo los circuitos medidos.",
  },
  averageInstantaneousPower: {
    title: "Potencia media de la flota",
    description: "Potencia AC media entregada por todas las plantas juntas en lo que va del mes (día y noche).",
    calculation: "Generación del mes (kWh) × 1000 / horas transcurridas.",
    dataSource: "Inversores de las plantas (conector SCADA).",
    units: "W (se muestra en kW).",
    frequency: "Mensual.",
    interpretation: "Equivale a la generación expresada como potencia constante; léase junto a la irradiancia.",
  },
  avgDailyTemp: {
    title: "Temperatura Promedio Diaria",
    description: "Temperatura ambiente media de las estaciones meteorológicas en el mes.",
    calculation: "Promedio del campo temperature de las estaciones (avg_daily_temp_current_month). No es promedio de máximas y mínimas.",
    dataSource: "Estaciones meteorológicas del conector SCADA.",
    units: "°C.",
    frequency: "Muestreo ~cada hora; promedio mensual.",
    interpretation: "Variable de contexto: mayor temperatura reduce la eficiencia FV (efecto real vía temperatura de módulo, ~−0.4%/°C). Sin umbral de alarma; útil para explicar caídas de generación en meses cálidos.",
  },
  relativeHumidity: {
    title: "Humedad Relativa Promedio",
    description: "Humedad relativa media del aire en las estaciones durante el mes.",
    calculation: "Promedio del campo humidity de las estaciones (avg_relative_humidity_current_month).",
    dataSource: "Estaciones meteorológicas del conector SCADA.",
    units: "% HR.",
    frequency: "Muestreo ~cada hora; promedio mensual.",
    interpretation: "Óptima ~40–60%; Alta >60% (favorece condensación y ensuciamiento de paneles); Baja <40%.",
  },
  windSpeed: {
    title: "Velocidad del Viento Promedio",
    description: "Velocidad media del viento en las estaciones durante el mes.",
    calculation: "Promedio del campo windSpeed de las estaciones (avg_wind_speed_current_month).",
    dataSource: "Anemómetros de las estaciones del conector SCADA.",
    units: "km/h.",
    frequency: "Muestreo ~cada hora; promedio mensual.",
    interpretation: "Viento moderado favorece el enfriamiento de módulos; rachas altas sostenidas importan para seguridad estructural (el promedio subestima el riesgo de racha).",
  },
  irradiance: {
    title: "Irradiancia Solar Promedio",
    description: "Irradiancia media diurna (06:00–18:00) por m² durante el mes.",
    calculation: "Promedio de irradiance entre 06:00 y 17:59 (0–1400 W/m²) de las estaciones aptas; la de Udenar está descalibrada y no entra.",
    dataSource: "Piranómetros de las estaciones del conector SCADA.",
    units: "W/m².",
    frequency: "Muestreo ~cada hora; promedio mensual.",
    interpretation: "Principal driver de la generación esperada: generación baja con irradiancia alta señala pérdidas en planta. Bandas del sistema: Baja / Moderada / Alta.",
  },
  activeInverters: {
    title: "Inversores con datos",
    description: "Inversores de las plantas del proyecto con lecturas en SIVE en las últimas 24 h, sobre los inversores de planta vigentes.",
    calculation: "Conteo de inversores de planta (sin equipos de prueba ni retirados) con al menos una lectura en las últimas 24 h.",
    dataSource: "Lecturas guardadas en SIVE (no depende de que el conector responda).",
    units: "con datos / total.",
    frequency: "Se actualiza con cada consulta.",
    interpretation: "Si falta alguno, la descripción dice cuál. De noche los inversores no publican, por eso se mira una ventana de 24 h.",
  },
};

export const METER_KPI_INFO = {
  totalEnergyConsumed: {
    title: "Energía Importada de la Red",
    description: "Energía activa IMPORTADA de la red por los medidores en el rango (sin descontar la exportada). No confundir con la demanda de los circuitos medidos del Inicio.",
    calculation: "Integración de la potencia: Σ max(totalActivePower, 0) × Δt sobre las lecturas del rango (imported_energy_kwh, C17). Ya no se usan los acumuladores importedActivePower, desescalados en varios medidores. Una lectura que no llegó no suma.",
    dataSource: "Medidores eléctricos del conector SCADA.",
    units: "kWh.",
    frequency: "Muestreo ~2 min; suma sobre el rango de fechas seleccionado.",
    interpretation: "Energía comprada a la red; contrástese con la generación propia para estimar el autoconsumo.",
  },
  peakDemand: {
    title: "Demanda Pico",
    description: "Máxima potencia demandada (media de un bloque de 15 min) alcanzada en el rango seleccionado.",
    calculation: "Máximo de peak_demand_kw sobre los registros del rango; peak_demand_kw es la mayor media de totalActivePower en bloques de reloj de 15 min. Con «Todos» se suman los picos de cada medidor, una cota superior porque no ocurren a la vez.",
    dataSource: "Medidores eléctricos del conector SCADA.",
    units: "kW.",
    frequency: "Muestreo ~2 min; máximo sobre el rango de fechas.",
    interpretation: "Compárese contra la demanda contratada; picos cercanos o superiores implican riesgo de penalización o recargo por potencia.",
  },
  loadFactor: {
    title: "Factor de Carga",
    description: "Uniformidad del uso de la capacidad instalada (relación entre demanda media y demanda pico) en el rango.",
    calculation: "load_factor = (demanda media del rango / demanda pico del rango) × 100, acotado a [0,100]. Con «Todos»: Σ medias / Σ picos de los medidores.",
    dataSource: "Medidores eléctricos del conector SCADA.",
    units: "%.",
    frequency: "Muestreo ~2 min; calculado sobre el rango de fechas.",
    interpretation: ">80% Excelente (uso parejo y eficiente); 60–80% Bueno; <60% Mejorable (demanda con picos costosos).",
  },
  powerFactor: {
    title: "Factor de Potencia",
    description: "Factor de potencia medio reportado por los medidores en el rango.",
    calculation: "Promedio de |totalPowerFactor| de cada lectura: el medidor lo reporta con signo según el sentido del flujo y promediar con signo cancelaba valores. No se recalcula P/S.",
    dataSource: "Medidores eléctricos del conector SCADA.",
    units: "adimensional (0–1).",
    frequency: "Muestreo ~2 min; promedio sobre el rango de fechas.",
    interpretation: "≥0.95 Óptimo; 0.90–0.95 Bueno; <0.90 Mejorable y con riesgo de penalización (umbral regulatorio Colombia 0.90). Valores bajos = cargas inductivas sin compensar.",
  },
};

export const INVERTER_KPI_INFO = {
  totalGeneration: {
    title: "Generación Total",
    description: "Energía AC total generada por los inversores en el rango seleccionado.",
    calculation: "Suma de total_generated_energy_kwh sobre los registros del rango. Por hora: Σ acPower × 2 min / 1000; si la hora tiene ≥ 15 de 30 lecturas, las que faltan se reponen con la media de las presentes; con menos, una lectura que no llegó no suma. Es la misma energía que la generación de Indicadores Solares.",
    dataSource: "Inversores solares del conector SCADA.",
    units: "MWh.",
    frequency: "Muestreo ~2 min; suma sobre el rango de fechas.",
    interpretation: "Sin umbral fijo; contrástese con la irradiancia del período — baja generación con alta irradiancia indica pérdidas o inversores caídos.",
  },
  activeInverters: {
    title: "Inversores Activos",
    description: "Número de inversores DISTINTOS con registros en el rango seleccionado (no es estado 'online' instantáneo).",
    calculation: "Conteo de device_id únicos en los registros del rango.",
    dataSource: "Inversores solares del conector SCADA.",
    units: "dispositivos.",
    frequency: "Según el rango de fechas seleccionado.",
    interpretation: "Debe coincidir con el parque instalado; si es menor, hay inversores sin reportar datos en el período. No confundir con «Inversores con datos» del Inicio, que mira solo las últimas 24 h.",
  },
  maxPower: {
    title: "Potencia Máxima",
    description: "Potencia AC máxima entregada por los inversores en el rango.",
    calculation: "Máximo de max_power_w sobre los registros del rango, mostrado en kW.",
    dataSource: "Inversores solares del conector SCADA.",
    units: "kW.",
    frequency: "Muestreo ~2 min; máximo sobre el rango de fechas.",
    interpretation: "Pico de potencia registrado; útil para dimensionamiento y para detectar recortes (clipping) del inversor.",
  },
  powerFactor: {
    title: "Factor de Potencia",
    description: "Factor de potencia medio entregado por los inversores mientras generan.",
    calculation: "El inversor reporta powerFactor en % con signo (−100 a 100). Se toma |FP|/100 de las muestras con acPower > 0 y se promedia (avg_power_factor, escala 0–1). Sin muestras generando: no disponible.",
    dataSource: "Inversores solares del conector SCADA.",
    units: "adimensional (0–1).",
    frequency: "Muestreo ~2 min; promedio sobre el rango de fechas.",
    interpretation: "≥0.95 óptimo; <0.90 deficiente. Un FP bajo en generación afecta la calidad de la inyección a la red.",
  },
  performanceRatio: {
    title: "Performance Ratio",
    description: "Relación entre la energía AC generada y la que daría la planta con la irradiación medida por la estación de la institución, sin pérdidas.",
    calculation: "PR = Σ E_AC / Σ (H × kWp / 1 kW/m²) sobre los días válidos. H = Σ irradiancia de 06:00–18:00 (0–1400 W/m²) × 2/60 / 1000; un día es válido con ≥ 80 % de las muestras diurnas de la estación, H ≤ 8 kWh/m² y H a ±25 % de la estación de referencia (Alvernia) ese día; se descartan los meses cuya mediana estación/referencia se aparta más de ±10 %. kWp = 17,55 por planta.",
    dataSource: "Inversor de la planta y estación meteorológica de la misma institución (conector SCADA).",
    units: "%.",
    frequency: "Por día; el del rango pondera los días válidos.",
    interpretation: "La estación mide en plano horizontal (GHI), así que es un PR con irradiancia horizontal. 75–85 % es típico de una planta sana; valores bajos y sostenidos sugieren suciedad, sombras o fallas. No disponible si la estación no es apta (la de Udenar está descalibrada) o no hay días válidos.",
  },
  dcAcEfficiency: {
    title: "Eficiencia DC/AC",
    description: "Relación entre la potencia AC entregada y la potencia DC recibida por el inversor.",
    calculation: "No se calcula: dcPower solo reporta una de las entradas MPPT del inversor, así que el cociente AC/DC (≈ 1,8 en el HUDN) no es una eficiencia.",
    dataSource: "Inversores solares del conector SCADA.",
    units: "%.",
    frequency: "—",
    interpretation: "No disponible con estos datos.",
  },
  phaseUnbalance: {
    title: "Desbalance de Fases (tensión)",
    description: "Máximo desbalance de tensión entre las tres fases del inversor en el rango.",
    calculation: "Desbalance máximo derivado de acVoltagePhaseA/B/C (max_voltage_unbalance_pct).",
    dataSource: "Inversores solares del conector SCADA.",
    units: "%.",
    frequency: "Muestreo ~2 min; máximo sobre el rango de fechas.",
    interpretation: "<2% saludable (NEMA); 2–3% vigilar; >3% problemático (estrés térmico, disparos). Desbalances altos y sostenidos indican fallo de fase o conexión.",
  },
  avgFrequency: {
    title: "Frecuencia Promedio",
    description: "Frecuencia eléctrica media de la red en el punto del inversor. (Antes rotulada 'Estabilidad Frecuencia', que era engañoso: muestra la frecuencia media, no un índice de estabilidad.)",
    calculation: "Promedio de acFrequency solo en las muestras con acFrequency > 0 y acPower > 0 (avg_frequency_hz). De noche el inversor reporta 0 Hz y esas muestras no cuentan.",
    dataSource: "Inversores solares del conector SCADA.",
    units: "Hz.",
    frequency: "Muestreo ~2 min; promedio sobre el rango de fechas.",
    interpretation: "Nominal 60 Hz, banda operativa ~59.5–60.5 Hz; desvíos sostenidos indican inestabilidad de red.",
  },
  currentUnbalance: {
    title: "Desbalance de Corriente",
    description: "Máximo desbalance de corriente entre fases del inversor en el rango. (Reemplaza al antiguo 'THD Voltaje', que no existe como medida en el sistema y salía 0.)",
    calculation: "Máximo de max_current_unbalance_pct sobre los registros del rango.",
    dataSource: "Inversores solares del conector SCADA.",
    units: "%.",
    frequency: "Muestreo ~2 min; máximo sobre el rango de fechas.",
    interpretation: "Complementa el desbalance de tensión; valores altos indican reparto desigual de carga entre fases (>10% se marca como anomalía).",
  },
};

export const WEATHER_KPI_INFO = {
  irradiance: {
    title: "Irradiancia Acumulada",
    description: "Energía solar incidente acumulada por m² en el día más reciente del rango. Equivale a las Horas Solares Pico (se muestra también como HSP).",
    calculation: "Suma de irradiancia instantánea (solo lecturas 0–1100 W/m² entre 06:00 y 18:00) · Δt, convertida a kWh/m². HSP = irradiancia acumulada / 1 kW/m² (mismo número en horas).",
    dataSource: "Piranómetros de las estaciones del conector SCADA.",
    units: "kWh/m²/día (≈ HSP).",
    frequency: "Muestreo ~cada hora; acumulado del día más reciente del rango.",
    interpretation: "Referencia zona andina ~4–5 kWh/m²/día (≈ 4–5 HSP); valores bajos = día nublado. Es el insumo directo del rendimiento FV esperado.",
  },
  windSpeed: {
    title: "Velocidad del Viento",
    description: "Velocidad media del viento en el día más reciente. Si la estación no tiene anemómetro se muestra «No disponible» (no 0).",
    calculation: "Promedio de windSpeed (lecturas válidas 0–150 km/h) del día.",
    dataSource: "Anemómetros de las estaciones del conector SCADA.",
    units: "km/h.",
    frequency: "Muestreo ~cada hora; promedio del día más reciente del rango.",
    interpretation: "Viento moderado favorece el enfriamiento de módulos; rachas altas importan para seguridad. El promedio subestima la racha máxima.",
  },
  windDirection: {
    title: "Dirección del Viento (Predominante)",
    description: "Dirección cardinal desde la que sopla el viento con mayor frecuencia en el rango.",
    calculation: "Sector cardinal con mayor conteo en wind_direction_distribution (rosa de los vientos de 8 sectores).",
    dataSource: "Veletas de las estaciones del conector SCADA.",
    units: "cardinal (N, NE, E, SE, S, SW, W, NW).",
    frequency: "Muestreo ~cada hora; sector dominante del día más reciente del rango.",
    interpretation: "Orienta el ensuciamiento/limpieza de paneles y el diseño; una única dirección dominante sugiere un régimen de viento estable.",
  },
  precipitation: {
    title: "Precipitación Acumulada",
    description: "Lluvia acumulada del día más reciente. Si la estación no tiene pluviómetro se muestra «No disponible» (no 0).",
    calculation: "En vista diaria se toma el último valor del acumulador de precipitation (reinicio diario); en vista mensual se suman los diarios.",
    dataSource: "Pluviómetros de las estaciones del conector SCADA.",
    units: "cm/día.",
    frequency: "Muestreo ~cada hora; acumulado del día más reciente del rango.",
    interpretation: "Relevante para la autolimpieza de módulos tras la lluvia y como contexto de baja irradiancia.",
  },
  pvPower: {
    title: "Potencia Fotovoltaica (teórica)",
    description: "Potencia FV teórica de referencia por m² a partir de la irradiancia medida. NO es la generación real (esa está en Inversores).",
    calculation: "Irradiancia media (W/m²) × eficiencia 17% × 1 m² de referencia (theoretical_pv_power_w). Supuestos fijos declarados.",
    dataSource: "Derivado de la irradiancia de las estaciones del conector SCADA.",
    units: "W (por m² de referencia).",
    frequency: "Muestreo ~cada hora; del día más reciente del rango.",
    interpretation: "Valor teórico para comparar 'esperado vs generado'. Siempre léase junto a los supuestos (17%, 1 m²); no representa la planta real.",
  },
  temperature: {
    title: "Temperatura Ambiente",
    description: "Temperatura ambiente media registrada por la estación en el día más reciente del rango.",
    calculation: "Promedio del campo temperature de la estación (avg_temperature_c).",
    dataSource: "Estaciones meteorológicas del conector SCADA.",
    units: "°C.",
    frequency: "Muestreo ~cada hora; promedio del día más reciente del rango.",
    interpretation: "Gobierna las pérdidas térmicas del panel (~−0.4%/°C sobre 25 °C): temperaturas altas reducen la generación aunque la irradiancia sea buena.",
  },
};
