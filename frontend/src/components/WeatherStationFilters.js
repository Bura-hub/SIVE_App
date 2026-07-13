import React, { useState, useEffect, useCallback } from 'react';
import { ENDPOINTS, getDefaultFetchOptions, buildApiUrl } from '../utils/apiConfig';

const WeatherStationFilters = ({ onFiltersChange, authToken }) => {
  const [timeRange, setTimeRange] = useState('daily');
  const [selectedInstitution, setSelectedInstitution] = useState('');
  const [selectedDevice, setSelectedDevice] = useState('');
  
  // Calcular fechas por defecto: 10 días atrás hasta hoy
  const getDefaultDates = () => {
    const endDate = new Date();
    const startDate = new Date();
    startDate.setDate(startDate.getDate() - 10);
    
    return {
      startDate: startDate.toISOString().split('T')[0],
      endDate: endDate.toISOString().split('T')[0]
    };
  };
  
  // Suma N días a una fecha en formato 'YYYY-MM-DD' y devuelve el mismo formato.
  const addDaysToDateString = (dateString, days) => {
    const date = new Date(`${dateString}T00:00:00`);
    date.setDate(date.getDate() + days);
    return date.toISOString().split('T')[0];
  };

  const defaultDates = getDefaultDates();
  const [startDate, setStartDate] = useState(defaultDates.startDate);
  const [endDate, setEndDate] = useState(defaultDates.endDate);

  const [institutions, setInstitutions] = useState([]);
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(false);

  const fetchInstitutions = useCallback(async () => {
    try {
      console.log('🔍 WeatherStationFilters - fetchInstitutions iniciando');
      // Usar el endpoint correcto para instituciones (compartido entre todas las categorías)
      const response = await fetch(buildApiUrl(ENDPOINTS.electrical.institutions), {
        ...getDefaultFetchOptions(authToken)
      });
      console.log('🔍 WeatherStationFilters - fetchInstitutions response status:', response.status);

      if (!response.ok) {
        throw new Error(`Error ${response.status}`);
      }
      const data = await response.json();
      console.log('🔍 WeatherStationFilters - fetchInstitutions data recibida:', data);

      // Espera formato: [{id, name}]
      const institutionsList = Array.isArray(data) ? data : (data.results || []);
      console.log('🔍 WeatherStationFilters - fetchInstitutions instituciones procesadas:', institutionsList);
      setInstitutions(institutionsList);
    } catch (error) {
      console.error('🔍 WeatherStationFilters - fetchInstitutions error:', error);
      setInstitutions([]);
    }
  }, [authToken]);

  const fetchDevices = useCallback(async (institutionId) => {
    setLoading(true);
    try {
      console.log('🔍 WeatherStationFilters - fetchDevices iniciando para institución:', institutionId);

      // Usar el endpoint específico para estaciones meteorológicas
      const url = buildApiUrl(ENDPOINTS.weather.stations, { institution_id: institutionId });

      const response = await fetch(url, {
        ...getDefaultFetchOptions(authToken)
      });
      console.log('🔍 WeatherStationFilters - fetchDevices response status:', response.status);
      console.log('🔍 WeatherStationFilters - fetchDevices response ok:', response.ok);

      if (!response.ok) {
        const errorText = await response.text();
        console.error('🔍 WeatherStationFilters - fetchDevices error response:', errorText);
        throw new Error(`Error ${response.status}: ${errorText}`);
      }

      const data = await response.json();
      console.log('🔍 WeatherStationFilters - fetchDevices data recibida:', data);

      // Espera formato: {count, results: [{id, name, institution, is_active}]}
      const devicesList = Array.isArray(data) ? data : (data.results || []);
      console.log('🔍 WeatherStationFilters - fetchDevices dispositivos procesados:', devicesList);

      setDevices(devicesList);

      // Reset device selection if current device is not in new list
      // (actualización funcional para no depender del estado selectedDevice)
      setSelectedDevice(prev => {
        if (prev && !devicesList.find(d => d.id === prev)) {
          console.log('🔍 WeatherStationFilters - fetchDevices reseteando device selection');
          return '';
        }
        return prev;
      });

    } catch (error) {
      console.error('🔍 WeatherStationFilters - fetchDevices error:', error);
      setDevices([]);
      setSelectedDevice('');
    } finally {
      setLoading(false);
    }
  }, [authToken]);

  // Cargar instituciones al montar el componente
  useEffect(() => {
    fetchInstitutions();
  }, [fetchInstitutions]);

  // Cargar dispositivos cuando cambie la institución
  useEffect(() => {
    if (selectedInstitution) {
      console.log('Institution changed, fetching devices for:', selectedInstitution);
      fetchDevices(selectedInstitution);
    } else {
      console.log('No institution selected, clearing devices');
      setDevices([]);
      setSelectedDevice(''); // Reset device selection when institution changes
    }
  }, [selectedInstitution, fetchDevices]);

  // Monitorear cambios en el estado de dispositivos
  useEffect(() => {
    console.log('Devices state changed:', devices);
    console.log('Devices count:', devices.length);
  }, [devices]);

  // Notificar cambios en los filtros
  useEffect(() => {
    console.log('🔍 WeatherStationFilters - useEffect filters changed:', { timeRange, selectedInstitution, selectedDevice, startDate, endDate });
    const newFilters = {
      timeRange,
      institutionId: selectedInstitution,
      deviceId: selectedDevice,
      startDate,
      endDate
    };
    console.log('🔍 WeatherStationFilters - Llamando onFiltersChange con:', newFilters);
    onFiltersChange(newFilters);
  }, [timeRange, selectedInstitution, selectedDevice, startDate, endDate, onFiltersChange]);

  // Vista horaria: fuerza un único dispositivo (auto-selecciona el primero si no hay ninguno).
  useEffect(() => {
    if (timeRange === 'hourly' && !selectedDevice && devices.length > 0) {
      setSelectedDevice(devices[0].id);
    }
  }, [timeRange, selectedDevice, devices]);

  return (
    <div className="flex flex-wrap gap-4 items-center bg-white p-4 rounded-lg shadow-sm border border-gray-200">
      {/* Filtro de rango de tiempo */}
      <div className="flex flex-col">
        <label className="text-sm font-medium text-gray-700 mb-1">Rango de Tiempo</label>
        <select aria-label="Rango de Tiempo"
          value={timeRange}
          onChange={(e) => setTimeRange(e.target.value)}
          className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent"
        >
          <option value="daily">Diario</option>
          <option value="monthly">Mensual</option>
          <option value="hourly">Horario</option>
        </select>
      </div>

      {/* Filtro de institución */}
      <div className="flex flex-col">
        <label className="text-sm font-medium text-gray-700 mb-1">Institución</label>
        <select aria-label="Institución"
          value={selectedInstitution}
          onChange={(e) => {
            setSelectedInstitution(e.target.value);
            setSelectedDevice(''); // Reset device selection when institution changes
          }}
          className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent"
        >
          <option value="">Seleccionar institución</option>
          {institutions.map((institution) => (
            <option key={institution.id} value={institution.id}>
              {institution.name}
            </option>
          ))}
        </select>
      </div>

      {/* Filtro de dispositivo */}
      <div className="flex flex-col">
        <label className="text-sm font-medium text-gray-700 mb-1">Estación Meteorológica</label>
        <select aria-label="Estación Meteorológica"
          value={selectedDevice}
          onChange={(e) => setSelectedDevice(e.target.value)}
          disabled={!selectedInstitution || loading}
          className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent disabled:bg-gray-100 disabled:cursor-not-allowed"
        >
          {timeRange !== 'hourly' && <option value="">Todas las estaciones</option>}
          {devices.map((device) => (
            <option key={device.id} value={device.id}>
              {device.name}
            </option>
          ))}
        </select>
      </div>

      {/* Filtro de fecha de inicio */}
      <div className="flex flex-col">
        <label className="text-sm font-medium text-gray-700 mb-1">Fecha de Inicio</label>
        <input aria-label="Fecha de Inicio"
          type="date"
          value={startDate}
          onChange={(e) => setStartDate(e.target.value)}
          className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent"
        />
      </div>

      {/* Filtro de fecha de fin */}
      <div className="flex flex-col">
        <label className="text-sm font-medium text-gray-700 mb-1">Fecha de Fin</label>
        <input aria-label="Fecha de Fin"
          type="date"
          value={endDate}
          min={timeRange === 'hourly' ? startDate : undefined}
          max={timeRange === 'hourly' && startDate ? addDaysToDateString(startDate, 6) : undefined}
          onChange={(e) => setEndDate(e.target.value)}
          className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent"
        />
      </div>

      {timeRange === 'hourly' && (
        <p className="text-xs text-orange-700 basis-full">
          Vista horaria: seleccione un dispositivo y un rango de máximo 7 días.
        </p>
      )}

      {devices.length === 0 && selectedInstitution && !loading && (
        <p className="text-xs text-orange-700 mt-1">
          No se encontraron estaciones meteorológicas para esta institución
        </p>
      )}
        
      {/* Información de depuración */}
      <div className="text-xs text-gray-500 mt-1">
        {devices.length > 0 && (
          <p className="text-xs text-green-700 mt-1">
            {devices.length} estación{devices.length !== 1 ? 'es' : ''} encontrada{devices.length !== 1 ? 's' : ''}
          </p>
        )}
        <p>Institution ID: {selectedInstitution}</p>
        <p>Devices count: {devices.length}</p>
        <p>Loading: {loading ? 'Yes' : 'No'}</p>
        <p>Selected device: {selectedDevice}</p>
      </div>

      {/* Indicador de carga */}
      {loading && (
        <div className="flex items-center text-sm text-gray-500">
          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-orange-500 mr-2"></div>
          Cargando estaciones meteorológicas...
        </div>
      )}
    </div>
  );
};

export default WeatherStationFilters;
