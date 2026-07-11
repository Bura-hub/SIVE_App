/**
 * Información detallada (info-al-click) de las tarjetas KPI, centralizada para las 4 pantallas
 * (Inicio / Medidores / Inversores / Estaciones). Antes estaba duplicada en 3 componentes y
 * ausente en Inversores (causaba ReferenceError al abrir el overlay). Ver AUDITORIA_SIVE/PLAN_KPIS.md.
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
 * Inicio son agregaciones MENSUALES recalculadas por tarea programada (salvo "Inversores activos",
 * que es tiempo real). Los detalles (Medidores/Inversores/Estaciones) agregan sobre el rango de fechas.
 */

export const DASHBOARD_KPI_INFO = {
  totalConsumption: {
    title: "Consumo Total de Energía (neto)",
    description: "Energía eléctrica activa NETA consumida por todas las instalaciones monitoreadas en el mes (net metering: descuenta lo inyectado, puede ser negativo).",
    calculation: "Suma de totalActivePower de todos los medidores integrada por Δt (MonthlyConsumptionKPI.total_consumption_current_month).",
    dataSource: "Medidores eléctricos del conector SCADA.",
    units: "kWh (se muestra en MWh según magnitud).",
    frequency: "Muestreo ~2 min; agregación mensual recalculada por tarea programada.",
    interpretation: "Sin umbral fijo; se compara contra el mes anterior (badge %). Valores negativos = exportación neta. Un alza sostenida sin nueva carga sugiere pérdida de eficiencia; léase junto a Generación y Balance.",
  },
  totalGeneration: {
    title: "Generación Total de Energía",
    description: "Energía solar entregada en corriente alterna por todos los inversores durante el mes.",
    calculation: "Suma de acPower·Δt/1000 sobre las medidas de inversores (MonthlyConsumptionKPI.total_generation_current_month).",
    dataSource: "Inversores solares del conector SCADA.",
    units: "kWh (se muestra en MWh según magnitud).",
    frequency: "Muestreo ~2 min; agregación mensual recalculada por tarea programada.",
    interpretation: "Sin umbral absoluto; interesa la fracción autoabastecida = Generación/Consumo. Caídas mensuales con irradiancia estable indican inversores fuera de línea o paneles sucios.",
  },
  energyBalance: {
    title: "Equilibrio Energético",
    description: "Diferencia entre la energía generada y la consumida en el mes.",
    calculation: "Balance = Generación total − Consumo total (derivado en la vista).",
    dataSource: "Cálculo derivado de los KPIs de generación y consumo.",
    units: "kWh (se muestra en MWh según magnitud).",
    frequency: "Cálculo mensual, derivado de generación y consumo.",
    interpretation: ">0 superávit (excedente exportable); <0 déficit (dependencia de la red); ≈0 autosuficiencia. Un déficit creciente indica que la demanda supera la capacidad solar instalada.",
  },
  averageInstantaneousPower: {
    title: "Potencia Instantánea Promedio",
    description: "Potencia AC promedio entregada por los inversores a lo largo del mes (no es el pico ni tiempo real).",
    calculation: "Promedio de acPower sobre las medidas de inversores (avg_instantaneous_power_current_month).",
    dataSource: "Inversores solares del conector SCADA.",
    units: "W (se muestra en kW).",
    frequency: "Muestreo ~2 min; promedio mensual.",
    interpretation: "Refleja el nivel de generación típico; léase junto a la irradiancia. Un promedio bajo con irradiancia alta sugiere pérdidas en planta.",
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
    description: "Radiación solar media incidente por m² durante el mes.",
    calculation: "Promedio del campo irradiance de las estaciones (avg_irradiance_current_month).",
    dataSource: "Piranómetros de las estaciones del conector SCADA.",
    units: "W/m².",
    frequency: "Muestreo ~cada hora; promedio mensual.",
    interpretation: "Principal driver de la generación esperada: generación baja con irradiancia alta señala pérdidas en planta. Bandas del sistema: Baja / Moderada / Alta.",
  },
  activeInverters: {
    title: "Inversores Activos",
    description: "Número de inversores reportando estado 'online' en SCADA en este instante, sobre el total registrado. ÚNICO KPI en tiempo real de esta pantalla.",
    calculation: "Conteo de dispositivos categoría inversor con status=='online' / total (summarize_inverter_status).",
    dataSource: "Estado de conexión de inversores en tiempo real del conector SCADA.",
    units: "activos / total (p. ej. 5/6).",
    frequency: "Consulta en tiempo real al conector SCADA (el resto de la pantalla es mensual).",
    interpretation: "Ideal activos = total; si activos < total hay inversores caídos a inspeccionar. Un 0 con aviso de error significa que SCADA no respondió, NO que la planta esté apagada.",
  },
};

