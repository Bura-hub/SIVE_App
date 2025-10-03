import React, { useState, useEffect } from 'react';
import { KpiCard } from "./KPI/KpiCard";
import { ChartCard } from "./KPI/ChartCard";
import TransitionOverlay from './TransitionOverlay';
import { buildApiUrl, getDefaultFetchOptions } from '../utils/apiConfig';

// Componente para datos externos de energía - Integración XM
const ExternalEnergyData = () => {
  const [loading, setLoading] = useState(true);
  const [energyData, setEnergyData] = useState(null);
  const [priceHistory, setPriceHistory] = useState([]);
  const [savingsData, setSavingsData] = useState(null);
  const [error, setError] = useState(null);
  const [xmApiStatus, setXmApiStatus] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);

  // Estados para las diferentes secciones
  const [activeSection, setActiveSection] = useState('overview');
  const [dateRange, setDateRange] = useState('month');
  const [dataSource, setDataSource] = useState('xm'); // 'xm' o 'error'

  useEffect(() => {
    fetchExternalEnergyData();
  }, [dateRange]);

  const fetchExternalEnergyData = async () => {
    try {
      setLoading(true);
      const authToken = localStorage.getItem('authToken');
      
      if (!authToken) {
        throw new Error('No hay token de autenticación');
      }

      const options = getDefaultFetchOptions(authToken);
      
      // Obtener datos de precios de energía desde XM
      const pricesResponse = await fetch(
        buildApiUrl('/api/external-energy/prices/', { range: dateRange }),
        options
      );
      
      if (!pricesResponse.ok) {
        throw new Error('Error al obtener precios de energía');
      }
      
      const pricesData = await pricesResponse.json();
      
      // Obtener datos de ahorro calculado
      const savingsResponse = await fetch(
        buildApiUrl('/api/external-energy/savings/', { range: dateRange }),
        options
      );
      
      if (!savingsResponse.ok) {
        throw new Error('Error al obtener datos de ahorro');
      }
      
      const savingsData = await savingsResponse.json();
      
      // Obtener datos de generación desde XM
      const generationResponse = await fetch(
        buildApiUrl('/api/external-energy/generation/', { range: dateRange }),
        options
      );
      
      let generationData = null;
      if (generationResponse.ok) {
        generationData = await generationResponse.json();
      }
      
      // Obtener datos de demanda desde XM
      const demandResponse = await fetch(
        buildApiUrl('/api/external-energy/demand/', { range: dateRange }),
        options
      );
      
      let demandData = null;
      if (demandResponse.ok) {
        demandData = await demandResponse.json();
      }
      
      // Obtener datos de emisiones desde XM
      const emissionsResponse = await fetch(
        buildApiUrl('/api/external-energy/emissions/', { range: dateRange }),
        options
      );
      
      let emissionsData = null;
      if (emissionsResponse.ok) {
        emissionsData = await emissionsResponse.json();
      }
      
      // Obtener datos de exportaciones desde XM
      const exportsResponse = await fetch(
        buildApiUrl('/api/external-energy/exports/', { range: dateRange }),
        options
      );
      
      let exportsData = null;
      if (exportsResponse.ok) {
        exportsData = await exportsResponse.json();
      }
      
      // Obtener datos de importaciones desde XM
      const importsResponse = await fetch(
        buildApiUrl('/api/external-energy/imports/', { range: dateRange }),
        options
      );
      
      let importsData = null;
      if (importsResponse.ok) {
        importsData = await importsResponse.json();
      }
      
      // Combinar todos los datos
      const combinedData = {
        ...pricesData,
        generation: generationData,
        demand: demandData,
        emissions: emissionsData,
        exports: exportsData,
        imports: importsData
      };
      
      // Determinar fuente de datos y estado de la API
      const isXmData = pricesData.source === 'XM' || generationData?.source === 'XM';
      setDataSource(isXmData ? 'xm' : 'error');
      setXmApiStatus({
        connected: isXmData,
        lastSync: new Date().toISOString(),
        dataPoints: {
          prices: pricesData.price_history?.length || 0,
          generation: generationData?.generation_history?.length || 0,
          demand: demandData?.demand_history?.length || 0,
          emissions: emissionsData?.emissions_history?.length || 0
        }
      });
      
      setEnergyData(combinedData);
      setPriceHistory(pricesData.price_history || []);
      setSavingsData(savingsData);
      setLastUpdate(new Date());
      setError(null);
      
    } catch (err) {
      console.error('Error fetching external energy data:', err);
      setError(err.message);
      setXmApiStatus({
        connected: false,
        error: err.message,
        lastSync: null,
        dataPoints: { prices: 0, generation: 0, demand: 0, emissions: 0 }
      });
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (value) => {
    if (value === null || value === undefined || isNaN(value)) {
      return 'N/A';
    }
    return new Intl.NumberFormat('es-CO', {
      style: 'currency',
      currency: 'COP',
      minimumFractionDigits: 2
    }).format(value);
  };

  const formatEnergy = (value) => {
    if (value === null || value === undefined || isNaN(value)) {
      return 'N/A';
    }
    return `${Number(value).toFixed(2)} kWh`;
  };

  const calculateSavingsPercentage = (generated, consumed, price) => {
    if (consumed === 0 || !generated || !consumed || !price) return 0;
    const savings = (generated * price) / (consumed * price) * 100;
    return Math.min(savings, 100);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-100 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-16 w-16 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600 text-lg font-medium">Conectando con XM...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-100 p-6">
        <div className="max-w-4xl mx-auto">
          <div className="bg-white/80 backdrop-blur-sm rounded-2xl shadow-2xl border border-red-200/50 p-8">
            <div className="flex items-center space-x-4 mb-6">
              <div className="flex-shrink-0">
                <div className="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center">
                  <svg className="h-6 w-6 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z" />
                  </svg>
                </div>
              </div>
              <div>
                <h3 className="text-xl font-semibold text-gray-900">Error de Conexión XM</h3>
                <p className="text-gray-600 mt-1">No se pudo conectar con el Sistema Interconectado Nacional</p>
              </div>
            </div>
            <div className="bg-red-50 rounded-xl p-6 border border-red-100 mb-6">
              <p className="text-red-800 font-medium">{error}</p>
            </div>
            <div className="flex space-x-4">
              <button
                onClick={fetchExternalEnergyData}
                className="bg-gradient-to-r from-red-500 to-red-600 text-white px-6 py-3 rounded-xl font-medium hover:from-red-600 hover:to-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 transition-all duration-200 shadow-lg hover:shadow-xl transform hover:-translate-y-0.5"
              >
                🔄 Reintentar Conexión
              </button>
              <button
                onClick={() => window.location.reload()}
                className="bg-gray-100 text-gray-700 px-6 py-3 rounded-xl font-medium hover:bg-gray-200 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 transition-all duration-200"
              >
                🔄 Recargar Página
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header con banner profesional */}
      <header className="bg-gradient-to-r from-blue-600 to-indigo-700 shadow-lg -mx-4 -mt-4">
        <div className="px-6 py-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <div className="p-3 bg-white/20 rounded-xl">
                <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                </div>
                <div>
                <h1 className="text-4xl font-bold text-white">Datos Energéticos Externos</h1>
                <p className="text-blue-100 mt-1">Integración con Sistema Interconectado Nacional (XM)</p>
                  </div>
                </div>
            
            {/* Estado de conexión XM */}
            <div className="flex flex-col items-end space-y-2">
              <div className={`inline-flex items-center px-4 py-2 rounded-lg text-sm font-medium ${
                xmApiStatus?.connected 
                  ? 'bg-green-500/20 text-green-100 border border-green-400/30' 
                  : 'bg-red-500/20 text-red-100 border border-red-400/30'
              }`}>
                <div className={`w-2 h-2 rounded-full mr-2 ${
                  xmApiStatus?.connected ? 'bg-green-400' : 'bg-red-400'
                }`}></div>
                {xmApiStatus?.connected ? 'XM Conectado' : 'XM Desconectado'}
              </div>
              {lastUpdate && (
                <p className="text-blue-200 text-xs">
                  Última actualización: {lastUpdate.toLocaleTimeString()}
                </p>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Panel de control superpuesto */}
      <section className="-mt-6 mb-6">
        <div className="bg-white/90 backdrop-blur-sm rounded-2xl shadow-xl border border-white/20 overflow-hidden relative">
          <div className="p-4">
            <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
              {/* Selector de período */}
              <div className="flex items-center space-x-4">
                <label className="text-sm font-medium text-gray-700">Período:</label>
                <div className="flex space-x-2">
                  {['week', 'month', 'quarter', 'year'].map((period) => (
                <button
                      key={period}
                      onClick={() => setDateRange(period)}
                      className={`px-4 py-2 text-sm font-medium rounded-lg transition-all duration-200 ${
                        dateRange === period
                          ? 'bg-blue-600 text-white shadow-md'
                          : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                      }`}
                    >
                      {period === 'week' && 'Semana'}
                      {period === 'month' && 'Mes'}
                      {period === 'quarter' && 'Trimestre'}
                      {period === 'year' && 'Año'}
                </button>
              ))}
                </div>
              </div>

              {/* Botón de actualización */}
              <button
                onClick={fetchExternalEnergyData}
                disabled={loading}
                className="inline-flex items-center px-6 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent mr-2"></div>
                    Actualizando...
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                    Actualizar Datos
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* Selector de sección */}
      <section className="mb-6">
        <div className="bg-white rounded-2xl shadow-lg border border-gray-200 p-4">
          <div className="flex items-center justify-center space-x-4">
            {[
              { key: 'overview', label: 'Resumen General', icon: (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
              )},
              { key: 'market', label: 'Datos de Mercado', icon: (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1" />
                </svg>
              )},
              { key: 'environment', label: 'Análisis Ambiental', icon: (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              )}
            ].map((section) => (
              <button
                key={section.key}
                onClick={() => setActiveSection(section.key)}
                className={`flex items-center space-x-2 px-6 py-3 rounded-lg font-medium transition-all duration-200 ${
                  activeSection === section.key
                    ? 'bg-blue-600 text-white shadow-md'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                {section.icon}
                <span>{section.label}</span>
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* KPIs principales */}
      <section className="mb-6">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* KPI: Precio Promedio */}
          <div className="bg-white rounded-2xl shadow-lg border border-gray-200 p-4 hover:shadow-xl transition-shadow duration-300">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600 mb-1">Precio Promedio</p>
                <p className="text-2xl font-bold text-gray-900">
                  {energyData?.average_price ? `${Number(energyData.average_price).toFixed(2)}` : '0.00'}
                </p>
                <p className="text-sm text-gray-500">COP/kWh</p>
              </div>
              <div className="p-3 bg-blue-100 rounded-xl">
                <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1" />
                </svg>
              </div>
            </div>
            <div className="mt-4 flex items-center">
              <div className={`w-2 h-2 rounded-full mr-2 ${
                dataSource === 'xm' ? 'bg-green-500' : 'bg-yellow-500'
              }`}></div>
              <span className="text-xs text-gray-500">
                {dataSource === 'xm' ? 'Datos XM' : 'Error de conexión'}
              </span>
            </div>
          </div>
          
          {/* KPI: Exportaciones */}
          <div className="bg-white rounded-2xl shadow-lg border border-gray-200 p-4 hover:shadow-xl transition-shadow duration-300">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600 mb-1">Exportaciones</p>
                <p className="text-2xl font-bold text-gray-900">
                  {energyData?.exports?.average_exports ? `${(energyData.exports.average_exports / 1000).toFixed(1)}K` : '0.0K'}
                </p>
                <p className="text-sm text-gray-500">MWh</p>
              </div>
              <div className="p-3 bg-blue-100 rounded-xl">
                <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16l-4-4m0 0l4-4m-4 4h18" />
                </svg>
              </div>
            </div>
            <div className="mt-4 flex items-center">
              <div className={`w-2 h-2 rounded-full mr-2 ${
                dataSource === 'xm' ? 'bg-green-500' : 'bg-yellow-500'
              }`}></div>
              <span className="text-xs text-gray-500">
                {dataSource === 'xm' ? 'Datos XM' : 'Error de conexión'}
              </span>
            </div>
          </div>
          
          {/* KPI: Importaciones */}
          <div className="bg-white rounded-2xl shadow-lg border border-gray-200 p-4 hover:shadow-xl transition-shadow duration-300">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600 mb-1">Importaciones</p>
                <p className="text-2xl font-bold text-gray-900">
                  {energyData?.imports?.average_imports ? `${(energyData.imports.average_imports / 1000).toFixed(1)}K` : '0.0K'}
                </p>
                <p className="text-sm text-gray-500">MWh</p>
              </div>
              <div className="p-3 bg-orange-100 rounded-xl">
                <svg className="w-6 h-6 text-orange-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 8l4 4m0 0l-4 4m4-4H3" />
                </svg>
              </div>
            </div>
            <div className="mt-4 flex items-center">
              <div className={`w-2 h-2 rounded-full mr-2 ${
                dataSource === 'xm' ? 'bg-green-500' : 'bg-yellow-500'
              }`}></div>
              <span className="text-xs text-gray-500">
                {dataSource === 'xm' ? 'Datos XM' : 'Error de conexión'}
              </span>
            </div>
          </div>
          
          {/* KPI: Generación Promedio */}
          <div className="bg-white rounded-2xl shadow-lg border border-gray-200 p-4 hover:shadow-xl transition-shadow duration-300">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600 mb-1">Generación Promedio</p>
                <p className="text-2xl font-bold text-gray-900">
                  {energyData?.generation?.average_generation ? `${(energyData.generation.average_generation / 1000000).toFixed(1)}M` : '0.0M'}
                </p>
                <p className="text-sm text-gray-500">MW</p>
              </div>
              <div className="p-3 bg-purple-100 rounded-xl">
                <svg className="w-6 h-6 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
            </div>
            <div className="mt-4 flex items-center">
              <div className={`w-2 h-2 rounded-full mr-2 ${
                dataSource === 'xm' ? 'bg-green-500' : 'bg-yellow-500'
              }`}></div>
              <span className="text-xs text-gray-500">
                {dataSource === 'xm' ? 'Datos XM' : 'Error de conexión'}
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* Contenido dinámico basado en la sección seleccionada */}
      <div className="space-y-6">
        {/* Sección de Resumen */}
        {activeSection === 'overview' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Gráfico de precios */}
            <div className="bg-white rounded-2xl shadow-lg border border-gray-200 p-4">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-xl font-semibold text-gray-900 flex items-center">
                  <svg className="w-6 h-6 text-blue-600 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1" />
                  </svg>
                  Precios de Energía
                </h3>
                <div className={`px-3 py-1 rounded-full text-xs font-medium ${
                  dataSource === 'xm' 
                    ? 'bg-green-100 text-green-800' 
                    : 'bg-yellow-100 text-yellow-800'
                }`}>
                  {dataSource === 'xm' ? 'Datos XM' : 'Error de conexión'}
          </div>
        </div>
                <ChartCard
                  title=""
                  type="line"
                  data={{
                    labels: priceHistory.map(item => item.date),
                    datasets: [{
                      label: 'Precio COP/kWh',
                      data: priceHistory.map(item => item.price),
                      borderColor: 'rgb(59, 130, 246)',
                      backgroundColor: 'rgba(59, 130, 246, 0.1)',
                      tension: 0.4,
                      borderWidth: 3,
                      pointBackgroundColor: 'rgb(59, 130, 246)',
                      pointBorderColor: '#ffffff',
                      pointBorderWidth: 2,
                      pointRadius: 4,
                      pointHoverRadius: 6
                    }]
                  }}
                  options={{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                      legend: {
                        display: false
                      }
                    },
                    scales: {
                      y: {
                        beginAtZero: true,
                        title: {
                          display: true,
                          text: 'Precio (COP/kWh)',
                          font: {
                            size: 12,
                            weight: '600'
                          }
                        }
                      }
                    }
                  }}
                />
              </div>
              
            {/* Resumen de datos XM */}
            <div className="bg-white rounded-2xl shadow-lg border border-gray-200 p-4">
                <h3 className="text-xl font-semibold text-gray-900 mb-4 flex items-center">
                <svg className="w-6 h-6 text-indigo-600 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
                Estado de Integración XM
                </h3>
                <div className="space-y-4">
                  <div className="flex items-center justify-between p-4 bg-gray-50 rounded-xl">
                    <span className="text-gray-700 font-medium">Estado de conexión:</span>
                    <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                      xmApiStatus?.connected 
                        ? 'bg-green-100 text-green-800' 
                        : 'bg-red-100 text-red-800'
                    }`}>
                      {xmApiStatus?.connected ? 'Conectado' : 'Desconectado'}
                    </span>
                  </div>
                  <div className="flex items-center justify-between p-4 bg-gray-50 rounded-xl">
                    <span className="text-gray-700 font-medium">Última sincronización:</span>
                    <span className="text-gray-900 font-medium">
                      {lastUpdate ? lastUpdate.toLocaleString() : 'N/A'}
                    </span>
                  </div>
                  <div className="flex items-center justify-between p-4 bg-gray-50 rounded-xl">
                    <span className="text-gray-700 font-medium">Total de datos:</span>
                    <span className="text-gray-900 font-medium">
                      {Object.values(xmApiStatus?.dataPoints || {}).reduce((a, b) => a + b, 0)} registros
                    </span>
                  </div>
                  <div className="flex items-center justify-between p-4 bg-gray-50 rounded-xl">
                    <span className="text-gray-700 font-medium">Fuente actual:</span>
                    <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                      dataSource === 'xm' 
                        ? 'bg-green-100 text-green-800' 
                        : 'bg-yellow-100 text-yellow-800'
                    }`}>
                      {dataSource === 'xm' ? 'API XM' : 'Error de conexión'}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}

        {/* Sección de Mercado */}
        {activeSection === 'market' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Generación */}
            {energyData?.generation && (
              <div className="bg-white rounded-2xl shadow-lg border border-gray-200 p-4">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-xl font-semibold text-gray-900 flex items-center">
                    <svg className="w-6 h-6 text-purple-600 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                    Generación Nacional
                  </h3>
                  <div className={`px-3 py-1 rounded-full text-xs font-medium ${
                    dataSource === 'xm' 
                      ? 'bg-green-100 text-green-800' 
                      : 'bg-yellow-100 text-yellow-800'
                  }`}>
                    {dataSource === 'xm' ? 'Datos XM' : 'Error de conexión'}
                  </div>
                </div>
                <ChartCard
                    title=""
                    type="line"
                  data={{
                      labels: energyData.generation.generation_history?.map(item => item.date) || [],
                    datasets: [{
                        label: 'Generación (MW)',
                        data: energyData.generation.generation_history?.map(item => item.value) || [],
                        borderColor: 'rgb(234, 179, 8)',
                        backgroundColor: 'rgba(234, 179, 8, 0.1)',
                        tension: 0.4,
                        borderWidth: 3,
                        pointBackgroundColor: 'rgb(234, 179, 8)',
                        pointBorderColor: '#ffffff',
                        pointBorderWidth: 2,
                        pointRadius: 4,
                        pointHoverRadius: 6
                    }]
                  }}
                  options={{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                      legend: {
                        display: false
                      }
                    },
                    scales: {
                      y: {
                        beginAtZero: true,
                        title: {
                          display: true,
                            text: 'Generación (MW)',
                          font: {
                              size: 12,
                            weight: '600'
                            }
                        }
                      }
                    }
                  }}
                />
              </div>
              )}

            {/* Demanda */}
            {energyData?.demand && (
              <div className="bg-white rounded-2xl shadow-lg border border-gray-200 p-4">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-xl font-semibold text-gray-900 flex items-center">
                    <svg className="w-6 h-6 text-indigo-600 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                    </svg>
                    Demanda Nacional
                </h3>
                  <div className={`px-3 py-1 rounded-full text-xs font-medium ${
                    dataSource === 'xm' 
                      ? 'bg-green-100 text-green-800' 
                      : 'bg-yellow-100 text-yellow-800'
                  }`}>
                    {dataSource === 'xm' ? 'Datos XM' : 'Error de conexión'}
                  </div>
                </div>
                <ChartCard
                    title=""
                    type="line"
                  data={{
                      labels: energyData.demand.demand_history?.map(item => item.date) || [],
                    datasets: [{
                        label: 'Demanda (MW)',
                        data: energyData.demand.demand_history?.map(item => item.value) || [],
                        borderColor: 'rgb(249, 115, 22)',
                        backgroundColor: 'rgba(249, 115, 22, 0.1)',
                        tension: 0.4,
                      borderWidth: 3,
                        pointBackgroundColor: 'rgb(249, 115, 22)',
                        pointBorderColor: '#ffffff',
                        pointBorderWidth: 2,
                        pointRadius: 4,
                        pointHoverRadius: 6
                    }]
                  }}
                  options={{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                      legend: {
                          display: false
                        }
                      },
                      scales: {
                        y: {
                          beginAtZero: true,
                          title: {
                            display: true,
                            text: 'Demanda (MW)',
                          font: {
                              size: 12,
                            weight: '600'
                            }
                        }
                      }
                    }
                  }}
                />
                </div>
              )}
            </div>
          )}

        {/* Sección Ambiental */}
        {activeSection === 'environment' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Emisiones */}
            {energyData?.emissions && (
              <div className="bg-white rounded-2xl shadow-lg border border-gray-200 p-4">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-xl font-semibold text-gray-900 flex items-center">
                    <svg className="w-6 h-6 text-orange-600 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    Factor de Emisión CO₂
                  </h3>
                  <div className={`px-3 py-1 rounded-full text-xs font-medium ${
                    dataSource === 'xm' 
                      ? 'bg-green-100 text-green-800' 
                      : 'bg-yellow-100 text-yellow-800'
                  }`}>
                    {dataSource === 'xm' ? 'Datos XM' : 'Error de conexión'}
                  </div>
                </div>
                <ChartCard
                    title=""
                  type="line"
                  data={{
                      labels: energyData.emissions.emissions_history?.map(item => item.date) || [],
                    datasets: [{
                        label: 'Factor de Emisión (gCO₂e/kWh)',
                        data: energyData.emissions.emissions_history?.map(item => item.value) || [],
                        borderColor: 'rgb(16, 185, 129)',
                        backgroundColor: 'rgba(16, 185, 129, 0.1)',
                      tension: 0.4,
                      borderWidth: 3,
                        pointBackgroundColor: 'rgb(16, 185, 129)',
                      pointBorderColor: '#ffffff',
                      pointBorderWidth: 2,
                        pointRadius: 4,
                        pointHoverRadius: 6
                    }]
                  }}
                  options={{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                      legend: {
                        display: false
                      }
                    },
                    scales: {
                      y: {
                        beginAtZero: true,
                        title: {
                          display: true,
                            text: 'Factor de Emisión (gCO₂e/kWh)',
                          font: {
                              size: 12,
                            weight: '600'
                            }
                          }
                        }
                      }
                    }}
                  />
                </div>
              )}

            {/* Gráfico de Exportaciones e Importaciones */}
            {energyData?.exports && energyData?.imports && (
              <div className="bg-white rounded-2xl shadow-lg border border-gray-200 p-4">
                <h3 className="text-xl font-semibold text-gray-900 mb-4 flex items-center">
                  <svg className="w-6 h-6 text-blue-600 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
                  </svg>
                  Comercio Internacional de Energía
                </h3>
                <ChartCard
                  title=""
                  type="line"
                  data={{
                    labels: energyData.exports.exports_history?.map(item => item.date) || [],
                    datasets: [
                      {
                        label: 'Exportaciones (MWh)',
                        data: energyData.exports.exports_history?.map(item => item.value) || [],
                        borderColor: 'rgb(59, 130, 246)',
                        backgroundColor: 'rgba(59, 130, 246, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.4
                      },
                      {
                        label: 'Importaciones (MWh)',
                        data: energyData.imports.imports_history?.map(item => item.value) || [],
                        borderColor: 'rgb(249, 115, 22)',
                        backgroundColor: 'rgba(249, 115, 22, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.4
                      }
                    ]
                  }}
                  options={{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                      legend: {
                        display: true,
                        position: 'top'
                      }
                    },
                    scales: {
                      y: {
                        beginAtZero: true,
                        ticks: {
                          callback: function(value) {
                            return value + ' MWh';
                          }
                        }
                      }
                    },
                    interaction: {
                      intersect: false,
                      mode: 'index'
                    }
                  }}
                />
              </div>
          )}
            </div>
          )}
      </div>
    </div>
  );
};

export default ExternalEnergyData;