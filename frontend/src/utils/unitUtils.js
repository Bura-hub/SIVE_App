// Constantes para las unidades y sus conversiones
export const unitConversions = {
  power: {
    W: 1,
    kW: 1000,
    MW: 1000000,
    VAr: 1,
    kVAR: 1000,
    MVAR: 1000000,
    VA: 1,
    kVA: 1000,
    MVA: 1000000
  },
  energy: {
    Wh: 1,
    kWh: 1000,
    MWh: 1000000,
    VArh: 1,
    kVARh: 1000,
    MVARh: 1000000,
    VAh: 1,
    kVAh: 1000,
    MVAh: 1000000
  },
  temperature: {
    '°C': 1,
    '°F': 'special'
  },
  humidity: {
    '%RH': 1
  },
  speed: {
    'km/h': 1,
    'm/s': 3.6
  }
};

/**
 * Convierte un valor de una unidad a otra
 * @param {number} value - Valor a convertir
 * @param {string} fromUnit - Unidad original
 * @param {string} toUnit - Unidad destino
 * @param {string} type - Tipo de medida (power, energy, etc.)
 * @returns {number} - Valor convertido
 */
export const convertUnit = (value, fromUnit, toUnit, type = 'power') => {
  if (value === null || value === undefined) return 0;
  if (fromUnit === toUnit) return value;

  const conversions = unitConversions[type];
  if (!conversions) throw new Error(`Tipo de unidad no soportado: ${type}`);

  // Manejo especial para conversiones de temperatura
  if (type === 'temperature') {
    if (fromUnit === '°F' && toUnit === '°C') {
      return (value - 32) * (5/9);
    } else if (fromUnit === '°C' && toUnit === '°F') {
      return (value * (9/5)) + 32;
    }
  }

  return (value * conversions[fromUnit]) / conversions[toUnit];
};

/**
 * Formatea un valor numérico con su unidad
 * @param {number} value - Valor a formatear
 * @param {string} unit - Unidad del valor
 * @param {number} decimals - Número de decimales
 * @returns {string} - Valor formateado con unidad
 */
export const formatWithUnit = (value, unit, decimals = 2) => {
  if (value === null || value === undefined) return 'N/A';
  return `${value.toFixed(decimals)} ${unit}`;
};

/**
 * Determina el estado de un valor basado en umbrales
 * @param {number} value - Valor a evaluar
 * @param {Object} thresholds - Umbrales para cada estado
 * @returns {string} - Estado del valor (success, warning, error, normal)
 */
export const getValueStatus = (value, thresholds) => {
  if (!thresholds) return 'normal';
  
  if (value >= thresholds.error) return 'error';
  if (value >= thresholds.warning) return 'warning';
  if (value >= thresholds.success) return 'success';
  return 'normal';
};

/**
 * Objeto con las configuraciones de umbrales para diferentes medidas
 */
export const defaultThresholds = {
  temperature: {
    success: 18,
    warning: 25,
    error: 30
  },
  humidity: {
    success: 30,
    warning: 60,
    error: 80
  },
  powerFactor: {
    success: 0.95,
    warning: 0.85,
    error: 0.8
  }
};

/**
 * Número con coma decimal (es-CO) y una cantidad fija de decimales.
 */
export const formatNumber = (value, decimals = 2) =>
  new Intl.NumberFormat('es-CO', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
    .format(Number(value) || 0);

// Escalas por unidad base: se sube de prefijo mientras la cifra llegue a 1000.
const UNIT_SCALES = {
  kWh: ['kWh', 'MWh', 'GWh'],
  kW: ['kW', 'MW', 'GW'],
};

/**
 * Valor y unidad para una tarjeta: la unidad sube de prefijo (kWh → MWh → GWh, kW → MW → GW) para que la cifra
 * quede por debajo de 1000, con coma decimal. Las unidades sin escala se devuelven tal cual, solo formateadas.
 * @returns {{value: string, unit: string}}
 */
export const scaleUnit = (value, unit, decimals = 2) => {
  let v = Number(value) || 0;
  const scale = UNIT_SCALES[unit];
  if (!scale) return { value: formatNumber(v, decimals), unit };
  let i = 0;
  while (Math.abs(v) >= 1000 && i < scale.length - 1) {
    v /= 1000;
    i += 1;
  }
  return { value: formatNumber(v, decimals), unit: scale[i] };
};
