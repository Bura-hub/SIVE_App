// Importaciones necesarias de React y componentes personalizados
import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { ChartCard } from "./KPI/ChartCard";
import TransitionOverlay from './TransitionOverlay';
import WeatherStationFilters from './WeatherStationFilters';
import { useDeviceDetail } from '../hooks/useDeviceDetail';
import { ENDPOINTS, buildApiUrl } from '../utils/apiConfig';
import { WEATHER_KPI_INFO } from '../utils/kpiInfo';
import { IconCloudSun, IconRefresh, IconSun, IconWind, IconDroplets } from './icons';

// Importaciones desde Chart.js y el plugin de zoom

// Configuración de gráficos
const CHART_OPTIONS = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      display: true,
      position: 'bottom',
      labels: { usePointStyle: true, padding: 20, font: { size: 12, weight: '500' }, color: '#374151' }
    },
    title: { display: false },
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
        label: (context) => {
          let label = context.dataset.label || '';
          if (label) label += ': ';
          if (context.parsed.y !== null) {
            label += new Intl.NumberFormat('es-ES', { maximumFractionDigits: 2, minimumFractionDigits: 2 }).format(context.parsed.y);
          }
          return label;
        },
        title: (context) => `Fecha: ${context[0].label}`
      }
    },
    zoom: {
      pan: { enabled: true, mode: 'x', modifierKey: 'ctrl' },
      zoom: {
        wheel: { enabled: true, speed: 0.1 },
        pinch: { enabled: true },
        mode: 'x',
        drag: { enabled: true, backgroundColor: 'rgba(59, 130, 246, 0.1)', borderColor: 'rgba(59, 130, 246, 0.3)', borderWidth: 1 }
      }
    }
  },
  scales: {
    x: {
      type: 'category',
      grid: { display: true, color: 'rgba(0, 0, 0, 0.03)', drawBorder: false },
      ticks: { color: '#6B7280', font: { size: 11, weight: '500' }, maxRotation: 45, minRotation: 0 },
      border: { display: false }
    },
    y: {
      grid: { color: 'rgba(0, 0, 0, 0.03)', drawBorder: false },
      ticks: {
        color: '#6B7280',
        font: { size: 11, weight: '500' },
        callback: (value) => new Intl.NumberFormat('es-ES', { maximumFractionDigits: 1 }).format(value)
      },
      border: { display: false }
    }
  },
  elements: {
    point: { hoverRadius: 6, radius: 4, borderWidth: 2 },
    line: { borderWidth: 3, tension: 0.4 },
    bar: { borderRadius: 6 }
  },
  interaction: { mode: 'nearest', axis: 'x', intersect: false },
  animation: { duration: 1000, easing: 'easeInOutQuart' },
  transitions: { zoom: { animation: { duration: 300, easing: 'easeInOutQuart' } } }
};

// Componente de encabezado de sección
const SectionHeader = ({ title, icon, infoText }) => (
  <div className="flex items-center justify-between mb-6">
    <h2 className="text-2xl font-bold text-gray-800 flex items-center">
      <svg className="w-6 h-6 mr-3 text-gray-700" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d={icon} />
      </svg>
      {title}
    </h2>
    <div className="text-sm text-gray-600 bg-gray-50 px-4 py-2 rounded-full border border-gray-200">
      <span className="flex items-center">
        <svg className="w-4 h-4 mr-2 text-gray-600" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        {infoText}
      </span>
    </div>
  </div>
);

// Función para calcular potencia fotovoltaica teórica (pura, fuera del componente
// para poder usarla en hooks sin añadir dependencias inestables)
const calculateTheoreticalPVPower = (irradiance, temperature = 25) => {
  // Verificar que irradiance sea un número válido
  if (!irradiance || isNaN(irradiance) || irradiance < 0) {
              return 0;
  }

  // Verificar que temperature sea un número válido
  if (!temperature || isNaN(temperature)) {
    temperature = 25; // Usar temperatura estándar si no es válida
  }

  // Parámetros de referencia, unificados con el backend (theoretical_pv_power_w):
  // eficiencia 17% sobre 1 m² de referencia. Ver AUDITORIA_SIVE/PLAN_KPIS.md.
  const panelEfficiency = 0.17; // 17% (igual que el backend)
  const panelArea = 1.0; // 1 m² de referencia (igual que el backend)
  const temperatureCoefficient = -0.004; // -0.4% por °C
  const standardTemperature = 25; // Temperatura estándar de prueba

  // Calcular potencia teórica
  let power = irradiance * panelArea * panelEfficiency;

  // Ajustar por temperatura si está disponible
  if (temperature !== 25) {
    const tempAdjustment = 1 + (temperatureCoefficient * (temperature - standardTemperature));
    power *= tempAdjustment;
  }

  return Math.max(0, power); // No puede ser negativa
};

// Función para obtener la dirección predominante del viento (pura)
const getPredominantWindDirection = (data) => {
  if (!data || !Array.isArray(data) || data.length === 0) {
    return "N/A";
  }

  // El backend expone wind_direction_distribution: { N: n, NE: n, ... } por registro.
  // Sumamos la distribución sobre el rango y devolvemos el sector con mayor conteo.
  const totals = {};
  data.forEach(item => {
    const dist = item?.wind_direction_distribution;
    if (dist && typeof dist === 'object') {
      Object.entries(dist).forEach(([dir, count]) => {
        totals[dir] = (totals[dir] || 0) + (Number(count) || 0);
      });
    }
  });

  const ranked = Object.entries(totals).filter(([, c]) => c > 0).sort((a, b) => b[1] - a[1]);
  return ranked.length > 0 ? ranked[0][0] : "N/A";
};

// Definición única de los KPIs meteorológicos base (iconos del módulo común;
// windDirection y pvPower no tienen equivalente en el módulo y se definen aquí).
const WEATHER_KPI_BASE = {
  irradiance: {
    title: "Irradiancia Acumulada",
    value: "0.00",
    unit: "kWh/m²",
    change: "Este período",
    status: "normal",
    icon: <IconSun size={24} />,
    color: "text-orange-700"
  },
  temperature: {
    title: "Temperatura Ambiente",
    value: "0.0",
    unit: "°C",
    change: "Promedio del período",
    status: "normal",
    icon: <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 14.76V3.5a2.5 2.5 0 0 0-5 0v11.26a4.5 4.5 0 1 0 5 0z"></path></svg>,
    color: "text-red-700"
  },
  windSpeed: {
    title: "Velocidad del Viento",
    value: "0.0",
    unit: "km/h",
    change: "Promedio del período",
    status: "normal",
    icon: <IconWind size={24} />,
    color: "text-blue-700"
  },
  windDirection: {
    title: "Dirección del Viento",
    value: "N/A",
    unit: "",
    change: "Predominante",
    status: "normal",
    icon: <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>,
    color: "text-indigo-700"
  },
  precipitation: {
    title: "Precipitación Acumulada",
    value: "0.00",
    unit: "cm/día",
    change: "Acumulado del período",
    status: "normal",
    icon: <IconDroplets size={24} />,
    color: "text-cyan-700"
  },
  pvPower: {
    title: "Potencia Fotovoltaica",
    value: "0.0",
    unit: "W",
    change: "Basada en irradiancia",
    status: "normal",
    icon: <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="5" width="18" height="14" rx="2" ry="2"></rect><path d="M7 12h2l1 2 2-4 1 2h2"></path><path d="M17 16h.01"></path><path d="M17 8h.01"></path></svg>,
    color: "text-purple-700"
  }
};

