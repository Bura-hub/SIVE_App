/**
 * Utilidades para manejo de fechas en zona horaria de Colombia
 * Zona horaria: America/Bogota (UTC-5)
 */

// Zona horaria de Colombia
const COLOMBIA_TIMEZONE = 'America/Bogota';

/**
 * Obtiene la fecha actual en zona horaria de Colombia
 * @returns {Date} Fecha actual en Colombia
 */
export const getCurrentDateInColombia = () => {
  return new Date().toLocaleString("en-US", {timeZone: COLOMBIA_TIMEZONE});
};

/**
 * Convierte una fecha a zona horaria de Colombia
 * @param {Date|string} date - Fecha a convertir
 * @returns {Date} Fecha en zona horaria de Colombia
 */
export const toColombiaTime = (date) => {
  const dateObj = typeof date === 'string' ? new Date(date) : date;
  return new Date(dateObj.toLocaleString("en-US", {timeZone: COLOMBIA_TIMEZONE}));
};

/**
 * Formatea una fecha para envío a la API (formato YYYY-MM-DD)
 * @param {Date} date - Fecha a formatear
 * @returns {string} Fecha en formato YYYY-MM-DD
 */
export const formatDateForAPI = (date) => {
  const colombiaDate = toColombiaTime(date);
  return colombiaDate.toISOString().split('T')[0];
};

/**
 * Formatea una fecha de la API (string YYYY-MM-DD) para mostrar en la interfaz
 * @param {string} dateString - Fecha en formato YYYY-MM-DD
 * @returns {string} Fecha en formato DD/MM/YYYY
 */
export const formatAPIDateForDisplay = (dateString) => {
  // Para fechas de la API que vienen como YYYY-MM-DD, no necesitamos conversión de timezone
  // Solo formatear directamente
  const [year, month, day] = dateString.split('-');
  return `${day}/${month}/${year}`;
};

/**
 * Formatea una fecha para mostrar en la interfaz (formato DD/MM/YYYY)
 * @param {Date|string} date - Fecha a formatear
 * @returns {string} Fecha en formato DD/MM/YYYY
 */
export const formatDateForDisplay = (date) => {
  // Si es un string de fecha de la API (YYYY-MM-DD), usar la función específica
  if (typeof date === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(date)) {
    return formatAPIDateForDisplay(date);
  }
  
  // Para otros casos, usar la conversión de timezone
  const colombiaDate = toColombiaTime(date);
  const day = String(colombiaDate.getDate()).padStart(2, '0');
  const month = String(colombiaDate.getMonth() + 1).padStart(2, '0');
  const year = colombiaDate.getFullYear();
  return `${day}/${month}/${year}`;
};

/**
 * Obtiene el primer día del mes actual en Colombia
 * @returns {Date} Primer día del mes actual
 */
export const getCurrentMonthStart = () => {
  const now = new Date();
  const colombiaDate = toColombiaTime(now);
  return new Date(colombiaDate.getFullYear(), colombiaDate.getMonth(), 1);
};

/**
 * Obtiene el último día del mes actual en Colombia
 * @returns {Date} Último día del mes actual
 */
export const getCurrentMonthEnd = () => {
  const now = new Date();
  const colombiaDate = toColombiaTime(now);
  return new Date(colombiaDate.getFullYear(), colombiaDate.getMonth() + 1, 0);
};

/**
 * Obtiene el último día del mes anterior en Colombia
 * @returns {Date} Último día del mes anterior
 */
export const getPreviousMonthEnd = () => {
  const now = new Date();
  const colombiaDate = toColombiaTime(now);
  return new Date(colombiaDate.getFullYear(), colombiaDate.getMonth(), 0);
};

/**
 * Obtiene el primer día del mes anterior en Colombia
 * @returns {Date} Primer día del mes anterior
 */
export const getPreviousMonthStart = () => {
  const now = new Date();
  const colombiaDate = toColombiaTime(now);
  return new Date(colombiaDate.getFullYear(), colombiaDate.getMonth() - 1, 1);
};

/**
 * Convierte una fecha de la API (string YYYY-MM-DD) a objeto Date para comparación
 * @param {string} dateString - Fecha en formato YYYY-MM-DD
 * @returns {Date} Fecha como objeto Date
 */
export const parseAPIDate = (dateString) => {
  // Para fechas de la API que vienen como YYYY-MM-DD, crear Date directamente
  return new Date(dateString + 'T00:00:00');
};

/**
 * Convierte una fecha ISO string a fecha en Colombia
 * @param {string} isoString - Fecha en formato ISO
 * @returns {Date} Fecha en zona horaria de Colombia
 */
