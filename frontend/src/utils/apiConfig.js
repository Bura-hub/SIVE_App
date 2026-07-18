// Configuración base de la API. Cadena vacía por defecto: permite despliegues
// same-origin (p. ej. detrás de un reverse proxy con rutas relativas) sin que
// `API_BASE_URL + endpoint` quede como "undefined/...".
export const API_BASE_URL = import.meta.env.VITE_API_URL || '';

// Endpoints organizados por categoría
export const ENDPOINTS = {
  dashboard: {
    kpi: '/api/dashboard/summary/',
    charts: '/api/dashboard/chart-data/',
    tasks: '/api/dashboard/tasks/'
  },
  dataAvailability: '/api/data-availability/',
  electrical: {
    // meters/consumption/details apuntan al endpoint de indicadores (fuente única);
    // los antiguos /api/electric-meters/ y /api/electrical/energy/ se retiraron (tablas vacías).
    meters: '/api/electric-meter-indicators/',
    consumption: '/api/electric-meter-indicators/',
    details: '/api/electric-meter-indicators/',
    indicators: '/api/electric-meter-indicators/',
    institutions: '/api/institutions/',
    devices: '/api/electric-meters/list/',
    calculate: '/api/electric-meters/calculate-new/',
  },
  inverters: {
    status: '/api/inverters/status/',
    generation: '/api/inverters/generation/',
    details: '/api/inverters/details/',
    indicators: '/api/inverter-indicators/',
    chartData: '/api/inverter-chart-data/',
    calculate: '/api/inverters/calculate/',
    list: '/api/inverters/list/'
  },
  weather: {
    current: '/api/weather/current/',
    forecast: '/api/weather/forecast/',
    details: '/api/weather/details/',
    indicators: '/api/weather-station-indicators/',
    chartData: '/api/weather-station-chart-data/',
    calculate: '/api/weather-stations/calculate/',
    stations: '/api/weather-stations/list/'
  },
  tasks: {
    sync: '/tasks/fetch-historical/',
    deviceSync: '/local/sync-devices/',
    kpiCalculation: '/api/dashboard/calculate-kpis/',
    dailyData: '/api/dashboard/calculate-daily-data/'
  },
  
  // Nuevos endpoints para generación de reportes
  reports: {
    generate: '/api/reports/generate/',
    status: '/api/reports/status/',
    download: '/api/reports/download/',
    history: '/api/reports/history/',
    delete: '/api/reports/delete/'  // DeleteReportView (indicators/views.py), filtra por usuario
  },
  
  // Endpoints para datos externos de energía
  externalEnergy: {
    prices: '/api/external-energy/prices/',
    savings: '/api/external-energy/savings/',
    sync: '/api/external-energy/sync/',
    marketOverview: '/api/external-energy/market-overview/'
  },

  // Estado de conexión SCADA
  scada: {
    connectionStatus: '/scada/connection-status/'
  }
};

/**
 * Función para construir URLs completas de la API
 * @param {string} endpoint - Endpoint de la API
 * @param {Object} params - Parámetros de consulta
 * @returns {string} - URL completa
 */
export const buildApiUrl = (endpoint, params = {}) => {
  // window.location.origin como base: si API_BASE_URL es absoluta, gana; si es
  // vacía/relativa, la URL resuelve contra el origen actual en vez de lanzar
  // "Invalid URL".
  const url = new URL(API_BASE_URL + endpoint, window.location.origin);
  Object.keys(params).forEach(key => {
    if (params[key] !== undefined && params[key] !== null) {
      url.searchParams.append(key, params[key]);
    }
  });
  return url.toString();
};

/**
 * Opciones por defecto para las peticiones fetch
 * @param {string} authToken - Token de autenticación
 * @returns {Object} - Opciones de configuración
 */
export const getDefaultFetchOptions = (authToken) => ({
  headers: {
    'Authorization': `Token ${authToken}`,
    'Content-Type': 'application/json'
  }
});

/**
 * Función para manejar errores de la API con manejo especial para autenticación
 * @param {Response} response - Respuesta de fetch
 * @param {Function} onAuthError - Callback para errores de autenticación
 * @returns {Promise} - Promesa resuelta con los datos o rechazada con error.
 *                      En 401 limpia la sesión, redirige al login y rechaza con un
 *                      error marcado con `isAuthError = true` para que los callers
 *                      puedan ignorarlo (nunca resuelve con undefined).
 */
export const handleApiResponse = async (response, onAuthError = null) => {
  if (!response.ok) {
    // Manejar errores de autenticación específicamente
    if (response.status === 401) {
      console.warn('Token expirado o inválido');
      if (onAuthError) {
        onAuthError('Token expirado. Por favor, inicie sesión nuevamente.');
      }
      // Limpiar token del localStorage
      localStorage.removeItem('authToken');
      localStorage.removeItem('username');
      localStorage.removeItem('isSuperuser');
      // Recargar la MISMA ruta de la app (no la raíz del dominio). La app es un SPA
      // por estado: al recargar con el token ya borrado, App.js no encuentra authToken
      // y renderiza el login. Antes, href='/' expulsaba al usuario a la raíz del
      // dominio (el portal WordPress), fuera de la app.
      window.location.reload();
      // Rechazar con un error controlado para que los callers no procesen datos undefined
      const authError = new Error('Token expirado. Por favor, inicie sesión nuevamente.');
      authError.isAuthError = true;
      throw authError;
    }

    const error = await response.json().catch(() => ({
      detail: 'Error de red desconocido'
    }));
    throw new Error(error.detail || `Error ${response.status}: ${response.statusText}`);
  }
  return response.json();
};

/**
 * Función para hacer peticiones fetch con manejo automático de errores de autenticación
 * @param {string} url - URL de la petición
 * @param {Object} options - Opciones de fetch
 * @param {Function} onAuthError - Callback para errores de autenticación
 * @returns {Promise} - Promesa con el resultado
 */
export const fetchWithAuth = async (url, options = {}, onAuthError = null) => {
  try {
    const response = await fetch(url, options);
    return await handleApiResponse(response, onAuthError);
  } catch (error) {
    // Los errores 401 (isAuthError) ya notificaron a onAuthError dentro de handleApiResponse
    if (!error.isAuthError && error.message.includes('Token expirado')) {
      if (onAuthError) {
        onAuthError(error.message);
      }
    }
    throw error;
  }
};