// Componente principal
function WeatherStationDetails({ authToken, onLogout, username, isSuperuser, navigateTo, isSidebarMinimized, setIsSidebarMinimized }) {
  // Estados consolidados
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showTransition, setShowTransition] = useState(false);
  const [transitionType, setTransitionType] = useState('info');
  const [transitionMessage, setTransitionMessage] = useState('');
  
  // Filtros, datos y fetch: en useDeviceDetail (el hook se inicializa más abajo).

  // Estados de paginación
  const [currentPage, setCurrentPage] = useState(1);
  const [recordsPerPage, setRecordsPerPage] = useState(20);

  // Al montar, limpiar los KPIs (data/loading/error ya los inicia el hook).
  useEffect(() => {
    setKpiData({});
  }, []);

  // KPIs dinámicos basados en datos reales (definición base única)
  const [kpiData, setKpiData] = useState(WEATHER_KPI_BASE);

  // Funciones optimizadas
  const showTransitionAnimation = (type = 'info', message = '', duration = 2000) => {
    setTransitionType(type);
    setTransitionMessage(message);
    setShowTransition(true);
    setTimeout(() => setShowTransition(false), duration);
  };

  // Filtros + datos + fetch (race-guard, dedup, debounce 300ms, blank durante carga)
  // y cálculo: en useDeviceDetail.
  const {
    data: weatherData,
    loading: weatherLoading,
    error: weatherError,
    filters,
    handleFiltersChange: handleFilterChange,
    calculate: calculateWeatherData,
    fetchData: fetchWeatherData,
  } = useDeviceDetail({
    indicatorsEndpoint: ENDPOINTS.weather.indicators,
    calculateEndpoint: ENDPOINTS.weather.calculate,
    authToken,
    onNotify: showTransitionAnimation,
    debounceMs: 300,
    clearOnFetch: true,
  });

  const processKPIData = useCallback((latestData) => {
    console.log('🔍 processKPIData iniciado con:', latestData);
    // Verificar que latestData existe y es válido
    if (!latestData || typeof latestData !== 'object') {
      console.warn('processKPIData: latestData no es válido:', latestData);
      return;
    }
    
    // Iconos y colores base de los KPIs (definición única a nivel de módulo)
    const initialKpiData = WEATHER_KPI_BASE;
    
    const kpis = {
      irradiance: {
        title: "Irradiancia Acumulada",
        value: (latestData.daily_irradiance_kwh_m2 || 0).toFixed(2),
        unit: "kWh/m²",
        change: latestData.daily_hsp_hours ? `≈ ${latestData.daily_hsp_hours.toFixed(1)} HSP` : "N/A",
        status: "normal",
        icon: initialKpiData.irradiance.icon,
        color: initialKpiData.irradiance.color
      },
      temperature: {
        title: "Temperatura Ambiente",
        value: (latestData.avg_temperature_c ?? null) !== null ? latestData.avg_temperature_c.toFixed(1) : "N/A",
        unit: "°C",
        change: "Promedio del período",
        status: "normal",
        icon: initialKpiData.temperature.icon,
        color: initialKpiData.temperature.color
      },
      windSpeed: {
        title: "Velocidad del Viento",
        value: (latestData.avg_wind_speed_kmh || 0).toFixed(1),
        unit: "km/h",
        change: "Promedio del período",
        status: "normal",
        icon: initialKpiData.windSpeed.icon,
        color: initialKpiData.windSpeed.color
      },
      windDirection: {
        title: "Dirección Predominante",
        value: getPredominantWindDirection(weatherData?.results || []),
        unit: "",
        change: "Viento más frecuente",
        status: "normal",
        icon: initialKpiData.windDirection.icon,
        color: initialKpiData.windDirection.color
      },
      precipitation: {
        title: "Precipitación Acumulada",
        value: (latestData.daily_precipitation_cm || 0).toFixed(2),
        unit: "cm/día",
        change: "Acumulado del período",
        status: "normal",
        icon: initialKpiData.precipitation.icon,
        color: initialKpiData.precipitation.color
      },
      pvPower: {
        title: "Potencia Fotovoltaica",
        value: (latestData.theoretical_pv_power_w || calculateTheoreticalPVPower(
          latestData.daily_irradiance_kwh_m2 || 0,
          latestData.avg_temperature_c || 25
        )).toFixed(1),
        unit: "W",
        change: "Basada en irradiancia y temperatura",
        status: "normal",
        icon: initialKpiData.pvPower.icon,
        color: initialKpiData.pvPower.color
      }
    };

    // Actualizar el estado de kpiData con los nuevos valores
    console.log('🔍 Actualizando kpiData con:', kpis);
    setKpiData(kpis);
  }, [weatherData]);

  // Función para calcular datos de la rosa de los vientos
  const calculateWindRoseData = (data, minSpeed, maxSpeed) => {
    // Verificar que data existe y tiene resultados
    if (!data || !Array.isArray(data) || data.length === 0) {
      return [0, 0, 0, 0, 0, 0, 0, 0]; // Retornar array vacío si no hay datos
    }
    
    const directionNames = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];

    // Contadores por dirección (una entrada por sector cardinal)
    const directionCounts = directionNames.map(() => 0);

    // El backend entrega, por día, wind_direction_distribution: { N, NE, E, ... } con los
    // conteos reales de las lecturas sub-horarias. No hay dirección×velocidad por lectura,
    // así que asignamos la distribución del día a la banda de su velocidad MEDIA (avg_wind_speed_kmh).
    data.forEach(item => {
      if (!item) return;

      const windSpeed = item.avg_wind_speed_kmh || 0;
      if (windSpeed < minSpeed || windSpeed >= maxSpeed) return;

      const dist = item.wind_direction_distribution;
      if (dist && typeof dist === 'object') {
        directionNames.forEach((name, index) => {
          directionCounts[index] += Number(dist[name]) || 0;
        });
      }
    });

    // Conteos CRUDOS por dirección (sin normalizar) para poder apilar las bandas de
    // velocidad en la rosa polar. Sin datos -> ceros (no se dibuja el círculo uniforme falso).
    return directionCounts;
  };

  // Funciones de paginación
  const getCurrentPageData = () => {
    if (!weatherData?.results || !Array.isArray(weatherData.results)) {
      return [];
    }
    
    const startIndex = (currentPage - 1) * recordsPerPage;
    const endIndex = startIndex + recordsPerPage;
    return weatherData.results.slice(startIndex, endIndex);
  };

  const getTotalPages = () => {
    if (!weatherData?.results || !Array.isArray(weatherData.results)) {
      return 0;
    }
    return Math.ceil(weatherData.results.length / recordsPerPage);
  };

  const handlePageChange = (newPage) => {
    setCurrentPage(newPage);
    // Scroll hacia arriba de la tabla
    window.scrollTo({
      top: document.querySelector('.bg-white\\/95')?.offsetTop - 100 || 0,
      behavior: 'smooth'
    });
  };

  const resetPagination = () => {
    setCurrentPage(1);
  };

  const handleRecordsPerPageChange = (newRecordsPerPage) => {
    setRecordsPerPage(newRecordsPerPage);
    setCurrentPage(1); // Resetear a la primera página
  };

  // Efectos
  useEffect(() => {
    if (authToken) {
      setLoading(true);
      setTimeout(() => {
        setLoading(false);
      }, 300);
    }
  }, [authToken]);

  // Efecto para carga inicial de datos cuando se selecciona una institución
  useEffect(() => {
    // Solo cargar datos si hay institución seleccionada y no hay datos ya cargados
    if (filters.institutionId && authToken && !weatherData) {
      fetchWeatherData(filters);
    }
    // Se omiten `filters` y `weatherData` de las deps a propósito: incluirlos provocaría
    // cargas duplicadas (handleFilterChange ya gestiona esos cambios con debounce)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters.institutionId, authToken, fetchWeatherData]); // Solo depender de institutionId y authToken

  // Efecto para resetear paginación cuando cambien los filtros
  useEffect(() => {
    resetPagination();
  }, [filters.institutionId, filters.deviceId, filters.startDate, filters.endDate]);

  // Efecto para actualizar KPIs cuando cambien los datos meteorológicos
  useEffect(() => {
    console.log('🔍 useEffect weatherData cambió:', weatherData);
    if (weatherData && weatherData.results && weatherData.results.length > 0) {
      const latestData = weatherData.results[0];
      console.log('🔍 Procesando KPIs con datos:', latestData);
      processKPIData(latestData);
    } else {
      console.log('🔍 No hay datos meteorológicos para procesar KPIs');
    }
  }, [weatherData, processKPIData]);

  // Función para obtener información detallada de cada KPI
  // Info-al-click de cada tarjeta (centralizada en utils/kpiInfo.js).
  const getKpiDetailedInfo = (kpiKey) => WEATHER_KPI_INFO[kpiKey] || null;

  // Estados para mostrar información detallada de KPIs
  const [showKpiInfo, setShowKpiInfo] = useState(null);
  // A11y: cerrar el overlay de info del KPI con la tecla Escape.
  useEffect(() => {
    if (!showKpiInfo) return undefined;
    const onKey = (e) => { if (e.key === 'Escape') setShowKpiInfo(null); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [showKpiInfo]);

  const [isAnimating, setIsAnimating] = useState(false);
  const [isOpening, setIsOpening] = useState(false);

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

  // Filas en orden cronológico ascendente, calculadas una sola vez por cambio de datos.
  const weatherRows = useMemo(
    () => (weatherData?.results ? weatherData.results.slice().reverse() : []),
    [weatherData]
  );

  // Objetos `data` memoizados: evitan recalcular labels/datasets (y por tanto la animación
  // de chart.update()) en cada render (p.ej. al paginar la tabla o abrir un modal de KPI).
  const irradianceChartData = useMemo(() => ({
    labels: weatherRows.map(item => {
      // 🔍 CORREGIR PROCESAMIENTO DE FECHAS PARA EVITAR DESFASE
      const rawDate = item.date;
      // Crear fecha en zona horaria local para evitar desfase UTC
      const localDate = new Date(rawDate + 'T00:00:00');
      const formattedDate = localDate.toLocaleDateString('es-ES');

      return formattedDate;
    }),
    datasets: [
      {
        label: 'Irradiancia Acumulada (kWh/m²)',
        data: weatherRows.map(item => item.daily_irradiance_kwh_m2 || 0),
        borderColor: '#F59E0B',
        backgroundColor: 'rgba(245, 158, 11, 0.1)',
        fill: true,
        tension: 0.4,
        pointRadius: 4,
        pointBackgroundColor: '#F59E0B',
        pointBorderColor: '#ffffff',
        pointBorderWidth: 2,
      },
      {
        label: 'Horas Solares Pico (HSP)',
        data: weatherRows.map(item => item.daily_hsp_hours || 0),
        borderColor: '#10B981',
        backgroundColor: 'rgba(16, 185, 129, 0.1)',
        fill: false,
        tension: 0.4,
        pointRadius: 4,
        borderDash: [8, 4],
        pointBackgroundColor: '#10B981',
        pointBorderColor: '#ffffff',
        pointBorderWidth: 2,
      }
    ],
  }), [weatherRows]);

  const ambientConditionsChartData = useMemo(() => ({
    labels: weatherRows.map(item => {
      // 🔍 CORREGIR PROCESAMIENTO DE FECHAS PARA EVITAR DESFASE
      const rawDate = item.date;
      // Crear fecha en zona horaria local para evitar desfase UTC
      const localDate = new Date(rawDate + 'T00:00:00');
      const formattedDate = localDate.toLocaleDateString('es-ES');

      return formattedDate;
    }),
    datasets: [
      {
        label: 'Temperatura Promedio (°C)',
        data: weatherRows.map(item => item.avg_temperature_c || 0),
        borderColor: '#EF4444',
        backgroundColor: 'rgba(239, 68, 68, 0.1)',
        fill: true,
        tension: 0.4,
        pointRadius: 3,
        pointBackgroundColor: '#EF4444',
      },
      {
        label: 'Humedad Relativa (%)',
        data: weatherRows.map(item => item.avg_humidity_pct || 0),
        borderColor: '#3B82F6',
        backgroundColor: 'rgba(59, 130, 246, 0.1)',
        fill: true,
        tension: 0.4,
        pointRadius: 3,
        pointBackgroundColor: '#3B82F6',
      }
    ]
  }), [weatherRows]);

  const windConditionsChartData = useMemo(() => ({
    labels: weatherRows.map(item => {
      // 🔍 CORREGIR PROCESAMIENTO DE FECHAS PARA EVITAR DESFASE
      const rawDate = item.date;
      // Crear fecha en zona horaria local para evitar desfase UTC
      const localDate = new Date(rawDate + 'T00:00:00');
      const formattedDate = localDate.toLocaleDateString('es-ES');

      return formattedDate;
    }),
    datasets: [
      {
        label: 'Velocidad del Viento (km/h)',
        data: weatherRows.map(item => item.avg_wind_speed_kmh || 0),
        borderColor: '#10B981',
        backgroundColor: 'rgba(16, 185, 129, 0.1)',
        fill: true,
        tension: 0.4,
        pointRadius: 3,
        pointBackgroundColor: '#10B981',
      },
      {
        label: 'Precipitación Acumulada (cm/día)',
        data: weatherRows.map(item => item.daily_precipitation_cm || 0),
        borderColor: '#8B5CF6',
        backgroundColor: 'rgba(139, 92, 246, 0.1)',
        fill: false,
        tension: 0.4,
        pointRadius: 3,
        borderDash: [6, 3],
        pointBackgroundColor: '#8B5CF6',
      }
    ]
  }), [weatherRows]);

  // Rosa de los vientos: agrupa el bundle labels/slow/mid/fast/total/fills que alimenta
  // tanto el `data` (memoizado) como los callbacks del tooltip en `options` (sin tocar
  // su contenido, solo se referencia esta misma fuente ya calculada).
  const windRoseBundle = useMemo(() => {
    const labels = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
    const slow = calculateWindRoseData(weatherRows, 0, 5);
    const mid = calculateWindRoseData(weatherRows, 5, 10);
    const fast = calculateWindRoseData(weatherRows, 10, Infinity);
    const total = labels.map((_, i) => (slow[i] || 0) + (mid[i] || 0) + (fast[i] || 0));
    // Rueda de color tipo brújula (un color por sector), con relleno translúcido.
    const DIR_COLORS = ['#2563eb', '#0891b2', '#059669', '#65a30d', '#d97706', '#ea580c', '#dc2626', '#7c3aed'];
    const fills = DIR_COLORS.map(c => c + 'cc'); // ~80% opacidad
    const chartData = {
      labels,
      datasets: [
        {
          label: 'Lecturas de viento',
          data: total,
          backgroundColor: fills,
          borderColor: '#ffffff',
          borderWidth: 1.5,
        },
      ],
    };
    return { labels, slow, mid, fast, total, chartData };
  }, [weatherRows]);

  const pvTheoreticalPowerChartData = useMemo(() => ({
    labels: weatherRows.map(item => {
      // 🔍 CORREGIR PROCESAMIENTO DE FECHAS PARA EVITAR DESFASE
      const rawDate = item.date;
      // Crear fecha en zona horaria local para evitar desfase UTC
      const localDate = new Date(rawDate + 'T00:00:00');
      const formattedDate = localDate.toLocaleDateString('es-ES');

      return formattedDate;
    }),
    datasets: [
      {
        label: 'Potencia Teórica (W)',
        data: weatherRows.map(item =>
          calculateTheoreticalPVPower(
            item?.daily_irradiance_kwh_m2 || 0,
            item?.avg_temperature_c || 25
          )
        ),
        borderColor: '#8B5CF6',
        backgroundColor: 'rgba(139, 92, 246, 0.1)',
        fill: true,
        tension: 0.4,
        pointRadius: 4,
        pointBackgroundColor: '#8B5CF6',
        pointBorderColor: '#ffffff',
        pointBorderWidth: 2,
      },
      {
        label: 'Irradiancia (kWh/m²)',
        data: weatherRows.map(item => item?.daily_irradiance_kwh_m2 || 0),
        borderColor: '#F59E0B',
        backgroundColor: 'rgba(245, 158, 11, 0.05)',
        fill: false,
        tension: 0.4,
        pointRadius: 3,
        borderDash: [6, 3],
        pointBackgroundColor: '#F59E0B',
        pointBorderColor: '#ffffff',
        pointBorderWidth: 1,
        yAxisID: 'y1'
      }
    ],
  }), [weatherRows]);

  // Si está cargando, muestra un spinner o mensaje
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-100">
        <div className="flex flex-col items-center">
          <div className="animate-spin rounded-full h-16 w-16 border-t-4 border-b-4 border-orange-500"></div>
          <p className="mt-4 text-lg text-gray-700">Cargando estaciones meteorológicas...</p>
        </div>
      </div>
    );
  }

  // Si hay un error, muestra el mensaje de error
  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-100">
        <div className="text-red-700 text-lg p-4 bg-red-100 rounded-lg shadow-md">
          Error: {error}
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <header className="bg-gradient-to-r from-orange-700 to-amber-800 shadow-lg -mx-4 lg:-mx-8 -mt-4 lg:-mt-8">
        <div className="px-4 lg:px-8 py-8 lg:py-12">
          <div className="flex flex-col lg:flex-row lg:items-center space-y-4 lg:space-y-0 lg:space-x-4">
            <div className="p-3 bg-white/20 rounded-xl self-start lg:self-auto">
              <IconCloudSun className="w-6 h-6 lg:w-8 lg:h-8 text-white" />
            </div>
            <div>
              <h1 className="text-2xl lg:text-4xl font-bold text-white">Estaciones Meteorológicas</h1>
              <p className="text-orange-50 mt-1 text-sm lg:text-base">Análisis y monitoreo de indicadores meteorológicos</p>
            </div>
          </div>
        </div>
      </header>

      {/* KPIs */}
      <section className="bg-white/90 backdrop-blur-sm rounded-2xl shadow-xl border border-white/20 p-4 lg:p-8 -mt-4 lg:-mt-8 mb-6 lg:mb-8">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-4 lg:gap-6">
          {!filters.institutionId ? (
            // Estado de carga cuando no hay institución seleccionada
            Array.from({ length: 6 }).map((_, index) => (
              <div key={index} className="bg-white rounded-xl shadow-lg border border-gray-100 p-6 overflow-hidden relative">
                {/* Skeleton loader con animación */}
                <div className="animate-pulse">
                  {/* Icono skeleton */}
                  <div className="flex items-center justify-between mb-4">
                    <div className="w-12 h-12 bg-gray-200 rounded-lg"></div>
                    <div className="w-20 h-4 bg-gray-200 rounded"></div>
                  </div>
                  
                  {/* Título skeleton */}
                  <div className="w-32 h-5 bg-gray-200 rounded mb-2"></div>
                  
                  {/* Valor skeleton */}
                  <div className="flex items-baseline">
                    <div className="w-24 h-8 bg-gray-200 rounded"></div>
                    <div className="w-16 h-6 bg-gray-200 rounded ml-2"></div>
                  </div>
                  
                  {/* Línea inferior skeleton */}
                  <div className="mt-3 pt-3 border-t border-gray-100">
                    <div className="w-28 h-3 bg-gray-200 rounded"></div>
                  </div>
                </div>
                
                {/* Overlay de shimmer */}
                <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent animate-shimmer pointer-events-none"></div>
              </div>
            ))
          ) : weatherLoading ? (
            // Estado de carga cuando se están cargando los datos
            Array.from({ length: 6 }).map((_, index) => (
              <div key={index} className="bg-white rounded-xl shadow-lg border border-orange-200 p-6 overflow-hidden relative">
                {/* Skeleton loader con animación naranja */}
                <div className="animate-pulse">
                  {/* Icono skeleton */}
                  <div className="flex items-center justify-between mb-4">
                    <div className="w-12 h-12 bg-orange-200 rounded-lg"></div>
                    <div className="w-20 h-4 bg-orange-200 rounded"></div>
                  </div>
                  
                  {/* Título skeleton */}
                  <div className="w-32 h-5 bg-orange-200 rounded mb-2"></div>
                  
                  {/* Valor skeleton */}
                  <div className="flex items-baseline">
                    <div className="w-24 h-8 bg-orange-200 rounded"></div>
                    <div className="w-16 h-6 bg-orange-200 rounded ml-2"></div>
                  </div>
                  
                  {/* Línea inferior skeleton */}
                  <div className="mt-3 pt-3 border-t border-orange-100">
                    <div className="w-28 h-3 bg-orange-200 rounded"></div>
                  </div>
                </div>
                
                {/* Overlay de shimmer naranja */}
                <div className="absolute inset-0 bg-gradient-to-r from-transparent via-orange-100/30 to-transparent animate-shimmer pointer-events-none"></div>
              </div>
            ))
          ) : (
            // KPIs reales cuando hay datos
            (() => {
              console.log('🔍 Renderizando KPIs, kpiData:', kpiData);
              console.log('🔍 Claves de kpiData:', Object.keys(kpiData));
              return Object.keys(kpiData).map((key) => {
                const item = kpiData[key];
                // Mapear colores del KPI a colores de estilo adaptado
                const colorMap = {
                  'text-orange-700': { bgColor: 'bg-orange-50', borderColor: 'border-orange-200' },
                  'text-yellow-700': { bgColor: 'bg-yellow-50', borderColor: 'border-yellow-200' },
                  'text-blue-700': { bgColor: 'bg-blue-50', borderColor: 'border-blue-200' },
                  'text-indigo-700': { bgColor: 'bg-indigo-50', borderColor: 'border-indigo-200' },
                  'text-cyan-700': { bgColor: 'bg-cyan-50', borderColor: 'border-cyan-200' },
                  'text-purple-700': { bgColor: 'bg-purple-50', borderColor: 'border-purple-200' }
                };
                const styleColors = colorMap[item.color] || { bgColor: 'bg-gray-50', borderColor: 'border-gray-200' };
                
                return (
                  <div key={key} className={`${styleColors.bgColor} p-6 rounded-xl shadow-md border ${styleColors.borderColor} transform hover:scale-105 transition duration-300 hover:shadow-lg relative`}>
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
                        className={`p-2 rounded-lg ${styleColors.bgColor.replace('bg-', 'bg-').replace('-50', '-100')} hover:scale-110 transition-transform duration-150 cursor-pointer`}
                        title="Acerca de este KPI"
                      >
                        {item.icon}
                      </button>
                      <div className="text-right">
                        <p className="text-xs font-medium text-gray-600">{item.change}</p>
                      </div>
                    </div>
                    <h3 className="text-lg font-semibold text-gray-800 mb-2">{item.title}</h3>
                    <div className="flex items-baseline">
                      <p className={`text-3xl font-bold ${item.color}`}>{item.value}</p>
                      <span className="ml-2 text-lg text-gray-600">{item.unit}</span>
                    </div>
                    <div className="mt-3 pt-3 border-t border-gray-100">
                      <p className="text-xs text-gray-600">{item.change}</p>
                    </div>
                  </div>
                );
              });
            })()
          )}
        </div>
        
        {/* Mensaje de estado */}
        {!filters.institutionId && (
          <div className="text-center mt-4 lg:mt-6">
            <div className="inline-flex items-center px-3 lg:px-4 py-2 bg-orange-50 border border-orange-200 rounded-full text-sm lg:text-base">
              <svg className="w-4 h-4 lg:w-5 lg:h-5 text-orange-500 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className="text-orange-700 font-medium">Selecciona una institución para ver los indicadores</span>
            </div>
          </div>
        )}
        
        {filters.institutionId && weatherLoading && (
          <div className="text-center mt-4 lg:mt-6">
            <div className="inline-flex items-center px-3 lg:px-4 py-2 bg-orange-50 border border-orange-200 rounded-full text-sm lg:text-base">
              <svg className="w-4 h-4 lg:w-5 lg:h-5 text-orange-500 mr-2 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              <span className="text-orange-700 font-medium">Cargando indicadores de la institución...</span>
            </div>
          </div>
        )}
        
        {filters.institutionId && !weatherLoading && weatherData && (!weatherData.results || weatherData.results.length === 0) && (
          <div className="text-center mt-4 lg:mt-6">
            <div className="inline-flex items-center px-3 lg:px-4 py-2 bg-yellow-50 border border-yellow-200 rounded-full text-sm lg:text-base">
              <svg className="w-4 h-4 lg:w-5 lg:h-5 text-yellow-500 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
              </svg>
              <span className="text-yellow-700 font-medium">No hay datos disponibles para esta institución en el período seleccionado</span>
            </div>
            <div className="mt-4">
              <button
                onClick={calculateWeatherData}
                disabled={weatherLoading}
                className="inline-flex items-center px-4 py-2 bg-gradient-to-r from-orange-600 to-amber-600 hover:from-orange-700 hover:to-amber-700 text-white font-medium rounded-lg shadow-lg hover:shadow-xl transition duration-150 transform hover:scale-105 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <IconRefresh className="w-4 h-4 mr-2" />
                Calcular Datos Meteorológicos
              </button>
            </div>
          </div>
        )}
        
        {/* Overlay de información detallada del KPI - Se superpone en toda la sección */}
        {showKpiInfo && getKpiDetailedInfo(showKpiInfo) && (
          <div 
            role="dialog" aria-modal="true" aria-label="Información del indicador" className={`absolute inset-0 bg-white/95 backdrop-blur-sm rounded-2xl border-2 border-gray-200 shadow-2xl z-20 p-8 overflow-y-auto transition duration-300 ease-out transform ${
              isAnimating 
                ? 'opacity-0 scale-95 translate-y-4 backdrop-blur-none' 
                : isOpening
                ? 'opacity-0 scale-95 translate-y-4 backdrop-blur-none'
                : 'opacity-100 scale-100 translate-y-0 backdrop-blur-sm'
            }`}
          >
            <div className={`flex justify-between items-start mb-6 transition duration-300 delay-100 ${
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
                className="p-2 rounded-full bg-gray-100 hover:bg-gray-200 transition-colors duration-150"
                title="Cerrar"
              >
                <svg className="w-6 h-6 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className={`bg-blue-50 p-4 rounded-xl border border-blue-200 transition duration-300 delay-200 ${
                isAnimating ? 'opacity-0 translate-y-4 scale-95' : 'opacity-100 translate-y-0 scale-100'
              }`}>
                <span className="text-base font-semibold text-blue-800">Descripción</span>
                <p className="text-sm text-blue-700 mt-2 leading-relaxed">
                  {getKpiDetailedInfo(showKpiInfo).description}
                </p>
              </div>
              
              <div className={`bg-green-50 p-4 rounded-xl border border-green-200 transition duration-300 delay-300 ${
                isAnimating ? 'opacity-0 translate-y-4 scale-95' : 'opacity-100 translate-y-0 scale-100'
              }`}>
                <span className="text-base font-semibold text-green-800">Cálculo</span>
                <p className="text-sm text-green-700 mt-2 leading-relaxed">
                  {getKpiDetailedInfo(showKpiInfo).calculation}
                </p>
              </div>
              
              <div className={`bg-purple-50 p-4 rounded-xl border border-purple-200 transition duration-300 delay-400 ${
                isAnimating ? 'opacity-0 translate-y-4 scale-95' : 'opacity-100 translate-y-0 scale-100'
              }`}>
                <span className="text-base font-semibold text-purple-800">Fuente de datos</span>
                <p className="text-sm text-purple-700 mt-2 leading-relaxed">
                  {getKpiDetailedInfo(showKpiInfo).dataSource}
                </p>
              </div>
              
              <div className={`bg-orange-50 p-4 rounded-xl border border-orange-200 transition duration-300 delay-500 ${
                isAnimating ? 'opacity-0 translate-y-4 scale-95' : 'opacity-100 translate-y-0 scale-100'
              }`}>
                <span className="text-base font-semibold text-orange-800">Unidades</span>
                <p className="text-sm text-orange-700 mt-2 leading-relaxed">
                  {getKpiDetailedInfo(showKpiInfo).units}
                </p>
              </div>
              
              <div className={`bg-teal-50 p-4 rounded-xl border border-teal-200 lg:col-span-2 transition duration-300 delay-600 ${
                isAnimating ? 'opacity-0 translate-y-4 scale-95' : 'opacity-100 translate-y-0 scale-100'
              }`}>
                <span className="text-base font-semibold text-teal-800">Frecuencia</span>
                <p className="text-sm text-teal-700 mt-2 leading-relaxed">
                  {getKpiDetailedInfo(showKpiInfo).frequency}
                </p>
              </div>

              <div className={`bg-amber-50 p-4 rounded-xl border border-amber-200 lg:col-span-2 transition duration-300 delay-700 ${
                isAnimating ? 'opacity-0 translate-y-4 scale-95' : 'opacity-100 translate-y-0 scale-100'
              }`}>
                <span className="text-base font-semibold text-amber-800">Interpretación / Umbral</span>
                <p className="text-sm text-amber-700 mt-2 leading-relaxed">
                  {getKpiDetailedInfo(showKpiInfo).interpretation}
                </p>
              </div>
            </div>
          </div>
        )}
      </section>

      {/* Sección de Indicadores de Estaciones Meteorológicas */}
      <section className="mb-6 lg:mb-8">
        <div className="bg-white/95 backdrop-blur-sm rounded-2xl shadow-xl border border-white/30 overflow-hidden">
          {/* Header de la sección */}
          <div className="bg-gradient-to-r from-orange-700 to-amber-800 px-4 lg:px-8 py-4 lg:py-6">
            <div className="flex flex-col lg:flex-row lg:items-center space-y-3 lg:space-y-0 lg:space-x-4">
              <div className="p-2 lg:p-3 bg-white/20 rounded-xl self-start lg:self-auto">
                <svg className="w-6 h-6 lg:w-7 lg:h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <circle cx="12" cy="6" r="2"></circle>
                  <path d="M12 8v4"></path>
                  <path d="M6 20h12"></path>
                  <path d="M12 12l4 8"></path>
                  <path d="M12 12l-4 8"></path>
                  <path d="M4 10a8 8 0 0116 0"></path>
                </svg>
              </div>
              <div className="flex-1">
                <h2 className="text-lg lg:text-2xl font-bold text-white">Indicadores de Estaciones Meteorológicas</h2>
                <p className="text-orange-50 mt-1 text-sm lg:text-base">Análisis detallado por institución y estación</p>
                {/* Indicador de rango de fechas */}
                {filters.startDate && filters.endDate && (
                  <div className="mt-2 inline-flex items-center px-3 py-1 bg-white/20 rounded-full text-xs text-white">
                    <svg className="w-3 h-3 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                    {new Date(filters.startDate).toLocaleDateString('es-ES')} - {new Date(filters.endDate).toLocaleDateString('es-ES')}
                  </div>
                )}
              </div>
            </div>
          </div>
          
          {/* Contenido de la sección */}
          <div className="p-4 lg:p-8">
            <WeatherStationFilters 
              onFiltersChange={handleFilterChange}
              authToken={authToken}
            />

            {/* Mensaje informativo sobre fechas por defecto */}
            {filters.institutionId && !filters.startDate && !filters.endDate && (
              <div className="mb-4 p-3 bg-orange-50 border border-orange-200 rounded-lg">
                <div className="flex items-center text-sm text-orange-700">
                  <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <span>Mostrando datos de los últimos 10 días. Selecciona fechas específicas para personalizar el rango.</span>
                </div>
        </div>
            )}

            {/* Estado de carga */}
            {weatherLoading && (
              <div className="mb-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
                <div className="flex items-center text-sm text-blue-700">
                  <div className="animate-spin rounded-full h-4 w-4 border-2 border-blue-600 border-t-transparent mr-2"></div>
                  <span>Cargando datos meteorológicos...</span>
                </div>
                </div>
            )}

            {weatherLoading && (
              <div className="flex items-center justify-center py-8 lg:py-12 transition-opacity duration-300 ease-in-out">
                <div className="flex flex-col items-center">
                  <div className="relative">
                    <div className="animate-spin rounded-full h-12 w-12 lg:h-16 lg:w-16 border-4 border-orange-200"></div>
                    <div className="animate-spin rounded-full h-12 w-12 lg:h-16 lg:w-16 border-4 border-transparent border-t-orange-600 absolute top-0 left-0"></div>
                </div>
                  <p className="mt-3 lg:mt-4 text-base lg:text-lg font-medium text-gray-700">Cargando datos meteorológicos...</p>
                  <p className="mt-1 lg:mt-2 text-sm text-gray-600">Procesando indicadores meteorológicos</p>
                </div>
                </div>
            )}

            {weatherError && (
              <div className="bg-gradient-to-r from-red-50 to-pink-50 border border-red-200 rounded-xl p-4 lg:p-6 shadow-sm">
                <div className="flex items-start">
                  <div className="flex-shrink-0">
                    <div className="p-2 bg-red-100 rounded-lg">
                      <svg className="w-5 h-5 lg:w-6 lg:h-6 text-red-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
          </div>
                  <div className="ml-3 lg:ml-4">
                    <h3 className="text-base lg:text-lg font-semibold text-red-800 mb-1">Error al cargar datos</h3>
                    <p className="text-red-700 text-sm lg:text-base">{weatherError}</p>
              </div>
              </div>
          </div>
        )}
          </div>
        </div>
      </section>

      {/* Gráficos con diseño moderno */}
      {weatherData && weatherData.results && weatherData.results.length > 0 && (
        <section className="bg-white/90 backdrop-blur-sm rounded-2xl shadow-xl border border-white/20 p-4 lg:p-8 mb-6 lg:mb-8">
          
          <div className="space-y-6 lg:space-y-8">
            {/* Gráfico principal de irradiancia - Ancho completo */}
            <div className="w-full">
                <ChartCard
                title="Análisis de Irradiancia Solar"
                description="Irradiancia acumulada y horas solares pico en el tiempo"
                  type="line"
                data={irradianceChartData}
                options={{
                  ...CHART_OPTIONS,
                  plugins: {
                    ...CHART_OPTIONS.plugins,
                    title: { display: false },
                    legend: {
                      ...CHART_OPTIONS.plugins.legend,
                      position: 'top',
                      align: 'start',
                      labels: {
                        ...CHART_OPTIONS.plugins.legend.labels,
                        usePointStyle: true,
                        padding: 20,
                        font: { size: 13, weight: '600' }
                      }
                    }
                  },
                  scales: {
                    ...CHART_OPTIONS.scales,
                    y: {
                      ...CHART_OPTIONS.scales.y,
                      beginAtZero: true,
                      grid: { color: 'rgba(0, 0, 0, 0.05)' }
                    }
                  }
                }}
                height="400px"
                fullscreenHeight="800px"
                />
              </div>

            {/* Gráficos secundarios en grid responsive - Máximo ancho */}
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 lg:gap-6 xl:gap-8 w-full">
              {/* Condiciones ambientales */}
              <ChartCard
                title="Condiciones Ambientales"
                description="Temperatura y humedad relativa del ambiente"
                type="line"
                data={ambientConditionsChartData}
                options={{
                  ...CHART_OPTIONS,
                  plugins: {
                    ...CHART_OPTIONS.plugins,
                    title: { display: false },
                    legend: {
                      ...CHART_OPTIONS.plugins.legend,
                      position: 'top',
                      align: 'start'
                    }
                  }
                }}
                height="350px"
                fullscreenHeight="700px"
              />

              {/* Condiciones del viento */}
                <ChartCard
                title="Condiciones del Viento"
                description="Velocidad del viento y precipitación"
                  type="line"
                data={windConditionsChartData}
                options={{
                  ...CHART_OPTIONS,
                  plugins: {
                    ...CHART_OPTIONS.plugins,
                    title: { display: false },
                    legend: {
                      ...CHART_OPTIONS.plugins.legend,
                      position: 'top',
                      align: 'start'
                    }
                  }
                }}
                height="350px"
                fullscreenHeight="700px"
                />
              </div>
              </div>
        </section>
      )}

      {/* Rosa de los Vientos - Nuevo gráfico */}
      {weatherData && weatherData.results && weatherData.results.length > 0 && (
        <section className="bg-white/90 backdrop-blur-sm rounded-2xl shadow-xl border border-white/20 p-4 lg:p-8 mb-6 lg:mb-8">
          <div className="space-y-6 lg:space-y-8">
            <div className="mx-auto w-full max-w-[440px]">
              {(() => {
                // Rosa de los vientos: UN pétalo por dirección cardinal (frecuencia total de
                // lecturas del rango). El desglose por banda de velocidad (0-5/5-10/10+ km/h,
                // asignada por la velocidad media de cada día) se muestra en el tooltip.
                const { labels, slow, mid, fast, total, chartData } = windRoseBundle;
                return (
                  <ChartCard
                    title="Rosa de los Vientos"
                    description="Frecuencia del viento por dirección en el rango. El detalle por banda de velocidad aparece al pasar el cursor."
                    type="polarArea"
                    data={chartData}
                    options={{
                      responsive: true,
                      maintainAspectRatio: false,
                      plugins: {
                        legend: { display: false },
                        tooltip: {
                          callbacks: {
                            title: (items) => (items.length ? `Viento del ${labels[items[0].dataIndex]}` : ''),
                            label: (ctx) => {
                              const i = ctx.dataIndex;
                              return [
                                `Total: ${total[i]} lecturas`,
                                `0–5 km/h: ${slow[i] || 0}`,
                                `5–10 km/h: ${mid[i] || 0}`,
                                `10+ km/h: ${fast[i] || 0}`,
                              ];
                            },
                          },
                        },
                      },
                      scales: {
                        r: {
                          beginAtZero: true,
                          grid: { color: 'rgba(0, 0, 0, 0.08)' },
                          angleLines: { color: 'rgba(0, 0, 0, 0.08)' },
                          pointLabels: { display: true, font: { size: 14, weight: '700' }, color: '#334155' },
                          ticks: { display: true, backdropColor: 'transparent', color: '#64748b', font: { size: 10 }, precision: 0 },
                        },
                      },
                    }}
                    height="420px"
                    fullscreenHeight="760px"
                  />
                );
              })()}
                          </div>
                        </div>
        </section>
      )}

      {/* Potencia Fotovoltaica Teórica - Nuevo gráfico */}
      {weatherData && weatherData.results && weatherData.results.length > 0 && (
        <section className="bg-white/90 backdrop-blur-sm rounded-2xl shadow-xl border border-white/20 p-4 lg:p-8 mb-6 lg:mb-8">
          <div className="space-y-6 lg:space-y-8">
            <div className="w-full">
              <ChartCard
                title="Potencia Fotovoltaica Teórica"
                description="Potencia teórica generada basada en irradiancia solar y condiciones ambientales"
                type="line"
                data={pvTheoreticalPowerChartData}
                options={{
                  ...CHART_OPTIONS,
                  plugins: {
                    ...CHART_OPTIONS.plugins,
                    title: { display: false },
                    legend: {
                      ...CHART_OPTIONS.plugins.legend,
                      position: 'top',
                      align: 'start',
                      labels: {
                        ...CHART_OPTIONS.plugins.legend.labels,
                        usePointStyle: true,
                        padding: 20,
                        font: { size: 13, weight: '600' }
                      }
                    }
                  },
                  scales: {
                    y: {
                      ...CHART_OPTIONS.scales.y,
                      beginAtZero: true,
                      grid: { color: 'rgba(0, 0, 0, 0.05)' },
                      title: {
                        display: true,
                        text: 'Potencia (W)',
                        font: { size: 14, weight: '600' }
                      }
                    },
                    y1: {
                      type: 'linear',
                      display: true,
                      position: 'right',
                      beginAtZero: true,
                      grid: { drawOnChartArea: false },
                      title: {
                        display: true,
                        text: 'Irradiancia (kWh/m²)',
                        font: { size: 14, weight: '600' }
                      }
                    }
                  }
                }}
                height="400px"
                fullscreenHeight="800px"
              />
                          </div>
                        </div>
      </section>
      )}

      {/* Datos Históricos Detallados */}
      {weatherData?.results && weatherData.results.length > 0 && (
        // Nueva Sección de Tabla de Datos
        <section className="mb-6 lg:mb-8">
          <div className="bg-white/95 backdrop-blur-sm rounded-2xl shadow-xl border border-white/30 overflow-hidden">
            {/* Header de la sección de tabla */}
            <div className="bg-gradient-to-r from-orange-700 to-amber-800 px-4 lg:px-6 xl:px-8 py-4 lg:py-6">
              <div className="flex flex-col lg:flex-row lg:items-center space-y-3 lg:space-y-0 lg:space-x-4">
                <div className="p-2 lg:p-3 bg-white/20 rounded-xl self-start lg:self-auto">
                  <svg className="w-6 h-6 lg:w-7 lg:h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <circle cx="12" cy="6" r="2"></circle>
                    <path d="M12 8v4"></path>
                    <path d="M6 20h12"></path>
                    <path d="M12 12l4 8"></path>
                    <path d="M12 12l-4 8"></path>
                    <path d="M4 10a8 8 0 0116 0"></path>
                  </svg>
                </div>
                <div>
                  <h2 className="text-lg lg:text-xl xl:text-2xl font-bold text-white">Datos Históricos Detallados</h2>
                  <p className="text-orange-50 mt-1 text-sm lg:text-base">Registros completos de indicadores meteorológicos por fecha y estación</p>
                </div>
              </div>
            </div>
            
            {/* Contenido de la tabla */}
            <div className="p-3 lg:p-4 xl:p-6">
              {/* Tabla de datos moderna y responsive */}
              <div className="bg-white rounded-xl shadow-lg border border-gray-100 overflow-hidden">
                <div className="px-3 lg:px-4 xl:px-6 py-3 lg:py-4 xl:py-6 border-b border-gray-100 bg-gradient-to-r from-gray-50 to-gray-100">
                  <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between space-y-3 lg:space-y-0">
                    <div className="flex items-center space-x-3">
                      <div className="p-2 bg-orange-100 rounded-lg">
                        <svg className="w-5 h-5 lg:w-6 lg:h-6 text-orange-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <circle cx="12" cy="6" r="2"></circle>
                          <path d="M12 8v4"></path>
                          <path d="M6 20h12"></path>
                          <path d="M12 12l4 8"></path>
                          <path d="M12 12l-4 8"></path>
                          <path d="M4 10a8 8 0 0116 0"></path>
                        </svg>
                      </div>
                      <div>
                        <h3 className="text-base lg:text-lg xl:text-xl font-bold text-gray-800">Indicadores Meteorológicos Detallados</h3>
                        <p className="text-gray-600 mt-1 text-sm">Datos históricos y análisis de tendencias climáticas</p>
                        {/* Indicador de fechas por defecto */}
                        {filters.institutionId && !filters.startDate && !filters.endDate && (
                          <div className="mt-2 inline-flex items-center px-2 py-1 bg-orange-50 border border-orange-200 rounded-full text-xs text-orange-700">
                            <svg className="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                            Últimos 10 días
                          </div>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center space-x-2">
                      <div className="px-3 lg:px-4 py-2 bg-gradient-to-r from-orange-500 to-amber-600 text-white text-sm font-semibold rounded-lg shadow-sm">
                        {weatherData.results.length} registros totales
                      </div>
                      {getTotalPages() > 1 && (
                        <div className="px-3 lg:px-4 py-2 bg-blue-100 text-blue-700 text-sm font-semibold rounded-lg">
                          Página {currentPage} de {getTotalPages()}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
                
                {/* Tabla responsive con scroll horizontal */}
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-100">
                    <thead className="bg-gradient-to-r from-orange-50 to-amber-50">
                      <tr>
                        {[
                          { label: 'Fecha', width: 'w-20 lg:w-24 xl:w-32' },
                          { label: 'Estación', width: 'w-24 lg:w-28 xl:w-36' },
                          { label: 'Irradiancia (kWh/m²)', width: 'w-32 lg:w-36 xl:w-40' },
                          { label: 'HSP (Horas)', width: 'w-24 lg:w-28 xl:w-32' },
                          { label: 'Temperatura (°C)', width: 'w-28 lg:w-32 xl:w-36' },
                          { label: 'Humedad (%)', width: 'w-24 lg:w-28 xl:w-32' },
                          { label: 'Viento (km/h)', width: 'w-24 lg:w-28 xl:w-32' },
                          { label: 'Precipitación (cm)', width: 'w-28 lg:w-32 xl:w-36' }
                        ].map((header) => (
                          <th key={header.label} className={`${header.width} px-2 lg:px-3 xl:px-4 py-2 lg:py-3 xl:py-5 text-left text-xs font-bold text-orange-700 uppercase tracking-wider border-b border-orange-100`}>
                            {header.label}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-y divide-gray-50">
                      {getCurrentPageData().length > 0 ? (
                        getCurrentPageData().map((item, index) => (
                          <tr key={`${currentPage}-${index}`} className="hover:bg-orange-50 transition-colors duration-150 border-b border-gray-50">
                            <td className="px-2 lg:px-3 xl:px-4 py-2 lg:py-3 xl:py-4 whitespace-nowrap">
                              <div className="text-xs lg:text-sm font-medium text-gray-900">
                                {(() => {
                                  // 🔍 CORREGIR PROCESAMIENTO DE FECHAS PARA EVITAR DESFASE
                                  const rawDate = item.date;
                                  const localDate = new Date(rawDate + 'T00:00:00');
                                  return localDate.toLocaleDateString('es-ES');
                                })()}
                              </div>
                              <div className="text-xs text-gray-600">
                                {(() => {
                                  // 🔍 CORREGIR PROCESAMIENTO DE FECHAS PARA EVITAR DESFASE
                                  const rawDate = item.date;
                                  const localDate = new Date(rawDate + 'T00:00:00');
                                  return localDate.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' });
                                })()}
                              </div>
                            </td>
                            <td className="px-2 lg:px-3 xl:px-4 py-2 lg:py-3 xl:py-4 whitespace-nowrap">
                              <div className="text-xs lg:text-sm font-medium text-gray-900">{item.device_name || 'N/A'}</div>
                            </td>
                            <td className="px-2 lg:px-3 xl:px-4 py-2 lg:py-3 xl:py-4 whitespace-nowrap">
                              <div className="text-xs lg:text-sm font-medium text-gray-900">
                                {(item.daily_irradiance_kwh_m2 || 0).toFixed(2)}
                              </div>
                            </td>
                            <td className="px-2 lg:px-3 xl:px-4 py-2 lg:py-3 xl:py-4 whitespace-nowrap">
                              <div className="text-xs lg:text-sm font-medium text-gray-900">
                                {(item.daily_hsp_hours || 0).toFixed(1)}
                              </div>
                            </td>
                            <td className="px-2 lg:px-3 xl:px-4 py-2 lg:py-3 xl:py-4 whitespace-nowrap">
                              <div className="text-xs lg:text-sm font-medium text-gray-900">
                                {(item.avg_temperature_c || 0).toFixed(1)}
                              </div>
                            </td>
                            <td className="px-2 lg:px-3 xl:px-4 py-2 lg:py-3 xl:py-4 whitespace-nowrap">
                              <div className="text-xs lg:text-sm font-medium text-gray-900">
                                {(item.avg_humidity_pct || 0).toFixed(1)}
                              </div>
                            </td>
                            <td className="px-2 lg:px-3 xl:px-4 py-2 lg:py-3 xl:py-4 whitespace-nowrap">
                              <div className="text-xs lg:text-sm font-medium text-gray-900">
                                {(item.avg_wind_speed_kmh || 0).toFixed(1)}
                              </div>
                            </td>
                            <td className="px-2 lg:px-3 xl:px-4 py-2 lg:py-3 xl:py-4 whitespace-nowrap">
                              <div className="text-xs lg:text-sm font-medium text-gray-900">
                                {(item.daily_precipitation_cm || 0).toFixed(2)}
                              </div>
                            </td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan="8" className="px-4 py-8 text-center text-gray-600">
                            No hay datos disponibles para mostrar
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
                
                {/* Controles de paginación */}
                {getTotalPages() > 1 && (
                  <div className="px-3 lg:px-4 xl:px-6 py-4 lg:py-6 border-t border-gray-100 bg-gradient-to-r from-gray-50 to-gray-100">
                    <div className="flex flex-col sm:flex-row items-center justify-between space-y-3 sm:space-y-0">
                      {/* Información de paginación y selector de registros por página */}
                      <div className="flex flex-col sm:flex-row items-center space-y-2 sm:space-y-0 sm:space-x-4">
                        <div className="text-sm text-gray-600">
                          Mostrando {((currentPage - 1) * recordsPerPage) + 1} a {Math.min(currentPage * recordsPerPage, weatherData.results.length)} de {weatherData.results.length} registros
                        </div>
                        
                        {/* Selector de registros por página */}
                        <div className="flex items-center space-x-2">
                          <label className="text-sm text-gray-600">Mostrar:</label>
                          <select
                            value={recordsPerPage}
                            onChange={(e) => handleRecordsPerPageChange(Number(e.target.value))}
                            className="px-3 py-1 text-sm border border-gray-300 rounded-lg bg-white focus:ring-2 focus:ring-orange-500 focus:border-orange-500"
                          >
                            <option value={10}>10</option>
                            <option value={20}>20</option>
                            <option value={50}>50</option>
                            <option value={100}>100</option>
                          </select>
                          <span className="text-sm text-gray-600">por página</span>
                        </div>
                      </div>
                      
                      {/* Controles de navegación */}
                      <div className="flex items-center space-x-2">
                        {/* Botón Primera Página */}
                        <button
                          onClick={() => handlePageChange(1)}
                          disabled={currentPage === 1}
                          className={`px-3 py-2 text-sm font-medium rounded-lg transition duration-150 ${
                            currentPage === 1
                              ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                              : 'bg-white text-gray-700 hover:bg-gray-50 border border-gray-300 hover:border-gray-400'
                          }`}
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
                          </svg>
                        </button>
                        
                        {/* Botón Página Anterior */}
                        <button
                          onClick={() => handlePageChange(currentPage - 1)}
                          disabled={currentPage === 1}
                          className={`px-3 py-2 text-sm font-medium rounded-lg transition duration-150 ${
                            currentPage === 1
                              ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                              : 'bg-white text-gray-700 hover:bg-gray-50 border border-gray-300 hover:border-gray-400'
                          }`}
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                          </svg>
                        </button>
                        
                        {/* Números de página */}
                        <div className="flex items-center space-x-1">
                          {Array.from({ length: Math.min(5, getTotalPages()) }, (_, i) => {
                            let pageNum;
                            if (getTotalPages() <= 5) {
                              pageNum = i + 1;
                            } else if (currentPage <= 3) {
                              pageNum = i + 1;
                            } else if (currentPage >= getTotalPages() - 2) {
                              pageNum = getTotalPages() - 4 + i;
                            } else {
                              pageNum = currentPage - 2 + i;
                            }
                            
                            return (
                              <button
                                key={pageNum}
                                onClick={() => handlePageChange(pageNum)}
                                className={`px-3 py-2 text-sm font-medium rounded-lg transition duration-150 ${
                                  currentPage === pageNum
                                    ? 'bg-orange-600 text-white'
                                    : 'bg-white text-gray-700 hover:bg-gray-50 border border-gray-300 hover:border-gray-400'
                                }`}
                              >
                                {pageNum}
                              </button>
                            );
                          })}
                        </div>
                        
                        {/* Botón Página Siguiente */}
                        <button
                          onClick={() => handlePageChange(currentPage + 1)}
                          disabled={currentPage === getTotalPages()}
                          className={`px-3 py-2 text-sm font-medium rounded-lg transition duration-150 ${
                            currentPage === getTotalPages()
                              ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                              : 'bg-white text-gray-700 hover:bg-gray-50 border border-gray-300 hover:border-gray-400'
                          }`}
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                          </svg>
                        </button>
                        
                        {/* Botón Última Página */}
                        <button
                          onClick={() => handlePageChange(getTotalPages())}
                          disabled={currentPage === getTotalPages()}
                          className={`px-3 py-2 text-sm font-medium rounded-lg transition duration-150 ${
                            currentPage === getTotalPages()
                              ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                              : 'bg-white text-gray-700 hover:bg-gray-50 border border-gray-300 hover:border-gray-400'
                          }`}
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 5l7 7-7 7M6 5l7 7-7 7" />
                          </svg>
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </section>
      )}

      {/* Overlay de transición */}
      <TransitionOverlay 
        show={showTransition}
        type={transitionType}
        message={transitionMessage}
      />
    </div>
  );
}

export default WeatherStationDetails;
