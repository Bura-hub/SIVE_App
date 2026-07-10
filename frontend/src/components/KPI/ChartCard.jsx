import React, { useRef, useState, useEffect } from 'react';
import { Line, Bar } from 'react-chartjs-2';

// Componente reutilizable que renderiza una tarjeta con un gráfico (línea o barras),
// permite resetear el zoom del gráfico y expandirlo a pantalla completa.
export function ChartCard({ 
  title, 
  description, 
  type = "line", 
  data, 
  options,
  height = "256px",
  fullscreenHeight = "600px",
  maxFullscreenHeight = "80vh"
}) {
  const chartRef = useRef(null);
  const fullscreenChartRef = useRef(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isZoomed, setIsZoomed] = useState(false);

  // Selección dinámica del tipo de gráfico: línea o barras
  const ChartComponent = type === "bar" ? Bar : Line;

  // Función para resetear el zoom del gráfico utilizando la referencia correcta
  const resetZoom = () => {
    const currentChartRef = isFullscreen ? fullscreenChartRef.current : chartRef.current;
    if (currentChartRef && currentChartRef.resetZoom) {
      currentChartRef.resetZoom();
    }
  };

  // Función para obtener la instancia del gráfico desde la referencia
  const getChartInstance = (ref) => {
    if (ref && ref.current) {
      // Para react-chartjs-2, necesitamos acceder a la instancia del gráfico
      return ref.current.chartInstance || ref.current;
    }
    return null;
  };

  // Función para resetear el zoom usando la instancia del gráfico
  const resetChartZoom = () => {
    const normalChart = getChartInstance(chartRef);
    const fullscreenChart = getChartInstance(fullscreenChartRef);
    
    // Intentar resetear el zoom usando diferentes métodos disponibles
    const resetZoomForChart = (chart) => {
      if (!chart) return;
      
      try {
        // Método 1: Usar resetZoom del plugin de zoom
        if (chart.resetZoom) {
          chart.resetZoom();
          return;
        }
        
        // Método 2: Usar resetZoom de la instancia del plugin
        if (chart.zoomScale) {
          chart.zoomScale('x', { min: null, max: null });
          chart.zoomScale('y', { min: null, max: null });
          return;
        }
        
        // Método 3: Usar update del gráfico para forzar el reset
        if (chart.update) {
          chart.update('none'); // Actualizar sin animación
          return;
        }
        
        // Método 4: Intentar acceder a través de la configuración del plugin
        if (chart.options && chart.options.plugins && chart.options.plugins.zoom) {
          const zoomPlugin = chart.options.plugins.zoom;
          if (zoomPlugin.zoom && zoomPlugin.zoom.wheel && zoomPlugin.zoom.wheel.enabled) {
            // Forzar el reset manualmente
            chart.scales.x.min = null;
            chart.scales.x.max = null;
            chart.scales.y.min = null;
            chart.scales.y.max = null;
            chart.update('none');
          }
        }
      } catch (error) {
        console.log('Error al resetear zoom:', error);
      }
    };
    
    resetZoomForChart(normalChart);
    resetZoomForChart(fullscreenChart);
  };

  // Efecto para sincronizar el zoom entre las dos vistas cuando se maximiza
  useEffect(() => {
    if (isFullscreen) {
      // Pequeño delay para asegurar que el gráfico maximizado esté renderizado
      const timer = setTimeout(() => {
        const normalChart = getChartInstance(chartRef);
        const fullscreenChart = getChartInstance(fullscreenChartRef);
        
        if (normalChart && fullscreenChart) {
          // Sincronizar el estado del zoom
          try {
            // Intentar obtener el nivel de zoom actual
            let currentZoom = null;
            
            // Método 1: Usar getZoomLevel si está disponible
            if (normalChart.getZoomLevel) {
              currentZoom = normalChart.getZoomLevel();
            }
            
            // Método 2: Usar las escalas actuales
            if (!currentZoom && normalChart.scales) {
              currentZoom = {
                x: { min: normalChart.scales.x.min, max: normalChart.scales.x.max },
                y: { min: normalChart.scales.y.min, max: normalChart.scales.y.max }
              };
            }
            
            // Aplicar el zoom al gráfico maximizado si hay zoom activo
            if (currentZoom && (currentZoom.x.min !== null || currentZoom.x.max !== null)) {
              if (fullscreenChart.zoomScale) {
                fullscreenChart.zoomScale('x', { 
                  min: currentZoom.x.min, 
                  max: currentZoom.x.max 
                });
                fullscreenChart.zoomScale('y', { 
                  min: currentZoom.y.min, 
                  max: currentZoom.y.max 
                });
              } else if (fullscreenChart.scales) {
                // Aplicar directamente a las escalas
                fullscreenChart.scales.x.min = currentZoom.x.min;
                fullscreenChart.scales.x.max = currentZoom.x.max;
                fullscreenChart.scales.y.min = currentZoom.y.min;
                fullscreenChart.scales.y.max = currentZoom.y.max;
                fullscreenChart.update('none');
              }
            }
          } catch (error) {
            // Si hay error al sincronizar, continuar sin problemas
            console.log('Zoom sync not available for this chart type:', error);
          }
        }
      }, 200); // Aumentar el delay para asegurar que el gráfico esté completamente renderizado
      
      return () => clearTimeout(timer);
    }
  }, [isFullscreen]);

  // Efecto para detectar cuando el zoom está activo
  useEffect(() => {
    const checkZoomStatus = () => {
      const normalChart = getChartInstance(chartRef);
      const fullscreenChart = getChartInstance(fullscreenChartRef);
      
      let hasZoom = false;
      
      if (normalChart && normalChart.scales) {
        const xScale = normalChart.scales.x;
        const yScale = normalChart.scales.y;
        hasZoom = (xScale.min !== null || xScale.max !== null || 
                   yScale.min !== null || yScale.max !== null);
      }
      
      if (!hasZoom && fullscreenChart && fullscreenChart.scales) {
        const xScale = fullscreenChart.scales.x;
        const yScale = fullscreenChart.scales.y;
        hasZoom = (xScale.min !== null || xScale.max !== null || 
                   yScale.min !== null || yScale.max !== null);
      }
      
      setIsZoomed(hasZoom);
    };
    
    // Verificar el estado del zoom cada 500ms
    const interval = setInterval(checkZoomStatus, 500);
    
    return () => clearInterval(interval);
  }, []);

  // Iconos SVG modernos
  const ResetIcon = () => (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
    </svg>
  );

  const MaximizeIcon = () => (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
    </svg>
  );

  const CloseIcon = () => (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
    </svg>
  );

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
          color: '#374151',
          font: {
            size: 11,
            weight: '500'
          },
          maxRotation: 45,
          minRotation: 0
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
          color: '#374151',
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

  return (
    <>
      {/* Contenedor principal de la tarjeta del gráfico */}
      <div className="bg-white rounded-2xl shadow-lg hover:shadow-xl transition duration-300 border border-gray-100 overflow-hidden group">
        {/* Header elegante con título y controles */}
        <div className="px-6 py-4 border-b border-gray-100 bg-gradient-to-r from-gray-50 to-white">
          <div className="flex items-center justify-between">
            <div className="flex-1">
              <h3 className="text-lg font-semibold text-gray-800 flex items-center">
                <div className="w-1.5 h-1.5 bg-gradient-to-r from-blue-500 to-purple-500 rounded-full mr-3"></div>
                {title}
              </h3>
              {description && (
                <p className="text-sm text-gray-600 mt-1 ml-6">
                  {description}
                </p>
              )}
            </div>
            
            {/* Botones de acciones con diseño mejorado */}
            <div className="flex items-center space-x-1 opacity-0 group-hover:opacity-100 transition duration-300">
              <button
                onClick={resetChartZoom}
                className={`p-2 rounded-lg transition duration-150 hover:scale-105 group/btn relative ${
                  isZoomed 
                    ? 'text-blue-600 bg-blue-50 hover:bg-blue-100' 
                    : 'text-gray-500 hover:text-blue-600 hover:bg-blue-50'
                }`}
                title="Resetear Zoom"
                disabled={!isZoomed}
              >
                <ResetIcon />
                <span className="absolute -bottom-8 left-1/2 transform -translate-x-1/2 bg-gray-800 text-white text-xs px-2 py-1 rounded opacity-0 group-hover/btn:opacity-100 transition-opacity duration-150 whitespace-nowrap z-10">
                  {isZoomed ? 'Resetear Zoom' : 'Sin Zoom'}
                </span>
                {/* Indicador de zoom activo */}
                {isZoomed && (
                  <div className="absolute -top-1 -right-1 w-3 h-3 bg-blue-500 rounded-full border-2 border-white"></div>
                )}
              </button>
              <button
                onClick={() => setIsFullscreen(true)}
                className="p-2 text-gray-500 hover:text-green-600 hover:bg-green-50 rounded-lg transition duration-150 hover:scale-105 group/btn relative"
                title="Maximizar"
              >
                <MaximizeIcon />
                <span className="absolute -bottom-8 left-1/2 transform -translate-x-1/2 bg-gray-800 text-white text-xs px-2 py-1 rounded opacity-0 group-hover/btn:opacity-100 transition-opacity duration-150 whitespace-nowrap z-10">
                  Maximizar
                </span>
              </button>
            </div>
          </div>
        </div>

        {/* Contenedor del gráfico con padding y altura definida */}
        <div className="p-6">
          <div className="chart-container relative w-full" style={{ height: height }}>
            <ChartComponent ref={chartRef} data={data} options={chartOptions} aria-label={title} />
            
            {/* Overlay sutil para indicar interactividad */}
            <div className="absolute inset-0 bg-gradient-to-br from-transparent via-transparent to-gray-50/20 pointer-events-none group-hover:to-gray-50/10 transition duration-300 rounded-lg"></div>
          </div>
        </div>

        {/* Indicador de interactividad en la parte inferior */}
        <div className="px-6 pb-4 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
          <div className="flex items-center justify-center text-xs text-gray-500 space-x-4">
            <span className="flex items-center">
              <svg className="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              Zoom con rueda
            </span>
            <span className="flex items-center">
              <svg className="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
              </svg>
              Arrastrar para mover
            </span>
            {!isZoomed && (
              <span className="flex items-center text-blue-500">
                <svg className="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                Usa zoom para reset
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Vista de gráfico en pantalla completa mejorada */}
      {isFullscreen && (
        <div className="fixed inset-0 bg-black bg-opacity-60 backdrop-blur-sm flex items-center justify-center z-[9999] p-2">
          <div className="bg-white rounded-3xl shadow-2xl w-11/12 h-5/6 max-w-7xl max-h-[95vh] relative overflow-hidden border border-gray-100">
            {/* Header del modal con diseño elegante similar a ProfileSettings */}
            <div className="flex items-center justify-between p-8 border-b border-gray-100 bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50">
              <div className="space-y-2">
                <h2 className="text-3xl font-bold bg-gradient-to-r from-slate-800 to-blue-700 bg-clip-text text-transparent">
                  {title}
                </h2>
                {description && (
                  <p className="text-slate-600 text-lg">{description}</p>
                )}
                <p className="text-slate-500 text-sm">Vista ampliada del gráfico con controles avanzados</p>
              </div>
              
              {/* Controles del modal */}
              <div className="flex items-center space-x-3">
                <button
                  onClick={resetChartZoom}
                  className={`p-3 rounded-xl transition duration-150 hover:scale-105 relative ${
                    isZoomed 
                      ? 'text-white bg-gradient-to-r from-blue-500 to-indigo-600 hover:from-blue-600 hover:to-indigo-700 shadow-lg shadow-blue-500/25' 
                      : 'text-slate-400 bg-slate-100 hover:bg-slate-200 cursor-not-allowed'
                  }`}
                  title="Resetear Zoom"
                  disabled={!isZoomed}
                >
                  <ResetIcon />
                  {/* Indicador de zoom activo */}
                  {isZoomed && (
                    <div className="absolute -top-1 -right-1 w-3 h-3 bg-emerald-400 rounded-full border-2 border-white animate-pulse"></div>
                  )}
                </button>
                <button
                  onClick={() => setIsFullscreen(false)}
                  className="p-3 text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition duration-150 rounded-xl hover:scale-105"
                  title="Cerrar"
                >
                  <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>

            {/* Contenido principal del modal */}
            <div className="flex h-[calc(100%-200px)]">
              {/* Área del gráfico */}
              <div className="flex-1 p-8 overflow-hidden bg-gradient-to-br from-white to-slate-50/30">
                <div className="h-full w-full">
                  <div className="chart-container w-full h-full" style={{ height: fullscreenHeight, maxHeight: maxFullscreenHeight }}>
                    <ChartComponent ref={fullscreenChartRef} data={data} options={chartOptions} aria-label={title} />
                  </div>
                </div>
              </div>

              {/* Panel lateral con controles e información */}
              <div className="w-80 bg-gradient-to-b from-slate-50 to-blue-50 border-l border-slate-200 p-6">
                <div className="space-y-6">
                  {/* Información del gráfico */}
                  <div className="space-y-4">
                    <h3 className="text-xl font-semibold text-slate-800 flex items-center">
                      <div className="w-3 h-3 bg-gradient-to-r from-blue-400 to-purple-400 rounded-full mr-3"></div>
                      Controles del Gráfico
                    </h3>
                    
                    {/* Controles de zoom */}
                    <div className="space-y-3">
                      <div className="bg-white rounded-2xl p-4 border border-slate-200 shadow-sm">
                        <h4 className="font-semibold text-slate-700 mb-3 flex items-center">
                          <svg className="w-5 h-5 text-blue-500 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                          </svg>
                          Zoom y Navegación
                        </h4>
                        <div className="space-y-2 text-sm text-slate-600">
                          <div className="flex items-center">
                            <div className="w-2 h-2 bg-blue-400 rounded-full mr-2"></div>
                            <span>Rueda del mouse para zoom</span>
                          </div>
                          <div className="flex items-center">
                            <div className="w-2 h-2 bg-purple-400 rounded-full mr-2"></div>
                            <span>Ctrl + arrastrar para mover</span>
                          </div>
                          <div className="flex items-center">
                            <div className="w-2 h-2 bg-emerald-400 rounded-full mr-2"></div>
                            <span>Arrastrar para zoom en área</span>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Estado del zoom */}
                    <div className="bg-white rounded-2xl p-4 border border-slate-200 shadow-sm">
                      <h4 className="font-semibold text-slate-700 mb-3 flex items-center">
                        <svg className="w-5 h-5 text-emerald-500 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        Estado del Zoom
                      </h4>
                      <div className={`flex items-center justify-between p-3 rounded-xl ${
                        isZoomed 
                          ? 'bg-emerald-50 border border-emerald-200' 
                          : 'bg-slate-50 border border-slate-200'
                      }`}>
                        <span className={`font-medium ${isZoomed ? 'text-emerald-700' : 'text-slate-600'}`}>
                          {isZoomed ? 'Zoom Activo' : 'Sin Zoom'}
                        </span>
                        <div className={`w-3 h-3 rounded-full ${isZoomed ? 'bg-emerald-400' : 'bg-slate-400'}`}></div>
                      </div>
                    </div>

                    {/* Acciones rápidas */}
                    <div className="bg-white rounded-2xl p-4 border border-slate-200 shadow-sm">
                      <h4 className="font-semibold text-slate-700 mb-3 flex items-center">
                        <svg className="w-5 h-5 text-indigo-500 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                        </svg>
                        Acciones Rápidas
                      </h4>
                      <div className="space-y-2">
                        <button
                          onClick={resetChartZoom}
                          disabled={!isZoomed}
                          className={`w-full py-2 px-4 rounded-xl text-sm font-medium transition duration-150 ${
                            isZoomed
                              ? 'bg-gradient-to-r from-blue-500 to-indigo-600 text-white hover:from-blue-600 hover:to-indigo-700 shadow-md hover:shadow-lg transform hover:scale-105'
                              : 'bg-slate-100 text-slate-400 cursor-not-allowed'
                          }`}
                        >
                          Resetear Vista
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Indicador de controles en la parte inferior */}
            <div className="absolute bottom-4 left-1/2 transform -translate-x-1/2 bg-black/60 text-white px-6 py-3 rounded-full text-sm backdrop-blur-sm border border-white/10">
              <div className="flex items-center space-x-8">
                <span className="flex items-center">
                  <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                  Zoom con rueda del mouse
                </span>
                <span className="flex items-center">
                  <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
                  </svg>
                  Arrastrar para mover
                </span>
                {!isZoomed && (
                  <span className="flex items-center text-yellow-300">
                    <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    Usa zoom para activar reset
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}