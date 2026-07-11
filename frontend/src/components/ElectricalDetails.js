import React, { useState, useEffect, useRef, useCallback } from 'react';
import { KpiCard } from "./KPI/KpiCard";
import { ChartCard } from "./KPI/ChartCard";
import TransitionOverlay from './TransitionOverlay';
import ElectricMeterFilters from './ElectricMeterFilters';
import { buildApiUrl, ENDPOINTS } from '../utils/apiConfig';
import { IconGauge, IconRefresh } from './icons';
import { useDeviceDetail } from '../hooks/useDeviceDetail';

//###########################################################################
// Importaciones Chart.js
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, PointElement, LineElement, BarElement,
  Title, Tooltip, Legend, Filler
} from 'chart.js';
import zoomPlugin from 'chartjs-plugin-zoom';

ChartJS.register(
  CategoryScale, LinearScale, PointElement, LineElement, BarElement,
  Title, Tooltip, Legend, Filler, zoomPlugin
);



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
      <svg className="w-6 h-6 mr-3 text-gray-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={icon} />
      </svg>
      {title}
    </h2>
    <div className="text-sm text-gray-600 bg-gray-50 px-4 py-2 rounded-full border border-gray-200">
      <span className="flex items-center">
        <svg className="w-4 h-4 mr-2 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        {infoText}
      </span>
    </div>
  </div>
);





