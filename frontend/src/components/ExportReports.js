// Importaciones necesarias de React y componentes personalizados
import React, { useState, useEffect, useRef } from 'react';
import TransitionOverlay from './TransitionOverlay';
import RangeCalendar from './filters/RangeCalendar';
import { formatDateForAPI, monthInputToStartDate, monthInputToEndDate, dateStringToMonthInput } from '../utils/dateUtils';
import { ENDPOINTS, buildApiUrl, getDefaultFetchOptions, handleApiResponse, fetchWithAuth } from '../utils/apiConfig';
import { IconFileDown, IconDownload } from './icons';

// Límite de sondeos de estado por reporte (cada 2-5 s → ~5-12 min máximo)
const MAX_STATUS_CHECKS = 150;

function ExportReports({ authToken, onLogout, username, isSuperuser, navigateTo, isSidebarMinimized, setIsSidebarMinimized }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [exportProgress, setExportProgress] = useState(0);
  const [reportProgress, setReportProgress] = useState({}); // Progreso individual por reporte
 
  // Estados para datos de la API
  const [institutions, setInstitutions] = useState([]);
  const [electricMeters, setElectricMeters] = useState([]);
  const [inverters, setInverters] = useState([]);
  const [weatherStations, setWeatherStations] = useState([]);
  const [deviceCategories, setDeviceCategories] = useState([]);

  // Estados para el formulario de generación de reportes
  const [selectedInstitution, setSelectedInstitution] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('');
  const [selectedDevices, setSelectedDevices] = useState([]);
  const [reportType, setReportType] = useState('');
  const [timeRange, setTimeRange] = useState('daily');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [exportFormat, setExportFormat] = useState('CSV');

  // Estados para la animación de transición
  const [showTransition, setShowTransition] = useState(false);
  const [transitionType, setTransitionType] = useState('info');
  const [transitionMessage, setTransitionMessage] = useState('');

  // Estados para reportes previos
  const [previousExports, setPreviousExports] = useState([]);
  const [loadingExports, setLoadingExports] = useState(false);
  
  // Estados para paginación
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const [pageSize, setPageSize] = useState(5);

  // Refs para el monitoreo de reportes: timeouts y peticiones en curso por task_id,
  // para poder cancelarlos al desmontar el componente y evitar fugas
  const monitorTimeoutsRef = useRef({});
  const monitorControllersRef = useRef({});

  // Cancelar polling y peticiones pendientes al desmontar
  useEffect(() => {
    const timeouts = monitorTimeoutsRef.current;
    const controllers = monitorControllersRef.current;
    return () => {
      Object.values(timeouts).forEach(clearTimeout);
      Object.values(controllers).forEach(controller => controller.abort());
    };
  }, []);

  // Definir categorías de dispositivos disponibles
  const availableCategories = [
    { id: 'electricMeter', name: 'Medidores Eléctricos', description: 'Reportes de consumo, demanda y calidad eléctrica' },
    { id: 'inverter', name: 'Inversores', description: 'Reportes de generación, eficiencia y rendimiento fotovoltaico' },
    { id: 'weatherStation', name: 'Estaciones Meteorológicas', description: 'Reportes climáticos y condiciones ambientales' }
  ];

  // Definir tipos de reportes por categoría
  const reportTypesByCategory = {
    electricMeter: [
      { id: 'consumption_summary', name: 'Resumen de Consumo', description: 'Consumo energético total y por períodos' },
      { id: 'demand_analysis', name: 'Análisis de Demanda', description: 'Demanda pico, promedio y factor de carga' },
      { id: 'power_quality', name: 'Calidad de Potencia', description: 'THD, factor de potencia y desbalance' },
      { id: 'energy_balance', name: 'Balance Energético', description: 'Energía importada vs exportada' },
      { id: 'comprehensive', name: 'Reporte Integral', description: 'Todos los indicadores eléctricos' }
    ],
    inverter: [
      { id: 'generation_summary', name: 'Resumen de Generación', description: 'Energía total generada y eficiencia' },
      { id: 'performance_analysis', name: 'Análisis de Rendimiento', description: 'Performance Ratio y curvas de generación' },
      { id: 'operational_metrics', name: 'Métricas Operativas', description: 'Factor de potencia y estabilidad' },
      { id: 'anomaly_report', name: 'Reporte de Anomalías', description: 'Detección y análisis de anomalías' },
      { id: 'comprehensive', name: 'Reporte Integral', description: 'Todos los indicadores de inversores' }
    ],
    weatherStation: [
      { id: 'climate_summary', name: 'Resumen Climático', description: 'Temperatura, humedad y precipitación' },
      { id: 'solar_analysis', name: 'Análisis Solar', description: 'Irradiancia y horas solares pico' },
      { id: 'wind_analysis', name: 'Análisis de Viento', description: 'Velocidad y dirección del viento' },
      { id: 'environmental_impact', name: 'Impacto Ambiental', description: 'Condiciones para generación fotovoltaica' },
      { id: 'comprehensive', name: 'Reporte Integral', description: 'Todos los indicadores meteorológicos' }
    ]
  };

  // Inicializar fechas con valores por defecto en zona horaria de Colombia
  useEffect(() => {
    const today = new Date();
    const firstDayOfMonth = new Date(today.getFullYear(), today.getMonth(), 1);
    
    setStartDate(formatDateForAPI(firstDayOfMonth));
    setEndDate(formatDateForAPI(today));
  }, []);

  // Cargar datos iniciales
  useEffect(() => {
    if (!authToken) return;
    const controller = new AbortController();
    setLoading(true);
    // Simular un pequeño delay para mostrar la animación
    const timer = setTimeout(() => {
      loadInstitutions(controller.signal);
      loadPreviousExports(1, pageSize, controller.signal);
      setLoading(false);
    }, 300);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
    // Las funciones de carga se recrean en cada render; incluirlas en deps provocaría recargas infinitas
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authToken]);

  // Cargar dispositivos cuando cambie la institución o categoría
  useEffect(() => {
    if (selectedInstitution && selectedCategory) {
      // AbortController por ejecución del efecto: evita condiciones de carrera
      // con respuestas fuera de orden al cambiar rápido de institución/categoría
      const controller = new AbortController();
      loadDevices(controller.signal);
      return () => controller.abort();
    } else {
      setElectricMeters([]);
      setInverters([]);
      setWeatherStations([]);
    }
    // loadDevices se recrea en cada render; incluirla en deps provocaría recargas infinitas
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedInstitution, selectedCategory, authToken]);

  // Cargar instituciones disponibles
  const loadInstitutions = async (signal = null) => {
    try {
      const data = await fetchWithAuth(buildApiUrl(ENDPOINTS.electrical.institutions), {
        ...getDefaultFetchOptions(authToken),
        signal
      });
      setInstitutions(data);
    } catch (error) {
      // Ignorar cancelaciones y errores de sesión (fetchWithAuth ya redirige en 401)
      if (error.name === 'AbortError' || error.isAuthError) return;
      console.error('Error cargando instituciones:', error);
      setError('Error al cargar instituciones');
    }
  };

  // Cargar dispositivos según la categoría seleccionada
  const loadDevices = async (signal = null) => {
    if (!selectedInstitution || !selectedCategory) return;

    try {
      let endpoint;
      let setterFunction;

      switch (selectedCategory) {
        case 'electricMeter':
          endpoint = ENDPOINTS.electrical.devices;
          setterFunction = setElectricMeters;
          break;
        case 'inverter':
          endpoint = ENDPOINTS.inverters.list;
          setterFunction = setInverters;
          break;
        case 'weatherStation':
          endpoint = ENDPOINTS.weather.stations;
          setterFunction = setWeatherStations;
          break;
        default:
          return;
      }

      const data = await fetchWithAuth(buildApiUrl(endpoint, { institution_id: selectedInstitution }), {
        ...getDefaultFetchOptions(authToken),
        signal
      });

      // Adaptar la respuesta según el endpoint
      if (selectedCategory === 'weatherStation') {
        setterFunction(data.results || []);
      } else {
        setterFunction(data.devices || []);
      }
    } catch (error) {
      // Ignorar respuestas obsoletas canceladas y errores de sesión
      if (error.name === 'AbortError' || error.isAuthError) return;
      console.error('Error cargando dispositivos:', error);
      setError('Error al cargar dispositivos');
    }
  };

  // Cargar reportes previos con paginación
  const loadPreviousExports = async (page = 1, size = pageSize, signal = null) => {
    setLoadingExports(true);
    try {
      // Llamada real a la API para obtener historial de reportes con paginación
      const url = `${buildApiUrl(ENDPOINTS.reports.history)}?page=${page}&page_size=${size}`;
      const data = await fetchWithAuth(url, {
        ...getDefaultFetchOptions(authToken),
        signal
      });

      // Actualizar estados de paginación
      setCurrentPage(data.current_page || 1);
      setTotalPages(data.total_pages || 1);
      setTotalCount(data.count || 0);
      setPageSize(data.page_size || 5);
      
      // Transformar datos de la API al formato esperado por el componente
      const transformedExports = data.results.map(report => ({
        id: report.id,
        type: report.report_type,
        category: report.category === 'electricMeter' ? 'Medidores Eléctricos' :
                  report.category === 'inverter' ? 'Inversores' :
                  report.category === 'weatherStation' ? 'Estaciones Meteorológicas' : report.category,
        institution: report.institution_name,
        date: new Date(report.created_at).toLocaleString('es-CO'),
        format: report.format,
        status: report.status === 'completed' ? 'Completado' :
                report.status === 'failed' ? 'Fallido' :
                report.status === 'processing' ? 'Procesando' : 'Pendiente',
        fileSize: report.file_size || 'N/A',
        recordCount: report.record_count || 0
      }));
      
      setPreviousExports(transformedExports);

    } catch (error) {
      // Ignorar cancelaciones y errores de sesión (fetchWithAuth ya redirige en 401)
      if (error.name === 'AbortError' || error.isAuthError) return;
      console.error('Error cargando reportes previos:', error);
      // En caso de error, mostrar lista vacía
      setPreviousExports([]);
    } finally {
      setLoadingExports(false);
    }
  };

  // Validar formulario antes de exportar
  const validateForm = () => {
    if (!selectedInstitution) {
      setError('Debe seleccionar una institución');
      return false;
    }
    if (!selectedCategory) {
      setError('Debe seleccionar una categoría de dispositivo');
      return false;
    }
    if (selectedDevices.length === 0) {
      setError('Debe seleccionar al menos un dispositivo');
      return false;
    }
    if (!reportType) {
      setError('Debe seleccionar un tipo de reporte');
      return false;
    }
    if (!startDate || !endDate) {
      setError('Debe especificar fechas de inicio y fin');
      return false;
    }
    if (new Date(startDate) > new Date(endDate)) {
      setError('La fecha de inicio no puede ser posterior a la fecha de fin');
      return false;
    }
    return true;
  };

  // Funciones de paginación
  const handlePageChange = (newPage) => {
    if (newPage >= 1 && newPage <= totalPages) {
      setCurrentPage(newPage);
      loadPreviousExports(newPage, pageSize);
    }
  };

  const handlePageSizeChange = (newSize) => {
    setPageSize(newSize);
    setCurrentPage(1); // Volver a la primera página
    loadPreviousExports(1, newSize);
  };

  // Generar y exportar reporte
  const handleExport = async () => {
    if (!validateForm()) return;

    setLoading(true);
    setExportProgress(0);
    setError(null);
    
    // Mostrar progreso inicial rápido
    setExportProgress(25);
    setTimeout(() => setExportProgress(50), 100);
    setTimeout(() => setExportProgress(75), 200);
    setTimeout(() => setExportProgress(90), 300);

    try {
      // Llamada real a la API para generar reporte (fetchWithAuth maneja 401 y errores)
      const result = await fetchWithAuth(buildApiUrl(ENDPOINTS.reports.generate), {
        method: 'POST',
        ...getDefaultFetchOptions(authToken),
        body: JSON.stringify({
          institution_id: parseInt(selectedInstitution),
          category: selectedCategory,
          devices: selectedDevices,
          report_type: reportType,
          time_range: timeRange,
          start_date: startDate,
          end_date: endDate,
          format: exportFormat
        })
      });

      if (result.success) {
        // Mostrar mensaje de éxito
        showTransitionAnimation('success', `Generación de reporte iniciada exitosamente! El reporte se generará en segundo plano.`, 4000);
        
        // Ocultar el loader inmediatamente después del éxito
        setLoading(false);
        setExportProgress(0);
        
        // Iniciar monitoreo del estado en segundo plano
        monitorReportStatus(result.task_id);
        
        // Agregar a la lista de reportes previos
        const newExport = {
          id: result.task_id,
          type: reportType,
          category: availableCategories.find(cat => cat.id === selectedCategory)?.name,
          institution: institutions.find(inst => inst.id.toString() === selectedInstitution)?.name,
          date: new Date().toLocaleString('es-CO'),
          format: exportFormat,
          status: 'Pendiente',
          fileSize: 'Generando...',
          recordCount: 0
        };
        setPreviousExports(prev => [newExport, ...prev]);
      } else {
        throw new Error(result.message || 'Error desconocido');
      }

    } catch (error) {
      console.error('Error en la exportación:', error);
      if (!error.isAuthError) {
        setError(error.message || 'Error al generar el reporte');
      }
      setLoading(false);
      setExportProgress(0);
    }
  };

  // Monitorear el estado de generación del reporte
  const monitorReportStatus = async (taskId) => {
    let attempts = 0;

    // Programar el siguiente sondeo guardando el timeout para poder limpiarlo al desmontar
    const scheduleNextCheck = (delay) => {
      monitorTimeoutsRef.current[taskId] = setTimeout(checkStatus, delay);
    };

    const stopMonitoring = () => {
      if (monitorTimeoutsRef.current[taskId]) {
        clearTimeout(monitorTimeoutsRef.current[taskId]);
        delete monitorTimeoutsRef.current[taskId];
      }
    };

    const checkStatus = async () => {
      attempts += 1;
      if (attempts > MAX_STATUS_CHECKS) {
        // Límite de reintentos alcanzado: detener el polling para evitar peticiones eternas
        stopMonitoring();
        showTransitionAnimation('warning', 'El monitoreo del reporte excedió el tiempo de espera. Actualice el historial para consultar su estado.', 4000);
        return;
      }

      const controller = new AbortController();
      monitorControllersRef.current[taskId] = controller;

      try {
        const statusInfo = await fetchWithAuth(buildApiUrl(ENDPOINTS.reports.status, { task_id: taskId }), {
          ...getDefaultFetchOptions(authToken),
          signal: controller.signal
        });

        // Actualizar progreso individual del reporte
        setReportProgress(prev => ({
          ...prev,
          [taskId]: statusInfo.progress
        }));

        if (statusInfo.status === 'completed') {
          // Reporte completado
          stopMonitoring();
          setReportProgress(prev => ({
            ...prev,
            [taskId]: 100
          }));

          // Descargar archivo automáticamente
          downloadReport(taskId);

          // Actualizar estado en la lista
          setPreviousExports(prev => prev.map(exp =>
            exp.id === taskId
              ? { ...exp, status: 'Completado', fileSize: 'Descargando...', recordCount: statusInfo.record_count || 0 }
              : exp
          ));

          showTransitionAnimation('success', `Reporte "${reportType}" generado exitosamente!`, 3000);

        } else if (statusInfo.status === 'failed') {
          // Reporte falló
          stopMonitoring();
          setReportProgress(prev => ({
            ...prev,
            [taskId]: 0
          }));
          setError(`Error al generar reporte: ${statusInfo.error}`);

          // Actualizar estado en la lista
          setPreviousExports(prev => prev.map(exp =>
            exp.id === taskId
              ? { ...exp, status: 'Fallido', fileSize: 'Error', recordCount: 0 }
              : exp
          ));

        } else if (statusInfo.status === 'processing') {
          // Reporte en proceso, continuar monitoreando
          scheduleNextCheck(2000);
        }

      } catch (error) {
        // Detener el monitoreo si la petición fue cancelada (desmontaje) o la sesión expiró
        if (error.name === 'AbortError' || error.isAuthError) {
          stopMonitoring();
          return;
        }
        console.error('Error monitoreando estado:', error);
        // Reintentar en 5 segundos (cuenta para el límite de reintentos)
        scheduleNextCheck(5000);
      } finally {
        delete monitorControllersRef.current[taskId];
      }
    };

    // Iniciar monitoreo
    checkStatus();
  };

  // Función para obtener la extensión correcta del archivo según el formato
  const getFileExtension = (format) => {
    switch (format) {
      case 'CSV':
        return 'csv';
      case 'PDF':
        return 'pdf';
      case 'Excel':
        return 'xlsx';
      default:
        return format.toLowerCase();
    }
  };

  // Descargar reporte generado
  const downloadReport = async (taskId) => {
    try {
      const response = await fetch(buildApiUrl(ENDPOINTS.reports.download, { task_id: taskId }), {
        ...getDefaultFetchOptions(authToken)
      });

      if (!response.ok) {
        // Manejar el 401 (limpieza de token y redirección) y demás errores ANTES de leer el blob;
        // handleApiResponse siempre lanza en respuestas no exitosas
        await handleApiResponse(response);
        return;
      }

      // Crear blob y descargar
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `reporte_${reportType.replace(/ /g, '_')}_${startDate}_${endDate}.${getFileExtension(exportFormat)}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      
      // Actualizar estado en la lista
      setPreviousExports(prev => prev.map(exp => 
        exp.id === taskId 
          ? { ...exp, fileSize: `${(blob.size / 1024 / 1024).toFixed(1)} MB` }
          : exp
      ));
      
    } catch (error) {
      // Si la sesión expiró, handleApiResponse ya redirigió al login
      if (error.isAuthError) return;
      console.error('Error descargando reporte:', error);
      setError('Error al descargar el reporte generado');
    }
  };

  // Función para mostrar transición
  const showTransitionAnimation = (type = 'info', message = '', duration = 2000) => {
    setTransitionType(type);
    setTransitionMessage(message);
    setShowTransition(true);
    
    setTimeout(() => {
      setShowTransition(false);
    }, duration);
  };

  // Limpiar selección de dispositivos cuando cambie la categoría
  const handleCategoryChange = (categoryId) => {
    setSelectedCategory(categoryId);
    setSelectedDevices([]);
    setReportType('');
  };

  // Obtener dispositivos disponibles según la categoría
  const getAvailableDevices = () => {
    switch (selectedCategory) {
      case 'electricMeter':
        return electricMeters;
      case 'inverter':
        return inverters;
      case 'weatherStation':
        return weatherStations;
      default:
        return [];
    }
  };

  // Obtener tipos de reporte disponibles según la categoría
  const getAvailableReportTypes = () => {
    return reportTypesByCategory[selectedCategory] || [];
  };

  // Regenerar reporte
  const regenerateReport = async (exportItem) => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchWithAuth(buildApiUrl(ENDPOINTS.reports.generate), {
        method: 'POST',
        ...getDefaultFetchOptions(authToken),
        body: JSON.stringify({
          // Regenerar con los parámetros ORIGINALES del reporte (los expone el
          // historial); si faltara alguno, caer a la selección actual.
          institution_id: exportItem.institution_id ?? parseInt(selectedInstitution),
          category: exportItem.category,
          devices: (exportItem.devices && exportItem.devices.length) ? exportItem.devices : selectedDevices,
          report_type: exportItem.type,
          time_range: exportItem.time_range ?? timeRange,
          start_date: exportItem.start_date ?? startDate,
          end_date: exportItem.end_date ?? endDate,
          format: exportItem.format ?? exportFormat
        })
      });

      if (result.success) {
        showTransitionAnimation('success', `Generación de reporte iniciada exitosamente!`, 3000);
        monitorReportStatus(result.task_id);
        const newExport = {
          id: result.task_id,
          type: exportItem.type,
          category: exportItem.category,
          institution: exportItem.institution,
          date: new Date().toLocaleString('es-CO'),
          format: exportFormat,
          status: 'Pendiente',
          fileSize: 'Generando...',
          recordCount: 0
        };
        setPreviousExports(prev => [newExport, ...prev]);
      } else {
        throw new Error(result.message || 'Error desconocido');
      }
    } catch (error) {
      console.error('Error al regenerar reporte:', error);
      if (!error.isAuthError) {
        setError(error.message || 'Error al regenerar el reporte');
      }
    } finally {
      // Liberar siempre la UI, tanto en éxito como en error
      setLoading(false);
    }
  };

  // Eliminar reporte
  const deleteReport = async (taskId) => {
    if (!window.confirm('¿Estás seguro de que quieres eliminar este reporte? Esta acción no se puede deshacer.')) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(buildApiUrl(ENDPOINTS.reports.delete, { task_id: taskId }), {
        method: 'DELETE',
        ...getDefaultFetchOptions(authToken)
      });

      if (!response.ok) {
        // handleApiResponse gestiona el 401 (limpieza y redirección) y lanza un error con el detalle
        await handleApiResponse(response);
        return;
      }

      setPreviousExports(prev => prev.filter(exp => exp.id !== taskId));
      showTransitionAnimation('success', 'Reporte eliminado exitosamente!');
    } catch (error) {
      console.error('Error al eliminar reporte:', error);
      if (!error.isAuthError) {
        setError(error.message || 'Error al eliminar el reporte');
      }
    } finally {
      // Liberar siempre la UI para que no quede bloqueada tras un fallo
      setLoading(false);
    }
  };

  // Si está cargando, muestra un spinner o mensaje
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-100">
        <div className="flex flex-col items-center">
          <div className="animate-spin rounded-full h-16 w-16 border-t-4 border-b-4 border-purple-500"></div>
          <p className="mt-4 text-lg text-gray-700">Cargando exportador de reportes...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-100">
      <header className="bg-gradient-to-r from-blue-700 to-purple-800 shadow-lg -mx-4 lg:-mx-8 -mt-4 lg:-mt-8">
        <div className="px-4 lg:px-8 py-8 lg:py-12">
          <div className="flex flex-col lg:flex-row lg:items-center space-y-4 lg:space-y-0 lg:space-x-4 pr-16 lg:pr-64">
            <div className="p-3 bg-white/20 rounded-xl self-start lg:self-auto">
              <IconFileDown className="w-6 h-6 lg:w-8 lg:h-8 text-white" />
            </div>
            <div>
              <h1 className="text-2xl lg:text-4xl font-bold text-white">Exportar Reportes</h1>
              <p className="text-blue-50 mt-1 text-sm lg:text-base">Genera reportes profesionales de todos tus dispositivos</p>
            </div>
          </div>
          
          {/* Badges informativos */}
          <div className="flex flex-col sm:flex-row items-start sm:items-center space-y-2 sm:space-y-0 sm:space-x-4 mt-4 lg:mt-6">
            {/* Aviso estático para el generador de reportes */}
            <div className="flex items-center bg-white/20 backdrop-blur-sm border border-white/30 text-white px-3 lg:px-4 py-2 rounded-full text-xs lg:text-sm font-medium w-full sm:w-auto justify-center lg:justify-start">
              <svg className="w-4 lg:w-5 h-4 lg:h-5 mr-2" fill="none" stroke="currentColor" strokeWidth="1.8" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <span className="hidden sm:inline">Generador Profesional</span>
              <span className="sm:hidden">Profesional</span>
            </div>
            
            {/* Aviso estático para formatos disponibles */}
            <div className="flex items-center bg-white/20 backdrop-blur-sm border border-white/30 text-white px-3 lg:px-4 py-2 rounded-full text-xs lg:text-sm font-medium w-full sm:w-auto justify-center lg:justify-start">
              <IconDownload className="w-4 lg:w-5 h-4 lg:h-5 mr-2" />
              <span className="hidden sm:inline">CSV (.csv) • PDF (.pdf) • Excel (.xlsx)</span>
              <span className="sm:hidden">Múltiples formatos</span>
            </div>
          </div>
        </div>
      </header>

      {/* Mensaje de error */}
      {error && (
        <div className="mx-4 lg:mx-8 mt-6 lg:mt-8 bg-red-50 border border-red-200 text-red-700 px-3 lg:px-4 py-2 lg:py-3 rounded-lg">
          <div className="flex items-center">
            <svg className="w-4 lg:w-5 h-4 lg:h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span className="text-sm lg:text-base">{error}</span>
          </div>
          <button 
            onClick={() => setError(null)}
            className="mt-2 text-red-600 hover:text-red-800 underline text-xs lg:text-sm"
          >
            Cerrar
          </button>
        </div>
      )}

      {/* Generate New Report Section - Superpuesto con el banner */}
      <section className="mx-4 lg:mx-8 bg-white/90 backdrop-blur-sm rounded-2xl shadow-xl border border-white/20 p-4 lg:p-8 -mt-4 lg:-mt-8">
        <h2 className="text-xl lg:text-2xl font-bold text-gray-800 mb-4 lg:mb-6 flex items-center">
          <svg className="w-6 lg:w-7 h-6 lg:h-7 mr-2 lg:mr-3 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
          </svg>
          Generar Nuevo Reporte
        </h2>

        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 lg:gap-8">
          {/* Columna izquierda - Filtros principales */}
          <div className="space-y-4 lg:space-y-6">
            {/* Institución */}
            <div>
              <label htmlFor="institution" className="block text-sm font-semibold text-gray-700 mb-2">
                Institución <span className="text-red-500">*</span>
              </label>
              <select
                id="institution"
                className="w-full px-3 lg:px-4 py-2 lg:py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors text-sm lg:text-base"
                value={selectedInstitution}
                onChange={(e) => {
                  setSelectedInstitution(e.target.value);
                  setSelectedCategory('');
                  setSelectedDevices([]);
                  setReportType('');
                }}
              >
                <option value="">Seleccionar institución</option>
                {institutions.map(inst => (
                  <option key={inst.id} value={inst.id}>{inst.name}</option>
                ))}
              </select>
            </div>

            {/* Categoría de Dispositivo */}
            <div>
              <label htmlFor="category" className="block text-sm font-semibold text-gray-700 mb-2">
                Categoría de Dispositivo <span className="text-red-500">*</span>
              </label>
              <select
                id="category"
                className="w-full px-3 lg:px-4 py-2 lg:py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors text-sm lg:text-base"
                value={selectedCategory}
                onChange={(e) => handleCategoryChange(e.target.value)}
                disabled={!selectedInstitution}
              >
                <option value="">Seleccionar categoría</option>
                {availableCategories.map(cat => (
                  <option key={cat.id} value={cat.id}>{cat.name}</option>
                ))}
              </select>
              {selectedCategory && (
                <p className="mt-2 text-xs lg:text-sm text-gray-600">
                  {availableCategories.find(cat => cat.id === selectedCategory)?.description}
                </p>
              )}
            </div>

            {/* Dispositivos */}
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-2">
                Dispositivos <span className="text-red-500">*</span>
              </label>
              <div className="max-h-32 lg:max-h-48 overflow-y-auto border border-gray-300 rounded-lg p-2 lg:p-3">
                {getAvailableDevices().length === 0 ? (
                  <p className="text-gray-500 text-xs lg:text-sm text-center py-3 lg:py-4">
                    {selectedCategory ? 'No hay dispositivos disponibles' : 'Seleccione una categoría primero'}
                  </p>
                ) : (
                  <div className="space-y-1 lg:space-y-2">
                    {getAvailableDevices().map(device => (
                      <label key={device.id || device.scada_id} className="flex items-center space-x-2 lg:space-x-3 cursor-pointer hover:bg-gray-50 p-1 lg:p-2 rounded">
                        <input
                          type="checkbox"
                          className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                          checked={selectedDevices.includes(device.id || device.scada_id)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSelectedDevices(prev => [...prev, device.id || device.scada_id]);
                            } else {
                              setSelectedDevices(prev => prev.filter(id => id !== (device.id || device.scada_id)));
                            }
                          }}
                        />
                        <span className="text-xs lg:text-sm text-gray-700">{device.name}</span>
                        {device.status && (
                          <span className={`px-1 lg:px-2 py-0.5 lg:py-1 text-xs rounded-full ${
                            device.status === 'active' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                          }`}>
                            {device.status}
                          </span>
                        )}
                      </label>
                    ))}
                  </div>
                )}
              </div>
              {selectedDevices.length > 0 && (
                <p className="mt-2 text-xs lg:text-sm text-gray-600">
                  {selectedDevices.length} dispositivo(s) seleccionado(s)
                </p>
              )}
            </div>
          </div>

          {/* Columna derecha - Configuración del reporte */}
          <div className="space-y-4 lg:space-y-6">
            {/* Tipo de Reporte */}
            <div>
              <label htmlFor="reportType" className="block text-sm font-semibold text-gray-700 mb-2">
                Tipo de Reporte <span className="text-red-500">*</span>
              </label>
              <select
                id="reportType"
                className="w-full px-3 lg:px-4 py-2 lg:py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors text-sm lg:text-base"
                value={reportType}
                onChange={(e) => setReportType(e.target.value)}
                disabled={!selectedCategory}
              >
                <option value="">Seleccionar tipo de reporte</option>
                {getAvailableReportTypes().map(type => (
                  <option key={type.id} value={type.name}>{type.name}</option>
                ))}
              </select>
              {reportType && (
                <p className="mt-2 text-xs lg:text-sm text-gray-600">
                  {getAvailableReportTypes().find(type => type.name === reportType)?.description}
                </p>
              )}
            </div>

            {/* Rango de Tiempo */}
            <div>
              <label htmlFor="timeRange" className="block text-sm font-semibold text-gray-700 mb-2">
                Rango de Tiempo
              </label>
              <select
                id="timeRange"
                className="w-full px-3 lg:px-4 py-2 lg:py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors text-sm lg:text-base"
                value={timeRange}
                onChange={(e) => {
                  const newRange = e.target.value;
                  setTimeRange(newRange);
                  // Al pasar a mensual, alinear las fechas internas a los límites del
                  // mes seleccionado para mantener la coherencia con el selector de meses.
                  if (newRange === 'monthly') {
                    setStartDate(prev => (prev ? monthInputToStartDate(dateStringToMonthInput(prev)) : prev));
                    setEndDate(prev => (prev ? monthInputToEndDate(dateStringToMonthInput(prev)) : prev));
                  }
                }}
              >
                <option value="daily">Diario</option>
                <option value="monthly">Mensual</option>
              </select>
            </div>

            {/* Fechas: selector de rango secuencial en español (inicio -> fin) */}
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-2">
                Rango de Fechas <span className="text-red-500">*</span>
              </label>
              {timeRange === 'monthly' ? (
                <RangeCalendar
                  mode="month"
                  startValue={startDate ? dateStringToMonthInput(startDate) : ''}
                  endValue={endDate ? dateStringToMonthInput(endDate) : ''}
                  onChange={(s, e) => {
                    setStartDate(s ? monthInputToStartDate(s) : '');
                    setEndDate(e ? monthInputToEndDate(e) : '');
                  }}
                  accentColor="green"
                />
              ) : (
                <RangeCalendar
                  mode="day"
                  startValue={startDate}
                  endValue={endDate}
                  onChange={(s, e) => {
                    setStartDate(s);
                    setEndDate(e);
                  }}
                  accentColor="green"
                />
              )}
            </div>

            {/* Formato de Exportación */}
            <div>
              <label htmlFor="exportFormat" className="block text-sm font-semibold text-gray-700 mb-2">
                Formato de Exportación
              </label>
              <div className="grid grid-cols-3 gap-2 lg:gap-3">
                {['CSV', 'PDF', 'Excel'].map(format => (
                  <label key={format} className="flex items-center justify-center p-2 lg:p-3 border border-gray-300 rounded-lg cursor-pointer hover:bg-gray-50 transition-colors">
                    <input
                      type="radio"
                      name="exportFormat"
                      value={format}
                      checked={exportFormat === format}
                      onChange={(e) => setExportFormat(e.target.value)}
                      className="sr-only"
                    />
                    <div className={`text-center ${exportFormat === format ? 'text-blue-600' : 'text-gray-600'}`}>
                      <div className={`text-sm lg:text-lg font-semibold ${exportFormat === format ? 'text-blue-600' : 'text-gray-600'}`}>
                        {format}
                      </div>
                      <div className="text-xs text-gray-500 hidden sm:block">
                        {format === 'CSV' ? 'Datos tabulares (.csv)' : format === 'PDF' ? 'Documento (.pdf)' : 'Hoja de cálculo (.xlsx)'}
                      </div>
                    </div>
                  </label>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Barra de progreso - Solo se muestra brevemente durante la generación inicial */}
        {loading && exportProgress > 0 && exportProgress < 100 && (
          <div className="mt-4 lg:mt-6">
            <div className="flex items-center justify-between text-xs lg:text-sm text-gray-600 mb-2">
              <span>Iniciando generación de reporte...</span>
              <span>{exportProgress}%</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div 
                className="bg-blue-600 h-2 rounded-full transition duration-300 ease-out"
                style={{ width: `${exportProgress}%` }}
              ></div>
            </div>
            <div className="text-xs text-gray-500 mt-2 text-center">
              El reporte se generará en segundo plano. Puedes continuar trabajando mientras se procesa.
            </div>
          </div>
        )}

        {/* Botón de Exportación */}
        <div className="mt-6 lg:mt-8 flex justify-center">
          <button
            onClick={handleExport}
            disabled={loading || !selectedInstitution || !selectedCategory || selectedDevices.length === 0 || !reportType}
            className="w-full sm:w-auto px-6 lg:px-8 py-3 lg:py-4 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-lg hover:from-blue-700 hover:to-purple-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition transform hover:scale-105 font-semibold text-base lg:text-lg shadow-lg"
          >
            {loading ? (
              <div className="flex items-center justify-center">
                <svg className="animate-spin -ml-1 mr-2 lg:mr-3 h-4 lg:h-5 w-4 lg:w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <span className="hidden sm:inline">Generando Reporte...</span>
                <span className="sm:hidden">Generando...</span>
              </div>
            ) : (
              <div className="flex items-center justify-center">
                <svg className="w-4 lg:w-5 h-4 lg:h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                <span className="hidden sm:inline">Generar y Exportar Reporte</span>
                <span className="sm:hidden">Generar Reporte</span>
              </div>
            )}
          </button>
        </div>
      </section>

      {/* Previous Exports Section */}
      <section className="mx-4 lg:mx-8 mt-8 lg:mt-12 bg-white p-4 lg:p-8 rounded-xl shadow-lg border border-gray-200">
        <h2 className="text-xl lg:text-2xl font-bold text-gray-800 mb-4 lg:mb-6 flex items-center">
          <svg className="w-6 lg:w-7 h-6 lg:h-7 mr-2 lg:mr-3 text-gray-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          Reportes Generados
        </h2>
        
        {/* Mensaje informativo sobre el nuevo comportamiento */}
        <div className="mb-4 lg:mb-6 p-3 lg:p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <div className="flex items-start">
            <svg className="w-5 h-5 text-blue-600 mt-0.5 mr-2 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div className="text-sm text-blue-800">
              <p className="font-medium">Generación en segundo plano</p>
              <p className="text-xs mt-1">Los reportes se generan automáticamente en segundo plano. Puedes continuar trabajando mientras se procesan. El progreso se muestra en la columna "Estado".</p>
            </div>
          </div>
        </div>
        
        {loadingExports ? (
          <div className="flex justify-center py-6 lg:py-8">
            <div role="status" className="animate-spin rounded-full h-6 lg:h-8 w-6 lg:w-8 border-b-2 border-blue-600"></div>
          </div>
        ) : (
          <div className="overflow-x-auto">
            {/* Tabla responsiva con scroll horizontal en móviles */}
            <div className="min-w-full">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th scope="col" className="px-3 lg:px-6 py-2 lg:py-3 text-left text-xs font-bold uppercase tracking-wider text-gray-700">
                      <span className="hidden sm:inline">Tipo de Reporte</span>
                      <span className="sm:hidden">Tipo</span>
                    </th>
                    <th scope="col" className="px-3 lg:px-6 py-2 lg:py-3 text-left text-xs font-bold uppercase tracking-wider text-gray-700">
                      <span className="hidden md:inline">Categoría</span>
                      <span className="md:hidden">Cat.</span>
                    </th>
                    <th scope="col" className="px-3 lg:px-6 py-2 lg:py-3 text-left text-xs font-bold uppercase tracking-wider text-gray-700">
                      <span className="hidden lg:inline">Institución</span>
                      <span className="lg:hidden">Inst.</span>
                    </th>
                    <th scope="col" className="px-3 lg:px-6 py-2 lg:py-3 text-left text-xs font-bold uppercase tracking-wider text-gray-700">
                      Fecha
                    </th>
                    <th scope="col" className="px-3 lg:px-6 py-2 lg:py-3 text-left text-xs font-bold uppercase tracking-wider text-gray-700">
                      <span className="hidden sm:inline">Formato</span>
                      <span className="sm:hidden">Fmt</span>
                    </th>
                    <th scope="col" className="px-3 lg:px-6 py-2 lg:py-3 text-left text-xs font-bold uppercase tracking-wider text-gray-700">
                      Estado
                    </th>
                    <th scope="col" className="px-3 lg:px-6 py-2 lg:py-3 text-left text-xs font-bold uppercase tracking-wider text-gray-700">
                      <span className="hidden lg:inline">Detalles</span>
                      <span className="lg:hidden">Det.</span>
                    </th>
                    <th scope="col" className="px-3 lg:px-6 py-2 lg:py-3 text-left text-xs font-bold uppercase tracking-wider text-gray-700">
                      Acciones
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {previousExports.map((exportItem) => (
                    <tr key={exportItem.id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-3 lg:px-6 py-3 lg:py-4 whitespace-nowrap">
                        <div className="text-xs lg:text-sm font-medium text-gray-900">{exportItem.type}</div>
                      </td>
                      <td className="px-3 lg:px-6 py-3 lg:py-4 whitespace-nowrap">
                        <div className="text-xs lg:text-sm text-gray-700">{exportItem.category}</div>
                      </td>
                      <td className="px-3 lg:px-6 py-3 lg:py-4 whitespace-nowrap">
                        <div className="text-xs lg:text-sm text-gray-700">{exportItem.institution}</div>
                      </td>
                      <td className="px-3 lg:px-6 py-3 lg:py-4 whitespace-nowrap">
                        <div className="text-xs lg:text-sm text-gray-500">{exportItem.date}</div>
                      </td>
                      <td className="px-3 lg:px-6 py-3 lg:py-4 whitespace-nowrap">
                        <span className={`px-2 lg:px-3 py-1 inline-flex text-xs leading-5 font-semibold rounded-full ${
                          exportItem.format === 'CSV' ? 'bg-green-100 text-green-800' :
                          exportItem.format === 'PDF' ? 'bg-red-100 text-red-800' :
                          'bg-blue-100 text-blue-800'
                        }`}>
                          {exportItem.format}
                        </span>
                      </td>
                      <td className="px-3 lg:px-6 py-3 lg:py-4 whitespace-nowrap">
                        <div className="flex flex-col space-y-1">
                          <span className={`px-2 lg:px-3 py-1 inline-flex text-xs leading-5 font-semibold rounded-full ${
                            exportItem.status === 'Completado' ? 'bg-green-100 text-green-800' : 
                            exportItem.status === 'Fallido' ? 'bg-red-100 text-red-800' : 'bg-orange-100 text-orange-800'
                          }`}>
                            {exportItem.status}
                          </span>
                          {/* Mostrar barra de progreso para reportes en proceso */}
                          {exportItem.status === 'Pendiente' && reportProgress[exportItem.id] !== undefined && (
                            <div className="w-full bg-gray-200 rounded-full h-1.5">
                              <div 
                                className="bg-blue-600 h-1.5 rounded-full transition duration-300 ease-out"
                                style={{ width: `${reportProgress[exportItem.id]}%` }}
                              ></div>
                            </div>
                          )}
                        </div>
                      </td>
                      <td className="px-3 lg:px-6 py-3 lg:py-4 whitespace-nowrap text-xs lg:text-sm text-gray-500">
                        <div>{exportItem.fileSize}</div>
                        <div>{exportItem.recordCount.toLocaleString('es-CO')} registros</div>
                      </td>
                      <td className="px-3 lg:px-6 py-3 lg:py-4 whitespace-nowrap text-xs lg:text-sm font-medium">
                        <div className="flex space-x-1 lg:space-x-2">
                          <button 
                            className="text-blue-600 hover:text-blue-900 transition-colors p-1 rounded hover:bg-blue-50"
                            title="Descargar"
                            onClick={() => downloadReport(exportItem.id)}
                            disabled={exportItem.status !== 'Completado'}
                          >
                            <IconDownload className="w-3 lg:w-4 h-3 lg:h-4" />
                          </button>
                          <button 
                            className="text-purple-600 hover:text-purple-900 transition-colors p-1 rounded hover:bg-purple-50"
                            title="Regenerar"
                            onClick={() => regenerateReport(exportItem)}
                          >
                            <svg className="w-3 lg:w-4 h-3 lg:h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                            </svg>
                          </button>
                          <button 
                            className="text-red-600 hover:text-red-900 transition-colors p-1 rounded hover:bg-red-50"
                            title="Eliminar"
                            onClick={() => deleteReport(exportItem.id)}
                          >
                            <svg className="w-3 lg:w-4 h-3 lg:h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            
            {/* Controles de Paginación */}
            {totalCount > 0 && (
              <div className="mt-4 lg:mt-6 flex flex-col lg:flex-row items-start lg:items-center justify-between space-y-4 lg:space-y-0">
                {/* Información de paginación */}
                <div className="text-xs lg:text-sm text-gray-700">
                  Mostrando <span className="font-medium">{((currentPage - 1) * pageSize) + 1}</span> a{' '}
                  <span className="font-medium">
                    {Math.min(currentPage * pageSize, totalCount)}
                  </span> de{' '}
                  <span className="font-medium">{totalCount}</span> reportes
                </div>
                
                {/* Controles de navegación */}
                <div className="flex flex-col sm:flex-row items-start sm:items-center space-y-3 sm:space-y-0 sm:space-x-4 w-full lg:w-auto">
                  {/* Selector de tamaño de página */}
                  <div className="flex items-center space-x-2">
                    <label className="text-xs lg:text-sm text-gray-700">Mostrar:</label>
                    <select
                      value={pageSize}
                      onChange={(e) => handlePageSizeChange(parseInt(e.target.value))}
                      className="border border-gray-300 rounded-md px-2 py-1 text-xs lg:text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      <option value={5}>5</option>
                      <option value={10}>10</option>
                      <option value={20}>20</option>
                      <option value={50}>50</option>
                    </select>
                    <span className="text-xs lg:text-sm text-gray-700">por página</span>
                  </div>
                  
                  {/* Botones de navegación */}
                  <div className="flex items-center space-x-1">
                    <button
                      onClick={() => handlePageChange(1)}
                      disabled={currentPage === 1}
                      className="px-2 lg:px-3 py-1 text-xs lg:text-sm border border-gray-300 rounded-md disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
                      title="Primera página"
                    >
                      <svg className="w-3 lg:w-4 h-3 lg:h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
                      </svg>
                    </button>
                    
                    <button
                      onClick={() => handlePageChange(currentPage - 1)}
                      disabled={currentPage === 1}
                      className="px-2 lg:px-3 py-1 text-xs lg:text-sm border border-gray-300 rounded-md disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
                      title="Página anterior"
                    >
                      <svg className="w-3 lg:w-4 h-3 lg:h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                      </svg>
                    </button>
                    
                    {/* Indicador de página actual */}
                    <span className="px-2 lg:px-3 py-1 text-xs lg:text-sm text-gray-700 border border-gray-300 rounded-md bg-gray-50">
                      <span className="hidden sm:inline">Página {currentPage} de {totalPages}</span>
                      <span className="sm:hidden">{currentPage}/{totalPages}</span>
                    </span>
                    
                    <button
                      onClick={() => handlePageChange(currentPage + 1)}
                      disabled={currentPage === totalPages}
                      className="px-2 lg:px-3 py-1 text-xs lg:text-sm border border-gray-300 rounded-md disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
                      title="Página siguiente"
                    >
                      <svg className="w-3 lg:w-4 h-3 lg:h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                      </svg>
                    </button>
                    
                    <button
                      onClick={() => handlePageChange(totalPages)}
                      disabled={currentPage === totalPages}
                      className="px-2 lg:px-3 py-1 text-xs lg:text-sm border border-gray-300 rounded-md disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
                      title="Última página"
                    >
                      <svg className="w-3 lg:w-4 h-3 lg:h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 5l7 7-7 7" />
                      </svg>
                    </button>
                  </div>
                </div>
              </div>
            )}
            
            {previousExports.length === 0 && (
              <div className="text-center py-8 lg:py-12 text-gray-500">
                <svg className="mx-auto h-8 lg:h-12 w-8 lg:w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                <h3 className="mt-2 text-sm lg:text-base font-medium text-gray-900">No hay reportes generados</h3>
                <p className="mt-1 text-xs lg:text-sm text-gray-500">Los reportes que generes aparecerán aquí.</p>
              </div>
            )}
          </div>
        )}
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

export default ExportReports;