export const METER_KPI_INFO = {
  totalEnergyConsumed: {
    title: "Energía Importada de la Red",
    description: "Energía activa total IMPORTADA de la red por los medidores en el rango (energía BRUTA, no neta). No confundir con el Consumo NETO del Inicio.",
    calculation: "Suma de imported_energy_kwh sobre todos los registros del rango (acumuladores importedActivePower con saneamiento anti roll-over).",
    dataSource: "Medidores eléctricos del conector SCADA.",
    units: "kWh.",
    frequency: "Muestreo ~2 min; suma sobre el rango de fechas seleccionado.",
    interpretation: "Energía comprada a la red; contrástese con la generación propia para estimar el autoconsumo.",
  },
  peakDemand: {
    title: "Demanda Pico",
    description: "Máxima potencia demandada (media móvil de ~15 min) alcanzada en el rango seleccionado.",
    calculation: "Máximo de peak_demand_kw sobre TODOS los registros del rango; peak_demand_kw es el máximo de medias móviles de 7 muestras de totalActivePower.",
    dataSource: "Medidores eléctricos del conector SCADA.",
    units: "kW.",
    frequency: "Muestreo ~2 min; máximo sobre el rango de fechas.",
    interpretation: "Compárese contra la demanda contratada; picos cercanos o superiores implican riesgo de penalización o recargo por potencia.",
  },
  loadFactor: {
    title: "Factor de Carga",
    description: "Uniformidad del uso de la capacidad instalada (relación entre demanda media y demanda pico) en el rango.",
    calculation: "load_factor = (demanda media del rango / demanda pico del rango) × 100, acotado a [0,100].",
    dataSource: "Medidores eléctricos del conector SCADA.",
    units: "%.",
    frequency: "Muestreo ~2 min; calculado sobre el rango de fechas.",
    interpretation: ">80% Excelente (uso parejo y eficiente); 60–80% Bueno; <60% Mejorable (demanda con picos costosos).",
  },
  powerFactor: {
    title: "Factor de Potencia",
    description: "Factor de potencia medio reportado por los medidores en el rango.",
    calculation: "Promedio del campo totalPowerFactor que reporta cada medidor (no se recalcula P/S).",
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
    calculation: "Suma de total_generated_energy_kwh (=Σ acPower·Δt/1000) sobre todos los registros del rango.",
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
    interpretation: "Debe coincidir con el parque instalado; si es menor, hay inversores sin reportar datos en el período. No confundir con el KPI homónimo del Inicio, que sí es estado 'online' en tiempo real.",
  },
  maxPower: {
    title: "Potencia Máxima",
    description: "Potencia AC máxima entregada por los inversores en el rango. (Reemplaza al antiguo Performance Ratio, que era irreparable: el inversor no mide irradiancia, por lo que siempre salía 0.)",
    calculation: "Máximo de max_power_w sobre los registros del rango, mostrado en kW.",
    dataSource: "Inversores solares del conector SCADA.",
    units: "kW.",
    frequency: "Muestreo ~2 min; máximo sobre el rango de fechas.",
    interpretation: "Pico de potencia registrado; útil para dimensionamiento y para detectar recortes (clipping) del inversor.",
  },
  powerFactor: {
    title: "Factor de Potencia",
    description: "Factor de potencia medio entregado por los inversores en el rango.",
    calculation: "Promedio del campo powerFactor reportado (avg_power_factor_pct).",
    dataSource: "Inversores solares del conector SCADA.",
    units: "adimensional (0–1).",
    frequency: "Muestreo ~2 min; promedio sobre el rango de fechas.",
    interpretation: "≥0.95 óptimo; <0.90 deficiente. Un FP bajo en generación afecta la calidad de la inyección a la red.",
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
    calculation: "Promedio de acFrequency (avg_frequency_hz).",
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
    description: "Velocidad media del viento en el día más reciente. Si la estación no tiene anemómetro se muestra N/A (no 0).",
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
    description: "Lluvia acumulada del día más reciente. Si la estación no tiene pluviómetro se muestra N/A (no 0).",
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
