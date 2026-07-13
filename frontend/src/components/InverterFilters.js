import React, { useState, useEffect } from 'react';
import { ENDPOINTS, getDefaultFetchOptions, buildApiUrl } from '../utils/apiConfig';

const InverterFilters = ({ onFiltersChange, authToken }) => {
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

  // Cargar instituciones al montar el componente
  useEffect(() => {
    fetchInstitutions();
  }, []);

  // Cargar dispositivos cuando cambie la institución
  useEffect(() => {
    if (selectedInstitution) {
      console.log('Institution changed, fetching inverters for:', selectedInstitution);
      fetchInverters(selectedInstitution);
    } else {
      console.log('No institution selected, clearing inverters');
      setDevices([]);
      setSelectedDevice(''); // Reset device selection when institution changes
    }
  }, [selectedInstitution]);

  // Monitorear cambios en el estado de dispositivos
  useEffect(() => {
    console.log('Inverters state changed:', devices);
    console.log('Inverters count:', devices.length);
  }, [devices]);

  // Notificar cambios en los filtros
  useEffect(() => {
    console.log('Filters changed:', { timeRange, selectedInstitution, selectedDevice, startDate, endDate });
    onFiltersChange({
      timeRange,
      institutionId: selectedInstitution,
      deviceId: selectedDevice,
      startDate,
      endDate
    });
  }, [timeRange, selectedInstitution, selectedDevice, startDate, endDate, onFiltersChange]);

  // Vista horaria: fuerza un único dispositivo (auto-selecciona el primero si no hay ninguno).
  useEffect(() => {
    if (timeRange === 'hourly' && !selectedDevice && devices.length > 0) {
      setSelectedDevice(devices[0].scada_id);
    }
  }, [timeRange, selectedDevice, devices]);

  const fetchInstitutions = async () => {
    try {
      const response = await fetch(buildApiUrl(ENDPOINTS.electrical.institutions), {
        ...getDefaultFetchOptions(authToken)
      });
      if (!response.ok) {
        throw new Error(`Error ${response.status}`);
      }
      const data = await response.json();
      // Espera formato: [{id, name}]
      setInstitutions(Array.isArray(data) ? data : (data.results || []));
    } catch (error) {
      console.error('Error fetching institutions:', error);
      setInstitutions([]);
    }
  };
  
  const fetchInverters = async (institutionId) => {
    setLoading(true);
    try {
      console.log('Fetching inverters for institution:', institutionId, 'Type:', typeof institutionId);
      console.log('Institutions available:', institutions);
      
      const url = buildApiUrl(ENDPOINTS.inverters.list, { institution_id: institutionId });

      const response = await fetch(url, {
        ...getDefaultFetchOptions(authToken)
      });
      console.log('Response status:', response.status);
      console.log('Response ok:', response.ok);
      
      if (!response.ok) {
        throw new Error(`Error ${response.status}`);
      }
      const data = await response.json();
      console.log('Inverters response:', data);
      
      // Backend devuelve { devices: [ { scada_id, name, ... } ], total_count }
      const parsed = Array.isArray(data) ? data : (data.devices || []);
      console.log('Parsed inverters:', parsed);
      console.log('Number of inverters found:', parsed.length);
      
      // Verificar si los dispositivos tienen la estructura esperada
      if (parsed.length > 0) {
        console.log('First inverter structure:', parsed[0]);
        console.log('Inverter keys:', Object.keys(parsed[0]));
      }
      
      setDevices(parsed);
      
      // Si solo hay un dispositivo, seleccionarlo automáticamente
      if (parsed.length === 1) {
        setSelectedDevice(parsed[0].scada_id);
      }
    } catch (error) {
      console.error('Error fetching inverters:', error);
      setDevices([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-wrap gap-4 items-center bg-white p-4 rounded-lg shadow-sm border border-gray-200">
      {/* Filtro de rango de tiempo */}
      <div className="flex flex-col">
        <label className="text-sm font-medium text-gray-700 mb-1">Rango de Tiempo</label>
        <select aria-label="Rango de Tiempo"
          value={timeRange}
          onChange={(e) => setTimeRange(e.target.value)}
          className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-red-500 focus:border-transparent"
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
            setSelectedDevice(''); // Reset device when institution changes
          }}
          className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-red-500 focus:border-transparent"
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
        <label className="text-sm font-medium text-gray-700 mb-1">Inversor</label>
        <select aria-label="Inversor"
          value={selectedDevice}
          onChange={(e) => setSelectedDevice(e.target.value)}
          disabled={!selectedInstitution || loading}
          className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-red-500 focus:border-transparent disabled:bg-gray-100 disabled:cursor-not-allowed"
        >
          {timeRange !== 'hourly' && <option value="">Todos los inversores</option>}
          {devices.map((device) => (
            <option key={device.scada_id} value={device.scada_id}>
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
          className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-red-500 focus:border-transparent"
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
          className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-red-500 focus:border-transparent"
        />
      </div>

      {timeRange === 'hourly' && (
        <p className="text-xs text-red-700 basis-full">
          Vista horaria: seleccione un dispositivo y un rango de máximo 7 días.
        </p>
      )}

      {devices.length === 0 && selectedInstitution && !loading && (
        <p className="text-xs text-orange-700 mt-1">
          No se encontraron inversores para esta institución
        </p>
      )}
        
      {/* Información de depuración */}
      <div className="text-xs text-gray-500 mt-1">
        {devices.length > 0 && (
          <p className="text-xs text-red-700 mt-1">
            {devices.length} inversor{devices.length !== 1 ? 'es' : ''} encontrado{devices.length !== 1 ? 's' : ''}
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
          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-red-500 mr-2"></div>
          Cargando inversores...
        </div>
      )}
    </div>
  );
};

export default InverterFilters;