export const parseISODateToColombia = (isoString) => {
  // Si es una fecha de la API (YYYY-MM-DD), usar parseAPIDate
  if (/^\d{4}-\d{2}-\d{2}$/.test(isoString)) {
    return parseAPIDate(isoString);
  }
  // Para otros casos, usar la conversión de timezone
  return toColombiaTime(new Date(isoString));
};

/**
 * Obtiene la fecha actual en Colombia como string ISO
 * @returns {string} Fecha actual en formato ISO
 */
export const getCurrentDateISO = () => {
  const colombiaDate = toColombiaTime(new Date());
  return colombiaDate.toISOString();
};

/**
 * Calcula la diferencia en días entre dos fechas
 * @param {Date} date1 - Primera fecha
 * @param {Date} date2 - Segunda fecha
 * @returns {number} Diferencia en días
 */
export const getDaysDifference = (date1, date2) => {
  const colombiaDate1 = toColombiaTime(date1);
  const colombiaDate2 = toColombiaTime(date2);
  const diffTime = Math.abs(colombiaDate2 - colombiaDate1);
  return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
};

/**
 * Verifica si una fecha es hoy en Colombia
 * @param {Date|string} date - Fecha a verificar
 * @returns {boolean} True si es hoy
 */
export const isTodayInColombia = (date) => {
  const colombiaDate = toColombiaTime(date);
  const today = toColombiaTime(new Date());
  return colombiaDate.toDateString() === today.toDateString();
};

const MONTHS_ES_FULL = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
  'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];
const MONTHS_ES_ABBR = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
  'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];

/** '2026-07-01' -> 'Jul 2026' (o 'Julio 2026' si abbreviated=false). */
export const formatMonthYearLabel = (dateString, { abbreviated = true } = {}) => {
  if (!dateString) return '';
  const [year, month] = dateString.split('-');
  const idx = parseInt(month, 10) - 1;
  const names = abbreviated ? MONTHS_ES_ABBR : MONTHS_ES_FULL;
  return `${names[idx]} ${year}`;
};

/** '2026-07' -> '2026-07-01'. */
export const monthInputToStartDate = (month) => `${month}-01`;

/** '2026-07' -> '2026-07-31' (último día real del mes). */
export const monthInputToEndDate = (month) => {
  const [year, m] = month.split('-').map(Number);
  const lastDay = new Date(year, m, 0).getDate(); // día 0 del mes siguiente
  return `${month}-${String(lastDay).padStart(2, '0')}`;
};

/** '2026-07-01' -> '2026-07'. */
export const dateStringToMonthInput = (dateString) => dateString.slice(0, 7);

/** Últimos 6 meses (inclusive el actual) en zona Colombia. */
export const getDefaultMonthlyRange = () => {
  const now = toColombiaTime(new Date());
  const end = new Date(now.getFullYear(), now.getMonth(), 1);
  const start = new Date(now.getFullYear(), now.getMonth() - 5, 1);
  const fmt = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
  return { startMonth: fmt(start), endMonth: fmt(end) };
};

/** Últimos 30 días. */
export const getDefaultDailyRange = () => {
  const end = toColombiaTime(new Date());
  const start = new Date(end);
  start.setDate(start.getDate() - 30);
  const fmt = (d) => d.toISOString().split('T')[0];
  return { startDate: fmt(start), endDate: fmt(end) };
};

/** Últimas 2 semanas (con hora), formato datetime-local YYYY-MM-DDTHH:MM. */
export const getDefaultHourlyRange = () => {
  const end = toColombiaTime(new Date());
  const start = new Date(end);
  start.setDate(start.getDate() - 14);
  const fmt = (d) =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-` +
    `${String(d.getDate()).padStart(2, '0')}T${String(d.getHours()).padStart(2, '0')}:` +
    `${String(d.getMinutes()).padStart(2, '0')}`;
  return { startDatetime: fmt(start), endDatetime: fmt(end) };
};

/** ISO con hora -> 'HH:MM' (zona Colombia). Extraído de los componentes Details. */
export const formatHourLabel = (isoHour) => {
  if (!isoHour) return '';
  const d = new Date(isoHour);
  if (isNaN(d.getTime())) return isoHour;
  return d.toLocaleTimeString('es-CO', {
    timeZone: COLOMBIA_TIMEZONE, hour: '2-digit', minute: '2-digit', hour12: false,
  });
};

/** Etiqueta de eje X según granularidad. Compartida por las 3 pantallas de detalle. */
export const buildAxisLabel = (item, timeRange) => {
  if (timeRange === 'hourly') return formatHourLabel(item.hour);
  if (timeRange === 'monthly') return formatMonthYearLabel(item.date);
  return new Date(item.date + 'T00:00:00').toLocaleDateString('es-ES');
}; 