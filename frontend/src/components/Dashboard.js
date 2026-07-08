// Importaciones necesarias de React y componentes personalizados
import React, { useState, useEffect, useCallback } from 'react';
import { ChartCard } from "./KPI/ChartCard";
import TransitionOverlay from './TransitionOverlay';

// Utilidades para manejo de fechas en zona horaria de Colombia
import { 
  formatDateForAPI, 
  getCurrentMonthStart, 
  getCurrentMonthEnd, 
  getPreviousMonthStart,
  getPreviousMonthEnd,
  formatAPIDateForDisplay, // Nueva función
  parseISODateToColombia
} from '../utils/dateUtils';

// Importar funciones de manejo de errores de autenticación y utilidades de API
import * as apiUtils from '../utils/apiConfig';

// Importaciones desde Chart.js y el plugin de zoom
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  Filler // Para gráficos con relleno de área
} from 'chart.js';
import zoomPlugin from 'chartjs-plugin-zoom'

// Registro de los componentes de Chart.js necesarios
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  Filler,
  zoomPlugin
);





// Estados posibles para las tareas
export const TaskStatus = {
  IDLE: 'idle',
  RUNNING: 'running',
  COMPLETED: 'completed',
  ERROR: 'error'
};

/**
 * Clase para manejar las tareas de Celery
 */
export class TaskManager {
  constructor(authToken, onStatusChange) {
    this.authToken = authToken;
    this.onStatusChange = onStatusChange;
    this.activeTasks = new Map();
  }

  /**
   * Ejecuta una tarea específica
   * @param {string} taskType - Tipo de tarea a ejecutar
   * @param {Object} params - Parámetros para la tarea
   * @returns {Promise} - Promesa con el resultado de la tarea
   */
  async executeTask(taskType, params = {}) {
    this._updateTaskStatus(taskType, TaskStatus.RUNNING);

    try {
      const endpoint = this._getEndpointForTask(taskType);
      const data = await apiUtils.fetchWithAuth(
        apiUtils.buildApiUrl(endpoint), 
        {
          method: 'POST',
          ...apiUtils.getDefaultFetchOptions(this.authToken),
          body: JSON.stringify(params)
        },
        (message) => {
          console.warn(`Error de autenticación en tarea ${taskType}: ${message}`);
        }
      );
      
      this._updateTaskStatus(taskType, TaskStatus.COMPLETED);
      return data;
    } catch (error) {
      this._updateTaskStatus(taskType, TaskStatus.ERROR, error.message);
      throw error;
    }
  }

  /**
   * Ejecuta una secuencia de tareas en orden
   * @param {Array} tasks - Array de objetos de tarea
   * @returns {Promise} - Promesa con los resultados de todas las tareas
   */
  async executeTaskSequence(tasks) {
    const results = [];
    for (const task of tasks) {
      try {
        const result = await this.executeTask(task.type, task.params);
        results.push({ type: task.type, success: true, data: result });
      } catch (error) {
        results.push({ type: task.type, success: false, error: error.message });
        if (task.critical) break;
      }
    }
    return results;
  }

  /**
   * Obtiene el endpoint correspondiente a un tipo de tarea
   * @private
   */
  _getEndpointForTask(taskType) {
    switch (taskType) {
      case 'sync':
        return apiUtils.ENDPOINTS.tasks.sync;
      case 'deviceSync':
        return apiUtils.ENDPOINTS.tasks.deviceSync;
      case 'kpiCalculation':
        return apiUtils.ENDPOINTS.tasks.kpiCalculation;
      case 'dailyData':
        return apiUtils.ENDPOINTS.tasks.dailyData;
      default:
        throw new Error(`Tipo de tarea no soportado: ${taskType}`);
    }
  }

  /**
   * Actualiza el estado de una tarea
   * @private
   */
  _updateTaskStatus(taskType, status, error = null) {
    const taskState = {
      status,
      timestamp: new Date(),
      error
    };
    
    this.activeTasks.set(taskType, taskState);
    if (this.onStatusChange) {
      this.onStatusChange(taskType, taskState);
    }
  }
}

// Definir los iconos fuera del componente ya que son constantes
const Icons = {
  consumption: <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="lucide lucide-zap" aria-hidden="true"><path d="M13 2L3 14h9l-1 8 11-12h-9l1-8z"></path></svg>,
  
  generation: <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="lucide lucide-solar-panel" aria-hidden="true"><path d="M12 2v20"></path><path d="M2 12h20"></path><path d="M20 12v8a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-8"></path><path d="M4 12V4a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v8"></path><path d="M12 6v4"></path><path d="M8 8h8"></path></svg>,
  
  balance: <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="lucide lucide-scale" aria-hidden="true"><path d="M12 3V19"></path><path d="M6 15H18"></path><path d="M14 11V19"></path><path d="M10 11V19"></path><path d="M12 19L19 12L22 15L12 19"></path><path d="M12 19L5 12L2 15L12 19"></path></svg>,
  
  inverters: <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="lucide lucide-cpu" aria-hidden="true"><rect x="4" y="4" width="16" height="16" rx="2" ry="2"></rect><rect x="9" y="9" width="6" height="6"></rect><path d="M9 1v3"></path><path d="M15 1v3"></path><path d="M9 21v3"></path><path d="M15 21v3"></path><path d="M1 9h3"></path><path d="M1 15h3"></path><path d="M21 9h3"></path><path d="M21 15h3"></path></svg>,
  
  power: <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="lucide lucide-power" aria-hidden="true"><path d="M12 2v5"></path><path d="M18 13v-2"></path><path d="M6 13v-2"></path><path d="M4.9 16.5l3.5-3.5"></path><path d="M19.1 16.5l-3.5-3.5"></path><path d="M12 19v3"></path><path d="M12 12v4"></path></svg>,
  
  temperature: <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="lucide lucide-thermometer" aria-hidden="true"><path d="M14 4v10.54a4 4 0 1 1-4 0V4a2 2 0 0 1 4 0Z"></path></svg>,
  
  humidity: <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="lucide lucide-droplets" aria-hidden="true"><path d="M7 16.3c2.2 0 4-1.83 4-4.05 0-1.16-.57-2.26-1.71-3.19S7.29 6.75 7 5.3c-.29 1.45-1.14 2.84-2.29 3.76S3 11.1 3 12.25c0 2.22 1.8 4.05 4 4.05z"></path><path d="M12.56 6.6A10.97 10.97 0 0 0 14 3.02c.5 2.5 2 4.9 4 6.5s3 3.5 3 5.5a6.98 6.98 0 0 1-11.91 4.97"></path></svg>,
  
  wind: <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="lucide lucide-wind" aria-hidden="true"><path d="M5 8h10"></path><path d="M4 12h16"></path><path d="M8 16h8"></path></svg>,
  
  irradiance: <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="lucide lucide-sun" aria-hidden="true"><circle cx="12" cy="12" r="4"></circle><path d="m4.93 4.93 4.24 4.24"></path><path d="m14.83 9.17 4.24-4.24"></path><path d="m14.83 14.83 4.24 4.24"></path><path d="m9.17 14.83-4.24 4.24"></path><path d="M3 12h1"></path><path d="M12 3v1"></path><path d="M12 20v1"></path><path d="M20 12h1"></path><path d="M3 12h1"></path><path d="M12 3v1"></path><path d="M12 20v1"></path><path d="M20 12h1"></path></svg>
};

