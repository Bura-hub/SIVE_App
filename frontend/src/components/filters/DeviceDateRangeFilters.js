import React, { useState, useEffect } from 'react';
import { ENDPOINTS, getDefaultFetchOptions, buildApiUrl } from '../../utils/apiConfig';
import {
  getDefaultMonthlyRange,
  getDefaultDailyRange,
  getDefaultHourlyRange,
  monthInputToStartDate,
  monthInputToEndDate,
} from '../../utils/dateUtils';

// Mapa fijo de clases Tailwind por color de acento. NO concatenar cadenas
// dinámicas: Tailwind solo detecta clases presentes literalmente en el código.
const ACCENT_CLASSES = {
  green: {
    ring: 'focus:ring-green-500',
    text: 'text-green-700',
    spinner: 'border-green-500',
  },
  red: {
    ring: 'focus:ring-red-500',
    text: 'text-red-700',
    spinner: 'border-red-500',
  },
  orange: {
    ring: 'focus:ring-orange-500',
    text: 'text-orange-700',
    spinner: 'border-orange-500',
  },
};

// Suma un mes a un valor datetime-local ('YYYY-MM-DDTHH:MM'), devolviendo el
// mismo formato. Usado como límite `max` del rango horario (máximo 1 mes).
const addOneMonthToDatetime = (datetime) => {
  if (!datetime) return undefined;
  const d = new Date(datetime);
  if (isNaN(d.getTime())) return undefined;
  d.setMonth(d.getMonth() + 1);
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T` +
    `${pad(d.getHours())}:${pad(d.getMinutes())}`;
};

/**
 * Filtro compartido y adaptativo de dispositivo + rango de fechas.
 * Cambia el tipo de input de fecha según la granularidad seleccionada:
 *  - daily: dos <input type="date">
 *  - monthly: dos <input type="month"> (traducidos a primer/último día del mes)
 *  - hourly: dos <input type="datetime-local"> (fuerza un solo dispositivo, límite 1 mes)
 */
const DeviceDateRangeFilters = ({
  authToken,
  devicesEndpoint,
  deviceIdField,
  deviceLabel,
  allOptionLabel,
  accentColor = 'green',
  onFiltersChange,
}) => {
  const accent = ACCENT_CLASSES[accentColor] || ACCENT_CLASSES.green;

  const [timeRange, setTimeRange] = useState('daily');
  const [selectedInstitution, setSelectedInstitution] = useState('');
  const [selectedDevice, setSelectedDevice] = useState('');

  // Estados de fecha por modo, inicializados con los defaults de los helpers.
  const defaultDaily = getDefaultDailyRange();
  const defaultMonthly = getDefaultMonthlyRange();
  const defaultHourly = getDefaultHourlyRange();

  const [startDate, setStartDate] = useState(defaultDaily.startDate);
  const [endDate, setEndDate] = useState(defaultDaily.endDate);
  const [startMonth, setStartMonth] = useState(defaultMonthly.startMonth);
  const [endMonth, setEndMonth] = useState(defaultMonthly.endMonth);
  const [startDatetime, setStartDatetime] = useState(defaultHourly.startDatetime);
  const [endDatetime, setEndDatetime] = useState(defaultHourly.endDatetime);

  const [institutions, setInstitutions] = useState([]);
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(false);

  // Cargar instituciones al montar.
  useEffect(() => {
    fetchInstitutions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Cargar dispositivos cuando cambie la institución.
  useEffect(() => {
    if (selectedInstitution) {
      fetchDevices(selectedInstitution);
    } else {
      setDevices([]);
      setSelectedDevice('');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedInstitution]);

  // Vista horaria: fuerza un único dispositivo (auto-selecciona el primero).
  useEffect(() => {
    if (timeRange === 'hourly' && !selectedDevice && devices.length > 0) {
      setSelectedDevice(devices[0][deviceIdField]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [timeRange, selectedDevice, devices]);

  // Al cambiar de granularidad, reinicializar el rango con el default correspondiente.
  const handleTimeRangeChange = (value) => {
    setTimeRange(value);
    if (value === 'monthly') {
      const r = getDefaultMonthlyRange();
      setStartMonth(r.startMonth);
      setEndMonth(r.endMonth);
    } else if (value === 'hourly') {
      const r = getDefaultHourlyRange();
      setStartDatetime(r.startDatetime);
      setEndDatetime(r.endDatetime);
    } else {
      const r = getDefaultDailyRange();
      setStartDate(r.startDate);
      setEndDate(r.endDate);
    }
  };

  // Notificar cambios en los filtros, normalizados según el modo.
  useEffect(() => {
    if (!selectedInstitution) return;
    if (timeRange === 'monthly') {
      onFiltersChange({
        timeRange,
        institutionId: selectedInstitution,
        deviceId: selectedDevice,
        startDate: monthInputToStartDate(startMonth),
        endDate: monthInputToEndDate(endMonth),
      });
    } else if (timeRange === 'hourly') {
      // Emite datetimes Y su porción de fecha: el recálculo POST del hook sólo
      // lee start_date/end_date, así que horario debe proveer ambas.
      onFiltersChange({
        timeRange,
        institutionId: selectedInstitution,
        deviceId: selectedDevice,
        startDatetime,
        endDatetime,
        startDate: startDatetime ? startDatetime.slice(0, 10) : '',
        endDate: endDatetime ? endDatetime.slice(0, 10) : '',
      });
    } else {
      onFiltersChange({
        timeRange,
        institutionId: selectedInstitution,
        deviceId: selectedDevice,
        startDate,
        endDate,
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [timeRange, selectedInstitution, selectedDevice, startDate, endDate,
    startMonth, endMonth, startDatetime, endDatetime]);

  const fetchInstitutions = async () => {
    try {
      const response = await fetch(buildApiUrl(ENDPOINTS.electrical.institutions), {
        ...getDefaultFetchOptions(authToken),
      });
      if (!response.ok) {
        throw new Error(`Error ${response.status}`);
      }
      const data = await response.json();
      setInstitutions(Array.isArray(data) ? data : (data.results || []));
    } catch (error) {
      console.error('Error al cargar instituciones:', error);
      setInstitutions([]);
    }
  };

  const fetchDevices = async (institutionId) => {
    setLoading(true);
    try {
      const url = buildApiUrl(devicesEndpoint, { institution_id: institutionId });
      const response = await fetch(url, {
        ...getDefaultFetchOptions(authToken),
      });
      if (!response.ok) {
        throw new Error(`Error ${response.status}`);
      }
      const data = await response.json();
      const parsed = Array.isArray(data) ? data : (data.devices || data.results || []);
      setDevices(parsed);
      // Si solo hay un dispositivo, seleccionarlo automáticamente.
      if (parsed.length === 1) {
        setSelectedDevice(parsed[0][deviceIdField]);
      }
    } catch (error) {
      console.error('Error al cargar dispositivos:', error);
      setDevices([]);
    } finally {
      setLoading(false);
    }
  };

  const inputClass =
    `px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 ` +
    `${accent.ring} focus:border-transparent`;

  return (
    <div className="flex flex-wrap gap-4 items-center bg-white p-4 rounded-lg shadow-sm border border-gray-200">
      {/* Filtro de rango de tiempo */}
      <div className="flex flex-col">
        <label htmlFor="time-range" className="text-sm font-medium text-gray-700 mb-1">
          Rango de Tiempo
        </label>
        <select
          id="time-range"
          value={timeRange}
          onChange={(e) => handleTimeRangeChange(e.target.value)}
          className={inputClass}
        >
          <option value="daily">Diario</option>
          <option value="monthly">Mensual</option>
          <option value="hourly">Horario</option>
        </select>
      </div>

      {/* Filtro de institución */}
      <div className="flex flex-col">
        <label className="text-sm font-medium text-gray-700 mb-1">Institución</label>
        <select
          aria-label="Institución"
          value={selectedInstitution}
          onChange={(e) => {
            setSelectedInstitution(e.target.value);
            setSelectedDevice('');
          }}
          className={inputClass}
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
        <label className="text-sm font-medium text-gray-700 mb-1">{deviceLabel}</label>
        <select
          aria-label={deviceLabel}
          value={selectedDevice}
          onChange={(e) => setSelectedDevice(e.target.value)}
          disabled={!selectedInstitution || loading}
          className={`${inputClass} disabled:bg-gray-100 disabled:cursor-not-allowed`}
        >
          {timeRange !== 'hourly' && <option value="">{allOptionLabel}</option>}
          {devices.map((device) => (
            <option key={device[deviceIdField]} value={device[deviceIdField]}>
              {device.name}
            </option>
          ))}
        </select>
      </div>

      {/* Inputs de fecha según granularidad */}
      {timeRange === 'monthly' ? (
        <>
          <div className="flex flex-col">
            <label className="text-sm font-medium text-gray-700 mb-1">Mes de Inicio</label>
            <input
              aria-label="Mes de Inicio"
              type="month"
              value={startMonth}
              onChange={(e) => setStartMonth(e.target.value)}
              className={inputClass}
            />
          </div>
          <div className="flex flex-col">
            <label className="text-sm font-medium text-gray-700 mb-1">Mes de Fin</label>
            <input
              aria-label="Mes de Fin"
              type="month"
              value={endMonth}
              min={startMonth}
              onChange={(e) => setEndMonth(e.target.value)}
              className={inputClass}
            />
          </div>
        </>
      ) : timeRange === 'hourly' ? (
        <>
          <div className="flex flex-col">
            <label className="text-sm font-medium text-gray-700 mb-1">Fecha y Hora de Inicio</label>
            <input
              aria-label="Fecha y Hora de Inicio"
              type="datetime-local"
              value={startDatetime}
              onChange={(e) => setStartDatetime(e.target.value)}
              className={inputClass}
            />
          </div>
          <div className="flex flex-col">
            <label className="text-sm font-medium text-gray-700 mb-1">Fecha y Hora de Fin</label>
            <input
              aria-label="Fecha y Hora de Fin"
              type="datetime-local"
              value={endDatetime}
              min={startDatetime || undefined}
              max={addOneMonthToDatetime(startDatetime)}
              onChange={(e) => setEndDatetime(e.target.value)}
              className={inputClass}
            />
          </div>
        </>
      ) : (
        <>
          <div className="flex flex-col">
            <label className="text-sm font-medium text-gray-700 mb-1">Fecha de Inicio</label>
            <input
              aria-label="Fecha de Inicio"
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className={inputClass}
            />
          </div>
          <div className="flex flex-col">
            <label className="text-sm font-medium text-gray-700 mb-1">Fecha de Fin</label>
            <input
              aria-label="Fecha de Fin"
              type="date"
              value={endDate}
              min={startDate || undefined}
              onChange={(e) => setEndDate(e.target.value)}
              className={inputClass}
            />
          </div>
        </>
      )}

      {timeRange === 'hourly' && (
        <p className={`text-xs ${accent.text} basis-full`}>
          Vista horaria: seleccione un dispositivo y un rango de máximo 1 mes.
        </p>
      )}

      {devices.length === 0 && selectedInstitution && !loading && (
        <p className="text-xs text-orange-700 mt-1 basis-full">
          No se encontraron dispositivos para esta institución
        </p>
      )}

      {loading && (
        <div className="flex items-center text-sm text-gray-500">
          <div className={`animate-spin rounded-full h-4 w-4 border-b-2 ${accent.spinner} mr-2`}></div>
          Cargando dispositivos...
        </div>
      )}
    </div>
  );
};

export default DeviceDateRangeFilters;
