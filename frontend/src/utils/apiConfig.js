// Configuración base de la API
export const API_BASE_URL = process.env.REACT_APP_API_URL;

// Endpoints organizados por categoría
export const ENDPOINTS = {
  dashboard: {
    kpi: '/api/dashboard/summary/',
    charts: '/api/dashboard/chart-data/',
    tasks: '/api/dashboard/tasks/'
  },
  electrical: {
    meters: '/api/electric-meters/',
    consumption: '/api/electric-meters/',
    details: '/api/electric-meters/',
    energy: '/api/electrical/energy/',
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
    delete: '/api/reports/delete/'  // usado por ExportReports; implementar en backend si no existe
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
  const url = new URL(API_BASE_URL + endpoint);
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
 * @returns {Promise} - Promesa resuelta con los datos o rechazada con error
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
      // Redirigir al login
      window.location.href = '/';
      return;
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
    if (error.message.includes('Token expirado')) {
      if (onAuthError) {
        onAuthError(error.message);
      }
    }
    throw error;
  }
};