// Componente principal del dashboard
function Dashboard({ authToken, onLogout, username, isSuperuser, navigateTo, isSidebarMinimized, setIsSidebarMinimized }) {
  // Primero definimos la función showTransitionAnimation
  const showTransitionAnimation = useCallback((type = 'info', message = '', duration = 2000) => {
    setTransitionType(type);
    setTransitionMessage(message);
    setShowTransition(true);
    
      setTimeout(() => {
      setShowTransition(false);
    }, duration);
  }, []);

  // Luego definimos handleTaskStatusChange que usa showTransitionAnimation
  const handleTaskStatusChange = useCallback((taskType, taskState) => {
    setTaskStates(prev => ({
      ...prev,
      [taskType]: taskState
    }));

    if (taskState.status === TaskStatus.RUNNING) {
      showTransitionAnimation('info', `Ejecutando tarea: ${taskType}...`);
    } else if (taskState.status === TaskStatus.COMPLETED) {
      showTransitionAnimation('success', `Tarea ${taskType} completada`);
    } else if (taskState.status === TaskStatus.ERROR) {
      showTransitionAnimation('error', `Error en tarea ${taskType}: ${taskState.error}`);
    }
  }, [showTransitionAnimation]);

  // Ahora declaramos todos los estados
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedTimeRange, setSelectedTimeRange] = useState('Últimos 30 días');
  const [selectedLocation, setSelectedLocation] = useState('Todas');
  const [selectedDevice, setSelectedDevice] = useState('Todos');
  const [taskExecuting, setTaskExecuting] = useState(false);
  const [taskStatus, setTaskStatus] = useState('');
  const [taskStates, setTaskStates] = useState({});
  const [showTransition, setShowTransition] = useState(false);
  const [transitionType, setTransitionType] = useState('info');
  const [transitionMessage, setTransitionMessage] = useState('');
  const [scadaConnection, setScadaConnection] = useState({ connected: null, message: '' });
  const [hasDashboardData, setHasDashboardData] = useState(true);

  // Creamos el taskManager después de tener todas las funciones necesarias
  const [taskManager] = useState(() => new TaskManager(authToken, handleTaskStatusChange));

  // Estados para los datos
  const [kpiData, setKpiData] = useState({
    totalConsumption: { title: "Consumo total", value: "Cargando...", unit: "", change: "", status: "normal", icon: Icons.consumption },
    totalGeneration: { title: "Generación total", value: "Cargando...", unit: "", change: "", status: "normal", icon: Icons.generation },
    energyBalance: { title: "Equilibrio energético", value: "Cargando...", unit: "", description: "", status: "normal", icon: Icons.balance },
    activeInverters: { title: "Inversores activos", value: "Cargando...", unit: "", description: "", status: "normal", icon: Icons.inverters },
    averageInstantaneousPower: { title: "Pot. instan. promedio", value: "Cargando...", unit: "kW", description: "", status: "normal", icon: Icons.power },
    avgDailyTemp: { title: "Temp. prom. diaria", value: "Cargando...", unit: "°C", description: "Rango normal", status: "normal", icon: Icons.temperature },
    relativeHumidity: { title: "Humedad relativa", value: "Cargando...", unit: "%", description: "", status: "normal", icon: Icons.humidity },
    windSpeed: { title: "Velocidad del viento", value: "Cargando...", unit: "km/h", description: "Moderado", status: "moderado", icon: Icons.wind },
    irradiance: { title: "Irradiancia solar", value: "N/A", unit: "W/m²", description: "Datos no disponibles", status: "normal", icon: Icons.irradiance }
  });

  // Estado para mostrar información detallada de KPIs
  const [showKpiInfo, setShowKpiInfo] = useState(null);
  const [isAnimating, setIsAnimating] = useState(false);
  const [isOpening, setIsOpening] = useState(false);

  const [electricityConsumptionData, setElectricityConsumptionData] = useState(null);
  const [inverterGenerationData, setInverterGenerationData] = useState(null);
  const [temperatureTrendsData, setTemperatureTrendsData] = useState(null);
  const [energyBalanceData, setEnergyBalanceData] = useState(null);
  const [windSpeedData, setWindSpeedData] = useState(null);
  const [irradianceData, setIrradianceData] = useState(null);

  // Función mejorada para ejecutar todas las tareas
  const executeAllTasks = async () => {
    if (taskExecuting) return;
    setTaskExecuting(true);

    try {
      const tasks = [
        { type: 'deviceSync', critical: true },
        { type: 'sync', params: { time_range_seconds: 172800 }, critical: false },
        { type: 'kpiCalculation', critical: false },
        { type: 'dailyData', params: { days_back: 3 }, critical: false }
      ];

      const results = await taskManager.executeTaskSequence(tasks);
      const hasErrors = results.some(result => !result.success);

      if (hasErrors) {
        showTransitionAnimation('warning', 'Algunas tareas no se completaron correctamente', 3000);
      } else {
        showTransitionAnimation('success', 'Todas las tareas completadas exitosamente', 2000);
      }

      // Recargar datos después de completar las tareas
      await fetchDashboardData();

    } catch (error) {
      console.error('Error en la ejecución de tareas:', error);
      showTransitionAnimation('error', 'Error en la ejecución de tareas', 3000);
    } finally {
      setTaskExecuting(false);
    }
  };

  // Hook de efecto para cargar datos desde la API
  const fetchDashboardData = async (signal = null) => {
    setLoading(true);
    setError(null);

    try {
      // Fechas para las consultas
      const dates = {
        currentMonth: {
          start: getCurrentMonthStart(),
          end: getCurrentMonthEnd()
        },
        prevMonth: {
          start: getPreviousMonthStart(),
          end: getPreviousMonthEnd()
        }
      };

      // Función para manejar errores de autenticación
      const handleAuthError = (message) => {
        setError(message);
        // El usuario será redirigido automáticamente por handleApiResponse
      };

      // Realizar todas las llamadas en paralelo usando fetchWithAuth
      const [kpisData, currentMonthCharts, prevMonthCharts] = await Promise.all([
        apiUtils.fetchWithAuth(
          apiUtils.buildApiUrl(apiUtils.ENDPOINTS.dashboard.kpi),
          { ...apiUtils.getDefaultFetchOptions(authToken), signal },
          handleAuthError
        ),
        apiUtils.fetchWithAuth(
          apiUtils.buildApiUrl(apiUtils.ENDPOINTS.dashboard.charts, {
            start_date: formatDateForAPI(dates.currentMonth.start),
            end_date: formatDateForAPI(dates.currentMonth.end)
          }),
          { ...apiUtils.getDefaultFetchOptions(authToken), signal },
          handleAuthError
        ),
        apiUtils.fetchWithAuth(
          apiUtils.buildApiUrl(apiUtils.ENDPOINTS.dashboard.charts, {
            start_date: formatDateForAPI(dates.prevMonth.start),
            end_date: formatDateForAPI(dates.prevMonth.end)
          }),
          { ...apiUtils.getDefaultFetchOptions(authToken), signal },
          handleAuthError
        )
      ]);

      // Actualizar KPIs con las unidades correctas
      updateKPIs(kpisData);

      // Guardar si hay datos para mostrar mensaje informativo
      setHasDashboardData(kpisData.hasData !== false);

      // Procesar y actualizar datos de gráficos
      updateCharts(currentMonthCharts, prevMonthCharts);

      // Verificar estado de conexión SCADA (no fallar el dashboard si falla)
      try {
        const connData = await apiUtils.fetchWithAuth(
          apiUtils.buildApiUrl(apiUtils.ENDPOINTS.scada.connectionStatus),
          { ...apiUtils.getDefaultFetchOptions(authToken), signal },
          handleAuthError
        );
        setScadaConnection({ connected: connData.connected, message: connData.message || '' });
      } catch (scadaError) {
        // Propagar cancelaciones y errores de sesión al manejador externo
        if (scadaError.name === 'AbortError' || scadaError.isAuthError) throw scadaError;
        setScadaConnection({ connected: false, message: 'No se pudo verificar la conexión SCADA.' });
      }
    } catch (error) {
      // Ignorar peticiones canceladas (desmontaje del componente)
      if (error.name === 'AbortError') return;
      setError(error.message);
      console.error('Error al cargar datos del dashboard:', error);
    } finally {
      if (!signal || !signal.aborted) {
        setLoading(false);
      }
    }
  };

  // Función para actualizar KPIs
  const updateKPIs = (data) => {
    setKpiData(prevKpiData => ({
      ...prevKpiData,
      totalConsumption: {
        ...(data.totalConsumption || {}),
        value: data.totalConsumption ? parseFloat(data.totalConsumption.value) : 0, // Usar el valor tal como viene del backend
        icon: Icons.consumption,
        color: "text-blue-600",
        // Usar el valor del mes anterior del backend
        previousMonthValue: data.totalConsumption?.previousMonthValue || data.totalConsumption?.previousMonth || 0,
        change: data.totalConsumption?.change || "Datos disponibles"
      },
      totalGeneration: {
        ...(data.totalGeneration || {}),
        value: data.totalGeneration ? parseFloat(data.totalGeneration.value) : 0, // Usar el valor tal como viene del backend
        icon: Icons.generation,
        color: "text-green-600",
        // Usar el valor del mes anterior del backend
        previousMonthValue: data.totalGeneration?.previousMonthValue || data.totalGeneration?.previousMonth || 0,
        change: data.totalGeneration?.change || "Datos disponibles"
      },
      energyBalance: {
        ...(data.energyBalance || {}),
        value: data.energyBalance ? parseFloat(data.energyBalance.value) : 0, // Usar el valor tal como viene del backend
        icon: Icons.balance,
        color: "text-purple-600"
      },
      averageInstantaneousPower: {
        ...(data.averageInstantaneousPower || {}),
        value: data.averageInstantaneousPower ? parseFloat(data.averageInstantaneousPower.value) : 0, // Usar el valor tal como viene del backend
        icon: Icons.power,
        color: "text-orange-600",
        // Usar el valor del mes anterior del backend
        previousMonthValue: data.averageInstantaneousPower?.previousMonthValue || data.averageInstantaneousPower?.previousMonth || 0,
        change: data.averageInstantaneousPower?.change || "Datos disponibles"
      },
      avgDailyTemp: {
        ...(data.avgDailyTemp || {}),
        value: data.avgDailyTemp ? parseFloat(data.avgDailyTemp.value) : 0, // Usar el valor tal como viene del backend
        icon: Icons.temperature,
        color: "text-red-600",
        // Usar el valor del mes anterior del backend
        previousMonthValue: data.avgDailyTemp?.previousMonthValue || data.avgDailyTemp?.previousMonth || 0,
        change: data.avgDailyTemp?.change || "Datos disponibles"
      },
      relativeHumidity: {
        ...(data.relativeHumidity || {}),
        value: data.relativeHumidity ? parseFloat(data.relativeHumidity.value) : 0, // Usar el valor tal como viene del backend
        icon: Icons.humidity,
        color: "text-cyan-600",
        // Usar el valor del mes anterior del backend
        previousMonthValue: data.relativeHumidity?.previousMonthValue || data.relativeHumidity?.previousMonth || 0,
        change: data.relativeHumidity?.change || "Datos disponibles"
      },
      windSpeed: {
        ...(data.windSpeed || {}),
        value: data.windSpeed ? parseFloat(data.windSpeed.value) : 0, // Usar el valor tal como viene del backend
        icon: Icons.wind,
        color: "text-teal-600",
        // Usar el valor del mes anterior del backend
        previousMonthValue: data.windSpeed?.previousMonthValue || data.windSpeed?.previousMonth || 0,
        change: data.windSpeed?.change || "Datos disponibles"
      },
      irradiance: {
        // Para irradiancia, usar valores por defecto hasta que el backend lo proporcione
        title: "Irradiancia solar",
        value: data.irradiance ? parseFloat(data.irradiance.value) : "N/A",
        unit: "W/m²",
        description: "Rango normal",
        status: "normal",
        icon: Icons.irradiance,
        color: "text-amber-600",
        previousMonthValue: data.irradiance?.previousMonthValue || data.irradiance?.previousMonth || 0,
        change: data.irradiance?.change || "Datos no disponibles"
      },
      activeInverters: {
        ...(data.activeInverters || {}),
        value: data.activeInverters ? parseInt(data.activeInverters.value) : 0, // Usar el valor tal como viene del backend
        icon: Icons.inverters,
        color: "text-indigo-600"
      }
        }));
  };

  // Función para actualizar gráficos
  const updateCharts = (currentData, previousData) => {
    // Ordenar datos por fecha
    const sortedCurrentData = currentData.sort((a, b) => 
      parseISODateToColombia(a.date) - parseISODateToColombia(b.date)
    );
    const sortedPrevData = previousData.sort((a, b) => 
      parseISODateToColombia(a.date) - parseISODateToColombia(b.date)
    );

    // Calcular el consumo total del mes anterior
    const previousMonthTotalConsumption = sortedPrevData.reduce((total, item) => {
      return total + parseFloat(item.daily_consumption || 0);
    }, 0);

    // Actualizar KPIs con la información del mes anterior
    updateKPIsWithPreviousMonth(previousMonthTotalConsumption);

    // Actualizar cada gráfico con los datos procesados
    updateConsumptionChart(sortedCurrentData, sortedPrevData);
    updateGenerationChart(sortedCurrentData, sortedPrevData);
    updateBalanceChart(sortedCurrentData, sortedPrevData);
    updateTemperatureChart(sortedCurrentData, sortedPrevData);
    updateWindSpeedChart(sortedCurrentData, sortedPrevData);
    updateIrradianceChart(sortedCurrentData, sortedPrevData);
  };

  // Nueva función para actualizar KPIs con información del mes anterior
  const updateKPIsWithPreviousMonth = (previousMonthTotalConsumption) => {
    setKpiData(prevKpiData => {
      return {
        ...prevKpiData,
        totalConsumption: {
          ...prevKpiData.totalConsumption,
          // No sobrescribir previousMonthValue, mantener el del backend
          change: prevKpiData.totalConsumption?.change || "Datos disponibles"
        }
      };
    });
  };

  // useEffect para manejar la animación de apertura
  useEffect(() => {
    if (showKpiInfo && isOpening) {
      // Pequeño delay para que la animación de entrada funcione
      const timer = setTimeout(() => {
        setIsOpening(false);
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [showKpiInfo, isOpening]);

  // Función para obtener información detallada de cada KPI
  const getKpiDetailedInfo = (kpiKey) => {
    const kpiInfo = {
      totalConsumption: {
        title: "Consumo Total de Energía",
        description: "Representa la cantidad total de energía eléctrica consumida por todas las instalaciones monitoreadas.",
        calculation: "Se calcula sumando el totalActivePower de todos los medidores eléctricos activos durante el período mensual.",
        dataSource: "Datos obtenidos de medidores eléctricos SCADA en tiempo real.",
        units: "kWh (convertido a MWh para visualización)",
        frequency: "Actualización cada 5 minutos desde SCADA, cálculo mensual automático."
      },
      totalGeneration: {
        title: "Generación Total de Energía",
        description: "Representa la cantidad total de energía solar generada por todos los inversores activos.",
        calculation: "Se calcula sumando la energía generada por todos los inversores solares durante el período mensual.",
        dataSource: "Datos obtenidos de inversores solares SCADA en tiempo real.",
        units: "kWh (convertido a MWh para visualización)",
        frequency: "Actualización cada 5 minutos desde SCADA, cálculo mensual automático."
      },
      energyBalance: {
        title: "Equilibrio Energético",
        description: "Representa la diferencia entre la energía generada y la consumida (Generación - Consumo).",
        calculation: "Balance = Generación Total - Consumo Total. Valores positivos indican superávit, negativos déficit.",
        dataSource: "Cálculo derivado de los KPIs de generación y consumo.",
        units: "kWh (convertido a MWh para visualización)",
        frequency: "Cálculo automático mensual basado en generación y consumo."
      },
      averageInstantaneousPower: {
        title: "Potencia Instantánea Promedio",
        description: "Representa la potencia promedio que están generando los inversores solares en tiempo real.",
        calculation: "Se calcula como el promedio de la potencia instantánea de todos los inversores activos durante el período.",
        dataSource: "Datos de potencia instantánea de inversores solares SCADA.",
        units: "W (convertido a kW para visualización)",
        frequency: "Actualización cada 5 minutos desde SCADA, promedio mensual automático."
      },
      avgDailyTemp: {
        title: "Temperatura Promedio Diaria",
        description: "Representa la temperatura ambiental promedio registrada por las estaciones meteorológicas.",
        calculation: "Se calcula como el promedio de las temperaturas máximas y mínimas diarias registradas.",
        dataSource: "Datos de estaciones meteorológicas SCADA y sensores locales.",
        units: "°C (grados Celsius)",
        frequency: "Actualización cada hora, promedio diario y mensual automático."
      },
      relativeHumidity: {
        title: "Humedad Relativa Promedio",
        description: "Representa el porcentaje de humedad en el aire respecto a la capacidad máxima de retención.",
        calculation: "Se calcula como el promedio de las mediciones de humedad relativa durante el período.",
        dataSource: "Sensores de humedad en estaciones meteorológicas SCADA.",
        units: "% (porcentaje)",
        frequency: "Actualización cada hora, promedio mensual automático."
      },
      windSpeed: {
        title: "Velocidad del Viento Promedio",
        description: "Representa la velocidad promedio del viento registrada por las estaciones meteorológicas.",
        calculation: "Se calcula como el promedio de las velocidades del viento registradas durante el período.",
        dataSource: "Anemómetros en estaciones meteorológicas SCADA.",
        units: "km/h (kilómetros por hora)",
        frequency: "Actualización cada hora, promedio mensual automático."
      },
      irradiance: {
        title: "Irradiancia Solar Promedio",
        description: "Representa la intensidad promedio de radiación solar incidente en la superficie.",
        calculation: "Se calcula como el promedio de las mediciones de irradiancia durante el período.",
        dataSource: "Piranómetros en estaciones meteorológicas SCADA.",
        units: "W/m² (vatios por metro cuadrado)",
        frequency: "Actualización cada hora, promedio mensual automático."
      },
      activeInverters: {
        title: "Inversores Activos",
        description: "Representa el número de inversores solares que están funcionando correctamente.",
        calculation: "Se cuenta el número de inversores con estado 'online' en el sistema SCADA.",
        dataSource: "Estado de conexión de inversores en tiempo real desde SCADA.",
        units: "Cantidad (número de inversores)",
        frequency: "Verificación cada 5 minutos desde SCADA."
      }
    };
    
    return kpiInfo[kpiKey] || null;
  };

  // Modificar las funciones de actualización de gráficos para usar unidades dinámicas
  const updateConsumptionChart = (currentData, prevData) => {
    const units = currentData[0]?.units?.consumption || 'kWh';
    
    setElectricityConsumptionData({
      labels: currentData.map(item => formatAPIDateForDisplay(item.date)),
      datasets: [
        {
          label: `Actual (${units})`,
          data: currentData.map(item => parseFloat(item.daily_consumption)),
          borderColor: '#3B82F6',
          backgroundColor: 'rgba(59, 130, 246, 0.2)',
          fill: true,
          tension: 0.4
        },
        {
          label: `Anterior (${units})`,
          data: prevData.map(item => parseFloat(item.daily_consumption)),
          borderColor: '#6B7280',
          backgroundColor: 'rgba(107, 114, 128, 0.2)',
          fill: true,
          tension: 0.4
        }
      ]
    });
  };

  const updateGenerationChart = (currentData, prevData) => {
    const units = currentData[0]?.units?.generation || 'kWh';
    
    setInverterGenerationData({
      labels: currentData.map(item => formatAPIDateForDisplay(item.date)),
      datasets: [
        {
          label: `Actual (${units})`,
          data: currentData.map(item => parseFloat(item.daily_generation)),
          backgroundColor: '#10B981',
          borderColor: '#059669',
          borderWidth: 1,
          borderRadius: 5,
        },
        {
          label: `Anterior (${units})`,
          data: prevData.map(item => parseFloat(item.daily_generation)),
          backgroundColor: 'rgba(107, 114, 128, 0.6)',
          borderColor: '#6B7280',
          borderWidth: 1,
          borderRadius: 5,
        }
      ]
    });
  };

  const updateBalanceChart = (currentData, prevData) => {
    const units = currentData[0]?.units?.balance || 'kWh';
    
    setEnergyBalanceData({
      labels: currentData.map(item => formatAPIDateForDisplay(item.date)),
      datasets: [
        {
          label: `Actual (${units})`,
          data: currentData.map(item => parseFloat(item.daily_balance)),
          borderColor: '#8B5CF6',
          backgroundColor: (context) => {
            const chart = context.chart;
            const { ctx, chartArea } = chart;
            if (!chartArea) return;
            const gradient = ctx.createLinearGradient(0, chartArea.bottom, 0, chartArea.top);
            gradient.addColorStop(0, 'rgba(139, 92, 246, 0.5)');
            gradient.addColorStop(0.5, 'rgba(139, 92, 246, 0.2)');
            gradient.addColorStop(1, 'rgba(139, 92, 246, 0.0)');
            return gradient;
          },
          fill: true,
          tension: 0.4,
        },
        {
          label: `Anterior (${units})`,
          data: prevData.map(item => parseFloat(item.daily_balance)),
          borderColor: '#6B7280',
          backgroundColor: 'rgba(107, 114, 128, 0.2)',
          fill: true,
          tension: 0.4,
        }
      ]
    });
  };

  const updateTemperatureChart = (currentData, prevData) => {
        setTemperatureTrendsData({
      labels: currentData.map(item => formatAPIDateForDisplay(item.date)),
          datasets: [
            {
              label: 'Actual (°C)',
          data: currentData.map(item => parseFloat(item.avg_daily_temp)), // Usar valor tal como viene del backend
              borderColor: 'rgb(255, 159, 64)',
              backgroundColor: 'rgba(255, 159, 64, 0.5)',
              tension: 0.4,
              fill: false,
            },
            {
              label: 'Anterior (°C)',
          data: prevData.map(item => parseFloat(item.avg_daily_temp)), // Usar valor tal como viene del backend
              borderColor: '#6B7280',
              backgroundColor: 'rgba(107, 114, 128, 0.5)',
              tension: 0.4,
              fill: false,
        }
      ]
    });
  };

  const updateWindSpeedChart = (currentData, prevData) => {
    setWindSpeedData({
      labels: currentData.map(item => formatAPIDateForDisplay(item.date)),
      datasets: [
        {
          label: 'Actual (km/h)',
          data: currentData.map(item => parseFloat(item.avg_wind_speed || 0)),
          borderColor: 'rgb(20, 184, 166)',
          backgroundColor: 'rgba(20, 184, 166, 0.5)',
          tension: 0.4,
          fill: false,
        },
        {
          label: 'Anterior (km/h)',
          data: prevData.map(item => parseFloat(item.avg_wind_speed || 0)),
          borderColor: '#6B7280',
          backgroundColor: 'rgba(107, 114, 128, 0.5)',
          tension: 0.4,
          fill: false,
        }
      ]
    });
  };

  const updateIrradianceChart = (currentData, prevData) => {
    setIrradianceData({
      labels: currentData.map(item => formatAPIDateForDisplay(item.date)),
      datasets: [
        {
          label: 'Actual (W/m²)',
          data: currentData.map(item => parseFloat(item.avg_irradiance || 0)),
          borderColor: 'rgb(245, 158, 11)',
          backgroundColor: 'rgba(245, 158, 11, 0.5)',
          tension: 0.4,
          fill: false,
        },
        {
          label: 'Anterior (W/m²)',
          data: prevData.map(item => parseFloat(item.avg_irradiance || 0)),
          borderColor: '#6B7280',
          backgroundColor: 'rgba(107, 114, 128, 0.5)',
          tension: 0.4,
          fill: false,
        }
      ]
    });
  };

  // Agregar un useEffect que se ejecute cuando el componente se monta o cambie el token
  useEffect(() => {
    if (!authToken) return;
    const controller = new AbortController();
    setLoading(true);
    // Simular un pequeño delay para mostrar la animación
    const timer = setTimeout(() => {
      fetchDashboardData(controller.signal);
    }, 300);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
    // fetchDashboardData se recrea en cada render; incluirla en deps provocaría un bucle de recargas
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authToken]);

  // Opciones genéricas para los gráficos (con soporte para zoom/pan y tooltips mejorados)
  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: true,
        position: 'bottom',
        labels: {
          usePointStyle: true,
          padding: 20,
          font: {
            size: 12,
            weight: '500'
          },
          color: '#374151'
        }
      },
      title: {
        display: false,
      },
      tooltip: {
        enabled: true,
        mode: 'index',
        intersect: false,
        backgroundColor: 'rgba(0, 0, 0, 0.85)',
        titleColor: '#ffffff',
        bodyColor: '#ffffff',
        borderColor: 'rgba(255, 255, 255, 0.1)',
        borderWidth: 1,
        cornerRadius: 12,
        padding: 16,
        displayColors: true,
        callbacks: {
          label: function(context) {
            let label = context.dataset.label || '';
            if (label) {
              label += ': ';
            }
            if (context.parsed.y !== null) {
              label += new Intl.NumberFormat('es-ES', { 
                maximumFractionDigits: 2,
                minimumFractionDigits: 2
              }).format(context.parsed.y);
            }
            return label;
          },
          title: function(context) {
            return `Fecha: ${context[0].label}`;
          }
        }
      },
      zoom: {
        pan: {
          enabled: true,
          mode: 'x',
          modifierKey: 'ctrl',
        },
        zoom: {
          wheel: {
            enabled: true,
            speed: 0.1,
          },
          pinch: {
            enabled: true
          },
          mode: 'x',
          drag: {
            enabled: true,
            backgroundColor: 'rgba(59, 130, 246, 0.1)',
            borderColor: 'rgba(59, 130, 246, 0.3)',
            borderWidth: 1,
          }
        }
      }
    },
    scales: {
      x: {
        type: 'category',
        grid: {
          display: true,
          color: 'rgba(0, 0, 0, 0.03)',
          drawBorder: false,
        },
        ticks: {
          color: '#6B7280',
          font: {
            size: 11,
            weight: '500'
          },
          maxRotation: 45,
          minRotation: 0,
          // Mostrar todas las fechas en el eje X
          callback: function(value, index, values) {
            return value;
          }
        },
        border: {
          display: false
        }
      },
      y: {
        grid: {
          color: 'rgba(0, 0, 0, 0.03)',
          drawBorder: false,
        },
        ticks: {
          color: '#6B7280',
          font: {
            size: 11,
            weight: '500'
          },
          callback: function(value) {
            return new Intl.NumberFormat('es-ES', {
              maximumFractionDigits: 1
            }).format(value);
          }
        },
        border: {
          display: false
        }
      },
    },
    elements: {
      point: {
        hoverRadius: 6,
        radius: 4,
        borderWidth: 2,
      },
      line: {
        borderWidth: 3,
        tension: 0.4,
      },
      bar: {
        borderRadius: 6,
      }
    },
    interaction: {
      mode: 'nearest',
      axis: 'x',
      intersect: false,
    },
    animation: {
      duration: 1000,
      easing: 'easeInOutQuart',
    },
    transitions: {
      zoom: {
        animation: {
          duration: 300,
          easing: 'easeInOutQuart',
        }
      }
    }
  };

  // Si está cargando, muestra un spinner o mensaje
  if (loading) { // Solo verificar loading, no electricityConsumptionData
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-100">
        <div className="flex flex-col items-center">
          <div className="animate-spin rounded-full h-16 w-16 border-t-4 border-b-4 border-blue-500"></div>
          <p className="mt-4 text-lg text-gray-700">Cargando datos del dashboard...</p>
        </div>
      </div>
    );
  }

  // Si hay un error, muestra el mensaje de error
  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-100">
        <div className="text-red-600 text-lg p-4 bg-red-100 rounded-lg shadow-md">
          Error: {error}
        </div>
      </div>
    );
  }

  // Si no hay datos de gráficos pero no está cargando, mostrar mensaje
  if (!electricityConsumptionData) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-100">
        <div className="text-orange-600 text-lg p-4 bg-orange-100 rounded-lg shadow-md">
          No se pudieron cargar los datos de los gráficos. Intente recargar la página.
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header con banner profesional */}
      <header className="bg-gradient-to-r from-blue-600 to-indigo-700 shadow-lg -mx-8 -mt-8">
        <div className="px-8 py-12">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <div className="p-3 bg-white/20 rounded-xl">
                <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"></path>
                </svg>
              </div>
              <div>
                <h1 className="text-4xl font-bold text-white">Dashboard Principal</h1>
                <p className="text-blue-100 mt-1">Visión general y análisis de indicadores del sistema</p>
              </div>
            </div>
            
            {/* Botón de ejecutar tareas con diseño profesional */}
            <div className="flex flex-col items-end space-y-2">
              <button
                onClick={executeAllTasks}
                disabled={taskExecuting}
                className={`
                  group relative inline-flex items-center justify-center px-6 py-3 
                  text-sm font-semibold text-white transition-all duration-300 
                  rounded-xl shadow-lg hover:shadow-xl transform hover:scale-105 
                  disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none
                  ${taskExecuting 
                    ? 'bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600' 
                    : 'bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-600 hover:to-teal-600'
                  }
                  border border-white/20 backdrop-blur-sm
                `}
                title={taskExecuting ? "Ejecutando tareas..." : "Sincronizar datos y calcular KPIs"}
              >
                {/* Icono animado */}
                <div className="flex items-center space-x-3">
                  {taskExecuting ? (
                    <>
                      <div className="animate-spin rounded-full h-5 w-5 border-2 border-white border-t-transparent"></div>
                      <span>Ejecutando...</span>
                    </>
                  ) : (
                    <>
                      <svg className="w-5 h-5 text-white group-hover:scale-110 transition-transform duration-200" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                      </svg>
                      <span>Ejecutar Tareas</span>
                    </>
                  )}
                </div>
                
                {/* Indicador de estado */}
                {taskExecuting && (
                  <div className="absolute -top-2 -right-2">
                    <div className="w-3 h-3 bg-red-400 rounded-full animate-pulse"></div>
                  </div>
                )}
              </button>
              
              {/* Información adicional */}
              <div className="text-right">
                <p className="text-xs text-blue-200 font-medium">
                  {taskExecuting ? "Sincronizando datos..." : "Última ejecución: "}
                  {!taskExecuting && (
                    <span className="text-blue-100">
                      {taskStates.deviceSync?.timestamp 
                        ? new Date(taskStates.deviceSync.timestamp).toLocaleTimeString('es-ES', { 
                            hour: '2-digit', 
                            minute: '2-digit' 
                          })
                        : "Nunca"
                      }
                    </span>
                  )}
                </p>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Banner de estado de conexión SCADA */}
      {scadaConnection.connected === false && (
        <div className="mx-4 mt-4 p-4 bg-amber-50 border border-amber-200 rounded-xl flex items-start gap-3 min-w-0" role="alert">
          <span className="flex-shrink-0 w-10 h-10 rounded-full bg-amber-200 flex items-center justify-center" aria-hidden="true">
            <svg className="w-5 h-5 text-amber-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </span>
          <div className="min-w-0 flex-1">
            <p className="font-semibold text-amber-800">Sin conexión con SCADA</p>
            <p className="text-sm text-amber-700 break-words">{scadaConnection.message}</p>
          </div>
        </div>
      )}

      {/* Mensaje cuando no hay datos de indicadores (conexión OK pero sin carga) */}
      {!loading && hasDashboardData === false && (
        <div className="mx-4 mt-4 p-4 bg-blue-50 border border-blue-200 rounded-xl flex items-start gap-3 min-w-0" role="status">
          <span className="flex-shrink-0 w-10 h-10 rounded-full bg-blue-200 flex items-center justify-center" aria-hidden="true">
            <svg className="w-5 h-5 text-blue-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </span>
          <div className="min-w-0 flex-1">
            <p className="font-semibold text-blue-800">No hay datos de indicadores aún</p>
            <p className="text-sm text-blue-700 break-words">
              Compruebe que la sincronización con SCADA y la carga de datos se hayan ejecutado. Puede usar el botón &quot;Ejecutar Tareas&quot; para sincronizar dispositivos y cargar datos.
            </p>
          </div>
        </div>
      )}

      {/* Sección KPI superpuesta con el banner */}
      <section className="-mt-8 mb-8">
        <div className="bg-white/90 backdrop-blur-sm rounded-2xl shadow-xl border border-white/20 overflow-hidden relative">
          {/* Contenido de KPIs */}
          <div className="p-8">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
              {Object.keys(kpiData).map((key) => {
                const item = kpiData[key];
                
                // Solo mostrar KPIs que no sean taskExecution (se maneja por separado)
                if (key === 'taskExecution') return null;
                
                const description = item.description || (item.change ? item.change : "Datos disponibles");
                
                // Mapear colores del KPI a colores de estilo adaptado
                const colorMap = {
                  'text-blue-600': { bgColor: 'bg-blue-50', borderColor: 'border-blue-200' },
                  'text-green-600': { bgColor: 'bg-green-50', borderColor: 'border-green-200' },
                  'text-purple-600': { bgColor: 'bg-purple-50', borderColor: 'border-purple-200' },
                  'text-indigo-600': { bgColor: 'bg-indigo-50', borderColor: 'border-indigo-200' },
                  'text-orange-600': { bgColor: 'bg-orange-50', borderColor: 'border-orange-200' },
                  'text-red-600': { bgColor: 'bg-red-50', borderColor: 'border-red-200' },
                  'text-cyan-600': { bgColor: 'bg-cyan-50', borderColor: 'border-cyan-200' },
                  'text-teal-600': { bgColor: 'bg-teal-50', borderColor: 'border-teal-200' },
                  'text-amber-600': { bgColor: 'bg-amber-50', borderColor: 'border-amber-200' },
                  'text-gray-600': { bgColor: 'bg-gray-50', borderColor: 'border-gray-200' }
                };
                const styleColors = colorMap[item.color] || { bgColor: 'bg-gray-50', borderColor: 'border-gray-200' };
                
                return (
                  <div 
                    key={key} 
                    className={`${styleColors.bgColor} p-6 rounded-xl shadow-md border ${styleColors.borderColor} transform hover:scale-105 transition-all duration-300 hover:shadow-lg ${item.onClick ? 'cursor-pointer' : ''} relative`}
                    onClick={item.onClick || undefined}
                  >
                    <div className="flex items-center justify-between mb-4">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          if (showKpiInfo === key) {
                            // Cerrar con animación
                            setIsAnimating(true);
                            setTimeout(() => {
                              setShowKpiInfo(null);
                              setIsAnimating(false);
                            }, 500);
                          } else {
                            // Abrir con animación
                            setIsOpening(true);
                            setShowKpiInfo(key);
                          }
                        }}
                        className={`p-2 rounded-lg ${styleColors.bgColor.replace('bg-', 'bg-').replace('-50', '-100')} hover:scale-110 transition-transform duration-200 cursor-pointer`}
                        title="Acerca de este KPI"
                      >
                        {item.icon}
                      </button>
                      <div className="text-right">
                        <p className="text-xs font-medium text-gray-600">{description}</p>
                      </div>
                    </div>
                    <h3 className="text-lg font-semibold text-gray-800 mb-2">{item.title}</h3>
                    <div className="flex items-baseline">
                      <p className={`text-3xl font-bold ${item.color}`}>{item.value}</p>
                      <span className="ml-2 text-lg text-gray-500">{item.unit}</span>
                    </div>
                    <div className="mt-3 pt-3 border-t border-gray-100">
                      {(key === 'totalConsumption' || key === 'totalGeneration' || key === 'averageInstantaneousPower' || key === 'avgDailyTemp' || key === 'relativeHumidity' || key === 'windSpeed' || key === 'irradiance') && item.previousMonthValue ? (
                        <div className="flex items-center justify-between">
                          <div className="flex items-center space-x-2">
                            <span className="text-xs text-gray-500">Mes anterior:</span>
                            <span className={`text-sm font-semibold ${
                              key === 'totalConsumption' ? 'text-blue-600' : 
                              key === 'totalGeneration' ? 'text-green-600' : 
                              key === 'averageInstantaneousPower' ? 'text-orange-600' :
                              key === 'avgDailyTemp' ? 'text-red-600' :
                              key === 'relativeHumidity' ? 'text-cyan-600' :
                              key === 'windSpeed' ? 'text-teal-600' :
                              'text-amber-600'
                            }`}>
                              {key === 'averageInstantaneousPower' 
                                ? `${(item.previousMonthValue / 1000).toFixed(2)} kW` 
                                : key === 'avgDailyTemp'
                                ? `${item.previousMonthValue.toFixed(1)} °C`
                                : key === 'relativeHumidity'
                                ? `${item.previousMonthValue.toFixed(1)} %`
                                : key === 'windSpeed'
                                ? `${item.previousMonthValue.toFixed(1)} km/h`
                                : key === 'irradiance'
                                ? `${item.previousMonthValue.toFixed(1)} W/m²`
                                : `${(item.previousMonthValue / 1000).toFixed(2)} MWh`
                              }
                            </span>
                          </div>
                          {item.change && item.change.includes('%') && (
                            <span className={`text-xs font-semibold px-2 py-1 rounded-full ${
                              item.change.includes('+') 
                                ? 'text-red-600 bg-red-100' 
                                : item.change.includes('-') 
                                ? 'text-green-600 bg-green-100' 
                                : 'text-gray-600 bg-gray-100'
                            }`}>
                              {item.change.match(/[+-]?\d+\.?\d*%/)?.[0] || item.change}
                            </span>
                          )}
                        </div>
                      ) : (
                        <p className="text-xs text-gray-500">{description}</p>
                      )}
                      

                    </div>
                  </div>
                );
              })}
            </div>
            

            
            {/* Overlay de información detallada del KPI - Se superpone en toda la sección */}
            {showKpiInfo && getKpiDetailedInfo(showKpiInfo) && (
              <div 
                className={`absolute inset-0 bg-white/95 backdrop-blur-sm rounded-2xl border-2 border-gray-200 shadow-2xl z-20 p-8 overflow-y-auto transition-all duration-500 ease-out transform ${
                  isAnimating 
                    ? 'opacity-0 scale-95 translate-y-4 backdrop-blur-none' 
                    : isOpening
                    ? 'opacity-0 scale-95 translate-y-4 backdrop-blur-none'
                    : 'opacity-100 scale-100 translate-y-0 backdrop-blur-sm'
                }`}
              >
                <div className={`flex justify-between items-start mb-6 transition-all duration-700 delay-100 ${
                  isAnimating ? 'opacity-0 translate-y-2' : 'opacity-100 translate-y-0'
                }`}>
                  <h3 className="font-bold text-gray-800 text-2xl">
                    {getKpiDetailedInfo(showKpiInfo).title}
                  </h3>
                  <button
                    onClick={() => {
                      setIsAnimating(true);
                      setTimeout(() => {
                        setShowKpiInfo(null);
                        setIsAnimating(false);
                      }, 500);
                    }}
                    className="p-2 rounded-full bg-gray-100 hover:bg-gray-200 transition-colors duration-200"
                    title="Cerrar"
                  >
                    <svg className="w-6 h-6 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
                
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  <div className={`bg-blue-50 p-4 rounded-xl border border-blue-200 transition-all duration-700 delay-200 ${
                    isAnimating ? 'opacity-0 translate-y-4 scale-95' : 'opacity-100 translate-y-0 scale-100'
                  }`}>
                    <span className="text-base font-semibold text-blue-800">Descripción</span>
                    <p className="text-sm text-blue-700 mt-2 leading-relaxed">
                      {getKpiDetailedInfo(showKpiInfo).description}
                    </p>
                  </div>
                  
                  <div className={`bg-green-50 p-4 rounded-xl border border-green-200 transition-all duration-700 delay-300 ${
                    isAnimating ? 'opacity-0 translate-y-4 scale-95' : 'opacity-100 translate-y-0 scale-100'
                  }`}>
                    <span className="text-base font-semibold text-green-800">Cálculo</span>
                    <p className="text-sm text-green-700 mt-2 leading-relaxed">
                      {getKpiDetailedInfo(showKpiInfo).calculation}
                    </p>
                  </div>
                  
                  <div className={`bg-purple-50 p-4 rounded-xl border border-purple-200 transition-all duration-700 delay-400 ${
                    isAnimating ? 'opacity-0 translate-y-4 scale-95' : 'opacity-100 translate-y-0 scale-100'
                  }`}>
                    <span className="text-base font-semibold text-purple-800">Fuente de datos</span>
                    <p className="text-sm text-purple-700 mt-2 leading-relaxed">
                      {getKpiDetailedInfo(showKpiInfo).dataSource}
                    </p>
                  </div>
                  
                  <div className={`bg-orange-50 p-4 rounded-xl border border-orange-200 transition-all duration-700 delay-500 ${
                    isAnimating ? 'opacity-0 translate-y-4 scale-95' : 'opacity-100 translate-y-0 scale-100'
                  }`}>
                    <span className="text-base font-semibold text-orange-800">Unidades</span>
                    <p className="text-sm text-orange-700 mt-2 leading-relaxed">
                      {getKpiDetailedInfo(showKpiInfo).units}
                    </p>
                  </div>
                  
                  <div className={`bg-teal-50 p-4 rounded-xl border border-teal-200 lg:col-span-2 transition-all duration-700 delay-600 ${
                    isAnimating ? 'opacity-0 translate-y-4 scale-95' : 'opacity-100 translate-y-0 scale-100'
                  }`}>
                    <span className="text-base font-semibold text-teal-800">Frecuencia</span>
                    <p className="text-sm text-teal-700 mt-2 leading-relaxed">
                      {getKpiDetailedInfo(showKpiInfo).frequency}
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* Charts Section con diseño mejorado */}
      <section className="mb-8">
        <div className="bg-white/95 backdrop-blur-sm rounded-2xl shadow-xl border border-white/30 overflow-hidden">
          {/* Header de la sección */}
          <div className="bg-gradient-to-r from-blue-600 to-indigo-700 px-8 py-6">
            <div className="flex items-center space-x-4">
              <div className="p-3 bg-white/20 rounded-xl">
                <svg className="w-7 h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
              </div>
              <div>
                <h2 className="text-2xl font-bold text-white">Análisis de Datos</h2>
                <p className="text-blue-100 mt-1">Tendencias y patrones del sistema energético</p>
              </div>
            </div>
          </div>
          
          {/* Contenido de gráficos */}
          <div className="p-8">
            <div className="mb-6">
              <div className="text-sm text-gray-600 bg-blue-50 px-4 py-3 rounded-xl border border-blue-200 inline-flex items-center">
                <svg className="w-4 h-4 mr-2 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span className="font-medium">Hover sobre los gráficos para ver controles de zoom y pan</span>
              </div>
            </div>
            
            <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
              <ChartCard
                title="Consumo de Electricidad"
                description="Análisis del consumo energético diario comparando el mes actual con el anterior"
                type="line"
                data={electricityConsumptionData}
                options={chartOptions}
                height="300px"
                fullscreenHeight="700px"
              />
              <ChartCard
                title="Generación de los Inversores"
                description="Producción de energía solar diaria y comparación mensual de rendimiento"
                type="bar"
                data={inverterGenerationData}
                options={chartOptions}
                height="280px"
                fullscreenHeight="650px"
              />
              <ChartCard
                title="Balance de Energía"
                description="Diferencia entre consumo y generación, mostrando la eficiencia del sistema"
                type="line"
                data={energyBalanceData}
                options={chartOptions}
                height="320px"
                fullscreenHeight="750px"
              />
              <ChartCard
                title="Temperatura Media Diaria"
                description="Seguimiento de las condiciones ambientales y su impacto en el rendimiento"
                type="line"
                data={temperatureTrendsData}
                options={chartOptions}
                height="260px"
                fullscreenHeight="600px"
              />
              <ChartCard
                title="Velocidad del Viento"
                description="Monitoreo de la velocidad del viento y su variación diaria"
                type="line"
                data={windSpeedData}
                options={chartOptions}
                height="280px"
                fullscreenHeight="650px"
              />
              <ChartCard
                title="Irradiancia Solar"
                description="Medición de la intensidad de radiación solar incidente"
                type="line"
                data={irradianceData}
                options={chartOptions}
                height="280px"
                fullscreenHeight="650px"
              />
            </div>
          </div>
        </div>
      </section>
      {/* Overlay de transición */}
      <TransitionOverlay 
        show={showTransition}
        type={transitionType}
        message={transitionMessage}
      />
    </div>
  );
}

export default Dashboard;