// Componente principal
function ElectricalDetails({ authToken, onLogout, username, isSuperuser, navigateTo, isSidebarMinimized, setIsSidebarMinimized }) {
  // Estados consolidados
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showTransition, setShowTransition] = useState(false);
  const [transitionType, setTransitionType] = useState('info');
  const [transitionMessage, setTransitionMessage] = useState('');
  
  // Filtros, datos y lógica de fetch: extraídos a useDeviceDetail (Ola 5).
  // (el hook se inicializa más abajo, tras definir showTransitionAnimation).

  // Estados de paginación
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage] = useState(30);

  // Estados para mostrar información detallada de KPIs
  const [showKpiInfo, setShowKpiInfo] = useState(null);
  const [isAnimating, setIsAnimating] = useState(false);
  const [isOpening, setIsOpening] = useState(false);

  // KPIs dinámicos basados en datos reales
  const [kpiData, setKpiData] = useState({
    totalEnergyConsumed: { 
      title: "Energía Total Consumida", 
      value: "0.00", 
      unit: "kWh", 
      change: "Este período", 
      status: "normal", 
      icon: <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M13 2L3 14h9l-1 8 11-12h-9l1-8z"></path></svg>,
      color: "text-blue-700"
    },
    peakDemand: { 
      title: "Demanda Pico", 
      value: "0.00", 
      unit: "kW", 
      change: "Máximo registrado", 
      status: "normal", 
      icon: <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="22,7 13.5,15.5 8.5,10.5 2,17"></polyline><polyline points="16,7 22,7 22,13"></polyline></svg>,
      color: "text-red-700"
    },
    loadFactor: { 
      title: "Factor de Carga", 
      value: "0.0", 
      unit: "%", 
      change: "Eficiencia del sistema", 
      status: "normal", 
      icon: <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 3v18h18"></path><path d="M18 17V9"></path><path d="M13 17V5"></path><path d="M8 17v-3"></path></svg>,
      color: "text-green-700"
    },
    powerFactor: { 
      title: "Factor de Potencia", 
      value: "0.00", 
      unit: "", 
      change: "Calidad de energía", 
      status: "normal", 
      icon: <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"></circle><path d="M12 6v6l4 2"></path></svg>,
      color: "text-purple-700"
    }
  });

  // Funciones optimizadas
  const showTransitionAnimation = (type = 'info', message = '', duration = 2000) => {
    setTransitionType(type);
    setTransitionMessage(message);
    setShowTransition(true);
    setTimeout(() => setShowTransition(false), duration);
  };

  // Filtros + datos + fetch (race-guard, dedup, debounce) y cálculo: en useDeviceDetail.
  const {
    data: meterData,
    loading: meterLoading,
    error: meterError,
    filters,
    handleFiltersChange,
    calculate: calculateElectricalData,
    fetchData: fetchMeterData,
  } = useDeviceDetail({
    indicatorsEndpoint: ENDPOINTS.electrical.indicators,
    calculateEndpoint: ENDPOINTS.electrical.calculate,
    authToken,
    onNotify: showTransitionAnimation,
  });

  // Funciones de paginación
  const resetPagination = () => {
    setCurrentPage(1);
  };

  const goToPage = (page) => {
    setCurrentPage(page);
  };

  const goToNextPage = () => {
    if (currentPage < totalPages) {
      setCurrentPage(currentPage + 1);
    }
  };

  const goToPreviousPage = () => {
    if (currentPage > 1) {
      setCurrentPage(currentPage - 1);
    }
  };

  // Calcular datos de paginación
  const totalItems = meterData?.results?.length || 0;
  const totalPages = Math.ceil(totalItems / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const endIndex = startIndex + itemsPerPage;
  const currentItems = meterData?.results?.slice(startIndex, endIndex) || [];




  // Cargar datos iniciales al montar el componente
  useEffect(() => {
    if (authToken) {
      setLoading(true);
      // Simular un pequeño delay para mostrar la animación
      setTimeout(() => {
        setLoading(false);
      }, 300);
    }
  }, [authToken]);

  // Efecto para actualizar datos cuando cambien los filtros
  useEffect(() => {
    if (filters.institutionId && (filters.startDate || filters.endDate)) {
      // Si hay institución seleccionada y fechas, cargar datos
      fetchMeterData(filters);
    }
  }, [filters, fetchMeterData]);

  // Resetear paginación cuando cambien los filtros
  useEffect(() => {
    resetPagination();
  }, [filters.institutionId, filters.deviceId, filters.startDate, filters.endDate]);

  // Resetear paginación cuando se carguen nuevos datos
  useEffect(() => {
    if (meterData && meterData.results) {
      resetPagination();
    }
  }, [meterData]);

  // Actualizar KPIs cuando cambien los datos del medidor
  useEffect(() => {
    if (meterData && meterData.results && meterData.results.length > 0) {
      const latestData = meterData.results[0];
      const totalEnergy = meterData.results.reduce((sum, item) => sum + (item.imported_energy_kwh || 0), 0);
      
      setKpiData(prev => ({
        totalEnergyConsumed: {
          ...prev.totalEnergyConsumed,
          value: totalEnergy.toFixed(2),
          change: `${meterData.results.length} registros`
        },
        peakDemand: {
          ...prev.peakDemand,
          value: (latestData.peak_demand_kw || 0).toFixed(2),
          change: latestData.date ? new Date(latestData.date).toLocaleDateString('es-ES') : 'Último registro'
        },
        loadFactor: {
          ...prev.loadFactor,
          value: (latestData.load_factor_pct || 0).toFixed(1),
          change: latestData.load_factor_pct > 80 ? 'Excelente' : latestData.load_factor_pct > 60 ? 'Bueno' : 'Mejorable'
        },
        powerFactor: {
          ...prev.powerFactor,
          value: (latestData.avg_power_factor || 0).toFixed(2),
          change: latestData.avg_power_factor > 0.95 ? 'Óptimo' : latestData.avg_power_factor > 0.85 ? 'Bueno' : 'Mejorable'
        }
      }));
    }
  }, [meterData]);

  // Función para obtener información detallada de cada KPI
  const getKpiDetailedInfo = (kpiKey) => {
    const kpiInfo = {
      totalEnergyConsumed: {
        title: "Energía Total Consumida",
        description: "Representa la cantidad total de energía eléctrica consumida por los medidores monitoreados en la institución seleccionada.",
        calculation: "Se calcula sumando la energía importada (imported_energy_kwh) de todos los medidores activos durante el período seleccionado.",
        dataSource: "Datos obtenidos de medidores eléctricos SCADA en tiempo real, incluyendo lecturas de energía activa.",
        units: "kWh (kilovatios-hora)",
        frequency: "Actualización cada 5 minutos desde SCADA, cálculo automático según el período seleccionado."
      },
      peakDemand: {
        title: "Demanda Pico",
        description: "Representa la máxima potencia demandada por los medidores eléctricos en un momento específico del período.",
        calculation: "Se identifica el valor más alto de potencia activa (peak_demand_kw) registrado durante el período de análisis.",
        dataSource: "Mediciones de potencia instantánea desde medidores eléctricos SCADA.",
        units: "kW (kilovatios)",
        frequency: "Actualización cada 5 minutos desde SCADA, identificación automática del pico máximo."
      },
      loadFactor: {
        title: "Factor de Carga",
        description: "Indica la eficiencia del uso de la capacidad instalada, comparando la demanda promedio con la demanda máxima.",
        calculation: "Factor de Carga = (Demanda Promedio / Demanda Máxima) × 100%. Valores altos indican uso eficiente.",
        dataSource: "Cálculo derivado de las mediciones de potencia activa de medidores eléctricos.",
        units: "% (porcentaje)",
        frequency: "Cálculo automático basado en datos de potencia, actualización según el período seleccionado."
      },
      powerFactor: {
        title: "Factor de Potencia",
        description: "Mide la eficiencia del uso de la potencia aparente, indicando qué tan bien se aprovecha la energía eléctrica.",
        calculation: "Factor de Potencia = Potencia Activa / Potencia Aparente. Valores cercanos a 1.0 indican alta eficiencia.",
        dataSource: "Mediciones de potencia activa y aparente desde medidores eléctricos SCADA.",
        units: "Adimensional (sin unidades)",
        frequency: "Actualización cada 5 minutos desde SCADA, promedio automático del período seleccionado."
      }
    };
    
    return kpiInfo[kpiKey] || null;
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



  // Estados de carga y error (suavizados)
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-100">
        <div className="flex flex-col items-center">
          <div className="animate-spin rounded-full h-16 w-16 border-t-4 border-b-4 border-green-500"></div>
          <p className="mt-4 text-lg text-gray-700">Cargando datos eléctricos...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-100">
        <div className="text-red-700 text-lg p-4 bg-red-100 rounded-lg shadow-md">Error: {error}</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <header className="bg-gradient-to-r from-green-700 to-emerald-800 shadow-lg -mx-4 lg:-mx-8 -mt-4 lg:-mt-8">
        <div className="px-4 lg:px-8 py-8 lg:py-12">
        <div className="flex flex-col lg:flex-row lg:items-center space-y-4 lg:space-y-0 lg:space-x-4">
            <div className="p-3 bg-white/20 rounded-xl self-start lg:self-auto">
              <IconGauge className="w-6 h-6 lg:w-8 lg:h-8 text-white" />
            </div>
            <div>
              <h1 className="text-2xl lg:text-4xl font-bold text-white">Detalles Eléctricos</h1>
              <p className="text-green-50 mt-1 text-sm lg:text-base">Análisis y monitoreo de indicadores eléctricos</p>
            </div>
          </div>
        </div>
      </header>

      {/* KPIs */}
      <section className="bg-white/90 backdrop-blur-sm rounded-2xl shadow-xl border border-white/20 p-4 lg:p-8 -mt-4 lg:-mt-8 mb-6 lg:mb-8">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 lg:gap-6">
          {!filters.institutionId ? (
            // Estado de carga cuando no hay institución seleccionada
            Array.from({ length: 4 }).map((_, index) => (
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
          ) : meterLoading ? (
            // Estado de carga cuando se están cargando los datos
            Array.from({ length: 4 }).map((_, index) => (
              <div key={index} className="bg-white rounded-xl shadow-lg border border-blue-200 p-6 overflow-hidden relative">
                {/* Skeleton loader con animación azul */}
                <div className="animate-pulse">
                  {/* Icono skeleton */}
                  <div className="flex items-center justify-between mb-4">
                    <div className="w-12 h-12 bg-blue-200 rounded-lg"></div>
                    <div className="w-20 h-4 bg-blue-200 rounded"></div>
                  </div>
                  
                  {/* Título skeleton */}
                  <div className="w-32 h-5 bg-blue-200 rounded mb-2"></div>
                  
                  {/* Valor skeleton */}
                  <div className="flex items-baseline">
                    <div className="w-24 h-8 bg-blue-200 rounded"></div>
                    <div className="w-16 h-6 bg-blue-200 rounded ml-2"></div>
                  </div>
                  
                  {/* Línea inferior skeleton */}
                  <div className="mt-3 pt-3 border-t border-blue-100">
                    <div className="w-28 h-3 bg-blue-200 rounded"></div>
        </div>
      </div>

                {/* Overlay de shimmer azul */}
                <div className="absolute inset-0 bg-gradient-to-r from-transparent via-blue-100/30 to-transparent animate-shimmer pointer-events-none"></div>
              </div>
            ))
          ) : (
            // KPIs reales cuando hay datos
            Object.keys(kpiData).map((key) => {
              const item = kpiData[key];
              // Mapear colores del KPI a colores de estilo adaptado
              const colorMap = {
                'text-blue-700': { bgColor: 'bg-blue-50', borderColor: 'border-blue-200' },
                'text-red-700': { bgColor: 'bg-red-50', borderColor: 'border-red-200' },
                'text-green-700': { bgColor: 'bg-green-50', borderColor: 'border-green-200' },
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
            })
          )}
        </div>
        
        {/* Mensaje de estado */}
        {!filters.institutionId && (
          <div className="text-center mt-4 lg:mt-6">
            <div className="inline-flex items-center px-3 lg:px-4 py-2 bg-blue-50 border border-blue-200 rounded-full text-sm lg:text-base">
              <svg className="w-4 h-4 lg:w-5 lg:h-5 text-blue-500 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className="text-blue-700 font-medium">Selecciona una institución para ver los indicadores</span>
            </div>
          </div>
        )}
        
        {filters.institutionId && meterLoading && (
          <div className="text-center mt-4 lg:mt-6">
            <div className="inline-flex items-center px-3 lg:px-4 py-2 bg-blue-50 border border-blue-200 rounded-full text-sm lg:text-base">
              <svg className="w-4 h-4 lg:w-5 lg:h-5 text-blue-500 mr-2 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              <span className="text-blue-700 font-medium">Cargando indicadores de la institución...</span>
            </div>
          </div>
        )}
        
        {filters.institutionId && !meterLoading && meterData && (!meterData.results || meterData.results.length === 0) && (
          <div className="text-center mt-4 lg:mt-6">
            <div className="inline-flex items-center px-3 lg:px-4 py-2 bg-yellow-50 border border-yellow-200 rounded-full text-sm lg:text-base">
              <svg className="w-4 h-4 lg:w-5 lg:h-5 text-yellow-500 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
              </svg>
              <span className="text-yellow-700 font-medium">No hay datos disponibles para esta institución en el período seleccionado</span>
            </div>
            <div className="mt-4">
              <button
                onClick={calculateElectricalData}
                disabled={meterLoading}
                className="inline-flex items-center px-4 py-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white font-medium rounded-lg shadow-lg hover:shadow-xl transition duration-150 transform hover:scale-105 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {meterLoading ? (
                  <>
                    <svg className="w-4 h-4 mr-2 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                    Calculando...
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                    Calcular Datos Eléctricos
                  </>
                )}
              </button>
            </div>
          </div>
        )}
        
        {/* Overlay de información detallada del KPI - Se superpone en toda la sección */}
        {showKpiInfo && getKpiDetailedInfo(showKpiInfo) && (
          <div 
            className={`absolute inset-0 bg-white/95 backdrop-blur-sm rounded-2xl border-2 border-gray-200 shadow-2xl z-20 p-8 overflow-y-auto transition duration-300 ease-out transform ${
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
            </div>
          </div>
        )}
      </section>

      {/* Sección de Medidores Eléctricos */}
      <section className="mb-6 lg:mb-8">
        <div className="bg-white/95 backdrop-blur-sm rounded-2xl shadow-xl border border-white/30 overflow-hidden">
          {/* Header de la sección */}
          <div className="bg-gradient-to-r from-green-700 to-emerald-800 px-4 lg:px-8 py-4 lg:py-6">
            <div className="flex flex-col lg:flex-row lg:items-center space-y-3 lg:space-y-0 lg:space-x-4">
              <div className="p-2 lg:p-3 bg-white/20 rounded-xl self-start lg:self-auto">
                <svg className="w-6 h-6 lg:w-7 lg:h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <div className="flex-1">
                <h2 className="text-lg lg:text-2xl font-bold text-white">Indicadores de Medidores Eléctricos</h2>
                <p className="text-indigo-50 mt-1 text-sm lg:text-base">Análisis detallado por institución y medidor</p>
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
          <ElectricMeterFilters onFiltersChange={handleFiltersChange} authToken={authToken} />

          {/* Mensaje informativo sobre fechas por defecto */}
          {filters.institutionId && !filters.startDate && !filters.endDate && (
            <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
              <div className="flex items-center text-sm text-blue-700">
                <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span>Mostrando datos de los últimos 10 días. Selecciona fechas específicas para personalizar el rango.</span>
              </div>
            </div>
          )}

          {meterLoading && (
            <div className="flex items-center justify-center py-8 lg:py-12 transition-opacity duration-300 ease-in-out">
              <div className="flex flex-col items-center">
                <div className="relative">
                  <div className="animate-spin rounded-full h-12 w-12 lg:h-16 lg:w-16 border-4 border-indigo-200"></div>
                  <div className="animate-spin rounded-full h-12 w-12 lg:h-16 lg:w-16 border-4 border-transparent border-t-indigo-600 absolute top-0 left-0"></div>
                </div>
                <p className="mt-3 lg:mt-4 text-base lg:text-lg font-medium text-gray-700">Cargando datos de medidores...</p>
                <p className="mt-1 lg:mt-2 text-sm text-gray-600">Procesando indicadores eléctricos</p>
              </div>
            </div>
          )}

          {meterError && (
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
                  <p className="text-red-700 text-sm lg:text-base">{meterError}</p>
                </div>
              </div>
            </div>
          )}

          {meterData && !meterLoading && (
            <>


              {/* Gráficos con diseño moderno */}
              {meterData.results && meterData.results.length > 0 && (
                <div className="space-y-6 lg:space-y-8">
                  {/* Gráfico principal de energía - Ancho completo */}
                  <div className="w-full">
                  <ChartCard
                      title="Análisis de Energía"
                      description="Consumo, exportación y balance energético en el tiempo"
                    type="line"
                    data={{
                        labels: meterData.results.slice().reverse().map(item => {
                          // 🔍 CORREGIR PROCESAMIENTO DE FECHAS PARA EVITAR DESFASE
                          const rawDate = item.date;
                          // Crear fecha en zona horaria local para evitar desfase UTC
                          const localDate = new Date(rawDate + 'T00:00:00');
                          const formattedDate = localDate.toLocaleDateString('es-ES');
                          
                          console.log('🔍 PROCESAMIENTO DE FECHA EN CHART PRINCIPAL:');
                          console.log('  Fecha raw:', rawDate);
                          console.log('  Fecha local:', localDate);
                          console.log('  Fecha formateada:', formattedDate);
                          
                          return formattedDate;
                        }),
                      datasets: [
                        {
                            label: 'Energía Importada (kWh)',
                            data: meterData.results.slice().reverse().map(item => item.imported_energy_kwh || 0),
                          borderColor: '#3B82F6',
                            backgroundColor: 'rgba(59, 130, 246, 0.1)',
                          fill: true,
                          tension: 0.4,
                            pointRadius: 4,
                          pointBackgroundColor: '#3B82F6',
                            pointBorderColor: '#ffffff',
                            pointBorderWidth: 2,
                        },
                        {
                            label: 'Energía Exportada (kWh)',
                            data: meterData.results.slice().reverse().map(item => item.exported_energy_kwh || 0),
                          borderColor: '#EF4444',
                            backgroundColor: 'rgba(239, 68, 68, 0.1)',
                            fill: true,
                            tension: 0.4,
                            pointRadius: 4,
                            pointBackgroundColor: '#EF4444',
                            pointBorderColor: '#ffffff',
                            pointBorderWidth: 2,
                          },
                          {
                            label: 'Consumo Neto (kWh)',
                            data: meterData.results.slice().reverse().map(item => item.net_energy_consumption_kwh || 0),
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
                    }}
                      options={{
                        ...CHART_OPTIONS,
                        plugins: {
                          ...CHART_OPTIONS.plugins,
                          title: {display: false},
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
                    {/* Indicadores de calidad */}
                  <ChartCard
                      title="Indicadores de Calidad Eléctrica"
                      description="Demanda, factor de carga y eficiencia del sistema"
                    type="line"
                    data={{
                        labels: meterData.results.slice().reverse().map(item => {
                          // 🔍 CORREGIR PROCESAMIENTO DE FECHAS PARA EVITAR DESFASE
                          const rawDate = item.date;
                          // Crear fecha en zona horaria local para evitar desfase UTC
                          const localDate = new Date(rawDate + 'T00:00:00');
                          const formattedDate = localDate.toLocaleDateString('es-ES');
                          
                          return formattedDate;
                        }),
                      datasets: [
                        {
                            label: 'Demanda Pico (kW)',
                            data: meterData.results.slice().reverse().map(item => item.peak_demand_kw || 0),
                            borderColor: '#F59E0B',
                            backgroundColor: 'rgba(245, 158, 11, 0.1)',
                          fill: true,
                          tension: 0.4,
                            pointRadius: 3,
                            pointBackgroundColor: '#F59E0B',
                          },
                          {
                            label: 'Demanda Promedio (kW)',
                            data: meterData.results.slice().reverse().map(item => item.avg_demand_kw || 0),
                            borderColor: '#8B5CF6',
                            backgroundColor: 'rgba(139, 92, 246, 0.1)',
                          fill: true,
                          tension: 0.4,
                            pointRadius: 3,
                            pointBackgroundColor: '#8B5CF6',
                          },
                          {
                            label: 'Factor de Carga (%)',
                            data: meterData.results.slice().reverse().map(item => item.load_factor_pct || 0),
                            borderColor: '#10B981',
                            backgroundColor: 'rgba(16, 185, 129, 0.1)',
                          fill: false,
                          tension: 0.4,
                            pointRadius: 3,
                            borderDash: [6, 3],
                            pointBackgroundColor: '#10B981',
                          }
                        ]
                      }}
                      options={{
                        ...CHART_OPTIONS,
                        plugins: {
                          ...CHART_OPTIONS.plugins,
                          title: {display: false},
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

                    {/* Calidad de energía */}
                    <ChartCard
                      title="Calidad de Energía"
                      description="Desequilibrios y distorsiones armónicas"
                      type="line"
                      data={{
                        labels: meterData.results.slice().reverse().map(item => {
                          // 🔍 CORREGIR PROCESAMIENTO DE FECHAS PARA EVITAR DESFASE
                          const rawDate = item.date;
                          // Crear fecha en zona horaria local para evitar desfase UTC
                          const localDate = new Date(rawDate + 'T00:00:00');
                          const formattedDate = localDate.toLocaleDateString('es-ES');
                          
                          return formattedDate;
                        }),
                        datasets: [
                          {
                            label: 'Desequilibrio de Voltaje (%)',
                            data: meterData.results.slice().reverse().map(item => item.max_voltage_unbalance_pct || 0),
                            borderColor: '#EF4444',
                            backgroundColor: 'rgba(239, 68, 68, 0.1)',
                            fill: true,
                            tension: 0.4,
                            pointRadius: 3,
                            pointBackgroundColor: '#EF4444',
                          },
                          {
                            label: 'Desequilibrio de Corriente (%)',
                            data: meterData.results.slice().reverse().map(item => item.max_current_unbalance_pct || 0),
                            borderColor: '#F59E0B',
                            backgroundColor: 'rgba(239, 68, 68, 0.1)',
                            fill: true,
                            tension: 0.4,
                            pointRadius: 3,
                            pointBackgroundColor: '#F59E0B',
                          },
                          {
                            label: 'THD de Voltaje (%)',
                            data: meterData.results.slice().reverse().map(item => item.max_voltage_thd_pct || 0),
                            borderColor: '#8B5CF6',
                            backgroundColor: 'rgba(139, 92, 246, 0.1)',
                            fill: false,
                            tension: 0.4,
                            pointRadius: 3,
                            borderDash: [6, 3],
                            pointBackgroundColor: '#8B5CF6',
                            },
                        ]
                      }}
                      options={{
                        ...CHART_OPTIONS,
                        plugins: {
                          ...CHART_OPTIONS.plugins,
                          title: {display: false},
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
              )}

            </>
          )}
          </div>
          </div>
        </section>

        {/* Nueva Sección de Tabla de Datos */}
        {meterData && !meterLoading && meterData.results && meterData.results.length > 0 && (
          <section className="mb-6 lg:mb-8">
            <div className="bg-white/95 backdrop-blur-sm rounded-2xl shadow-xl border border-white/30 overflow-hidden">
              {/* Header de la sección de tabla */}
              <div className="bg-gradient-to-r from-emerald-700 to-teal-800 px-4 lg:px-6 xl:px-8 py-4 lg:py-6">
                <div className="flex flex-col lg:flex-row lg:items-center space-y-3 lg:space-y-0 lg:space-x-4">
                  <div className="p-2 lg:p-3 bg-white/20 rounded-xl self-start lg:self-auto">
                    <svg className="w-6 h-6 lg:w-7 lg:h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                  </div>
                  <div>
                    <h2 className="text-lg lg:text-xl xl:text-2xl font-bold text-white">Datos Históricos Detallados</h2>
                    <p className="text-emerald-50 mt-1 text-sm lg:text-base">Registros completos de indicadores eléctricos por fecha y medidor</p>
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
                        <div className="p-2 bg-emerald-100 rounded-lg">
                          <svg className="w-5 h-5 lg:w-6 lg:h-6 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                          </svg>
                        </div>
                        <div>
                          <h3 className="text-base lg:text-lg xl:text-xl font-bold text-gray-800">Indicadores Eléctricos Detallados</h3>
                          <p className="text-gray-600 mt-1 text-sm">Datos históricos y análisis de tendencias</p>
                          {/* Indicador de fechas por defecto */}
                          {filters.institutionId && !filters.startDate && !filters.endDate && (
                            <div className="mt-2 inline-flex items-center px-2 py-1 bg-blue-50 border border-blue-200 rounded-full text-xs text-blue-700">
                              <svg className="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                              </svg>
                              Últimos 10 días
                            </div>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center space-x-2">
                        <div className="px-3 lg:px-4 py-2 bg-gradient-to-r from-emerald-500 to-teal-600 text-white text-sm font-semibold rounded-lg shadow-sm">
                          {totalItems} registros
                          {totalItems > 30 && (
                            <span className="ml-2 text-xs opacity-90">
                              (página {currentPage} de {totalPages})
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                  
                  {/* Tabla responsive con scroll horizontal */}
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-100">
                      <thead className="bg-gradient-to-r from-emerald-50 to-teal-50">
                        <tr>
                          {[
                            { label: 'Fecha', width: 'w-20 lg:w-24 xl:w-32' },
                            { label: 'Medidor', width: 'w-24 lg:w-28 xl:w-36' },
                            { label: 'Energía Importada (kWh)', width: 'w-32 lg:w-36 xl:w-40' },
                            { label: 'Energía Exportada (kWh)', width: 'w-32 lg:w-36 xl:w-40' },
                            { label: 'Consumo Neto (kWh)', width: 'w-28 lg:w-32 xl:w-36' },
                            { label: 'Demanda Pico (kW)', width: 'w-24 lg:w-28 xl:w-32' },
                            { label: 'Factor de Carga (%)', width: 'w-28 lg:w-32 xl:w-36' },
                            { label: 'Factor de Potencia', width: 'w-24 lg:w-28 xl:w-32' }
                          ].map((header) => (
                            <th key={header.label} className={`${header.width} px-2 lg:px-3 xl:px-4 py-2 lg:py-3 xl:py-5 text-left text-xs font-bold text-emerald-700 uppercase tracking-wider border-b border-emerald-100`}>
                              {header.label}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="bg-white divide-y divide-gray-50">
                        {currentItems && currentItems.length > 0 ? (
                          currentItems.map((item, index) => (
                            <tr key={startIndex + index} className="hover:bg-emerald-50 transition-colors duration-150 border-b border-gray-50">
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
                                <div className="text-xs lg:text-sm font-semibold text-blue-700">
                                  {(item.imported_energy_kwh || 0).toFixed(2)}
                                </div>
                              </td>
                              <td className="px-2 lg:px-3 xl:px-4 py-2 lg:py-3 xl:py-4 whitespace-nowrap">
                                <div className="text-xs lg:text-sm font-semibold text-red-700">
                                  {(item.exported_energy_kwh || 0).toFixed(2)}
                                </div>
                              </td>
                              <td className="px-2 lg:px-3 xl:px-4 py-2 lg:py-3 xl:py-4 whitespace-nowrap">
                                <div className={`text-xs lg:text-sm font-semibold ${(item.net_energy_consumption_kwh || 0) >= 0 ? 'text-green-700' : 'text-orange-700'}`}>
                                  {(item.net_energy_consumption_kwh || 0).toFixed(2)}
                                </div>
                              </td>
                              <td className="px-2 lg:px-3 xl:px-4 py-2 lg:py-3 xl:py-4 whitespace-nowrap">
                                <div className="text-xs lg:text-sm font-semibold text-orange-700">
                                  {(item.peak_demand_kw || 0).toFixed(2)}
                                </div>
                              </td>
                              <td className="px-2 lg:px-3 xl:px-4 py-2 lg:py-3 xl:py-4 whitespace-nowrap">
                                <div className="flex items-center">
                                  <div className="text-xs lg:text-sm font-semibold text-gray-900">
                                    {(item.load_factor_pct || 0).toFixed(1)}%
                                  </div>
                                  <div className={`ml-2 w-2 h-2 rounded-full ${
                                    (item.load_factor_pct || 0) > 80 ? 'bg-green-500' : 
                                    (item.load_factor_pct || 0) > 60 ? 'bg-yellow-500' : 'bg-red-500'
                                  }`}></div>
                                </div>
                              </td>
                              <td className="px-2 lg:px-3 xl:px-4 py-2 lg:py-3 xl:py-4 whitespace-nowrap">
                                <div className="flex items-center">
                                  <div className="text-xs lg:text-sm font-semibold text-gray-900">
                                    {(item.avg_power_factor || 0).toFixed(2)}
                                  </div>
                                  <div className={`ml-2 w-2 h-2 rounded-full ${
                                    (item.avg_power_factor || 0) > 0.95 ? 'bg-green-500' : 
                                    (item.avg_power_factor || 0) > 0.85 ? 'bg-yellow-500' : 'bg-red-500'
                                  }`}></div>
                                </div>
                              </td>
                            </tr>
                          ))
                        ) : (
                          <tr>
                            <td colSpan="8" className="px-4 lg:px-6 py-8 lg:py-12 text-center">
                              <div className="flex flex-col items-center">
                                <svg className="w-10 h-10 lg:w-12 lg:h-12 text-gray-400 mb-3 lg:mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                </svg>
                                <p className="text-base lg:text-lg font-medium text-gray-900 mb-1 lg:mb-2">No hay datos disponibles</p>
                                <p className="text-gray-600 text-sm lg:text-base mb-4">Selecciona una institución y medidor para ver los indicadores eléctricos</p>
                                <button
                                  onClick={calculateElectricalData}
                                  disabled={meterLoading}
                                  className="inline-flex items-center px-4 py-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white font-medium rounded-lg shadow-lg hover:shadow-xl transition duration-150 transform hover:scale-105 disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                  {meterLoading ? (
                                    <>
                                      <svg className="w-4 h-4 mr-2 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                                      </svg>
                                      Calculando...
                                    </>
                                  ) : (
                                    <>
                                      <IconRefresh className="w-4 h-4 mr-2" />
                                      Calcular Datos
                                    </>
                                  )}
                                </button>
                              </div>
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                  
                  {/* Paginación - Solo mostrar si hay más de 30 registros */}
                  {totalItems > 30 && (
                    <div className="px-3 lg:px-4 xl:px-6 py-4 lg:py-6 border-t border-gray-100 bg-gradient-to-r from-gray-50 to-gray-100">
                      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between space-y-3 sm:space-y-0">
                        {/* Información de página */}
                        <div className="flex items-center text-sm text-gray-700">
                          <span className="font-medium">
                            Mostrando {startIndex + 1} a {Math.min(endIndex, totalItems)} de {totalItems} registros
                          </span>
                        </div>
                        
                        {/* Controles de paginación */}
                        <div className="flex items-center space-x-2">
                          {/* Botón Anterior */}
                          <button
                            onClick={goToPreviousPage} aria-label="Página anterior"
                            disabled={currentPage === 1}
                            className={`px-3 py-2 text-sm font-medium rounded-lg border transition-colors duration-150 ${
                              currentPage === 1
                                ? 'bg-gray-100 text-gray-400 border-gray-200 cursor-not-allowed'
                                : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50 hover:border-gray-400'
                            }`}
                          >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                            </svg>
                          </button>
                          
                          {/* Números de página */}
                          <div className="flex items-center space-x-1">
                            {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                              let pageNum;
                              if (totalPages <= 5) {
                                pageNum = i + 1;
                              } else if (currentPage <= 3) {
                                pageNum = i + 1;
                              } else if (currentPage >= totalPages - 2) {
                                pageNum = totalPages - 4 + i;
                              } else {
                                pageNum = currentPage - 2 + i;
                              }
                              
                              return (
                                <button
                                  key={pageNum}
                                  onClick={() => goToPage(pageNum)}
                                  className={`px-3 py-2 text-sm font-medium rounded-lg border transition-colors duration-150 ${
                                    currentPage === pageNum
                                      ? 'bg-emerald-600 text-white border-emerald-600'
                                      : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50 hover:border-gray-400'
                                  }`}
                                >
                                  {pageNum}
                                </button>
                              );
                            })}
                          </div>
                          
                          {/* Botón Siguiente */}
                          <button
                            onClick={goToNextPage} aria-label="Página siguiente"
                            disabled={currentPage === totalPages}
                            className={`px-3 py-2 text-sm font-medium rounded-lg border transition-colors duration-150 ${
                              currentPage === totalPages
                                ? 'bg-gray-100 text-gray-400 border-gray-200 cursor-not-allowed'
                                : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50 hover:border-gray-400'
                            }`}
                          >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
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


      <TransitionOverlay show={showTransition} type={transitionType} message={transitionMessage} />
    </div>
  );
}

export default ElectricalDetails;