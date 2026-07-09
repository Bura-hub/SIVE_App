// Configuración del backend
const config = {
    // URL base del backend Django. Vacío por defecto → rutas relativas same-origin
    // (evita "undefined/..." si REACT_APP_API_URL no está definido en build-time).
    API_BASE_URL: process.env.REACT_APP_API_URL || '',
    
    // Endpoints de autenticación
    ENDPOINTS: {
        LOGIN: '/auth/login/',
        REGISTER: '/auth/register/',
        LOGOUT: '/auth/logout/',
        REFRESH_TOKEN: '/auth/refresh/',
        CHANGE_PASSWORD: '/auth/change-password/',
        USER_PROFILE: '/auth/profile/',
        SESSIONS: '/auth/sessions/',
        LOGOUT_ALL: '/auth/logout-all/',
        REGISTER_USER: '/auth/register/',
    }
};

// Función para construir URLs completas
export const buildApiUrl = (endpoint) => {
    return `${config.API_BASE_URL}${endpoint}`;
};

// Función para obtener endpoint específico
export const getEndpoint = (key) => {
    return config.ENDPOINTS[key];
};

export default config;
