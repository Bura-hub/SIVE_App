import React, { useState, useEffect, useRef } from 'react';
import { ENDPOINTS, getDefaultFetchOptions, buildApiUrl } from '../../utils/apiConfig';
import {
  getDefaultMonthlyRange,
  getDefaultDailyRange,
  getDefaultHourlyRange,
  monthInputToStartDate,
  monthInputToEndDate,
} from '../../utils/dateUtils';
import RangeCalendar from './RangeCalendar';

// Mapa fijo de clases Tailwind por color de acento. NO concatenar cadenas
// dinámicas: Tailwind solo detecta clases presentes literalmente en el código.
const ACCENT_CLASSES = {
  green: {
    ring: 'focus:ring-green-500',
    text: 'text-green-700',
    spinner: 'border-green-500',
    hint: 'ring-2 ring-green-200',
  },
  red: {
    ring: 'focus:ring-red-500',
    text: 'text-red-700',
    spinner: 'border-red-500',
    hint: 'ring-2 ring-red-200',
  },
  orange: {
    ring: 'focus:ring-orange-500',
    text: 'text-orange-700',
    spinner: 'border-orange-500',
    hint: 'ring-2 ring-orange-200',
  },
};

/**
 * Filtro compartido y adaptativo de dispositivo + rango de fechas.
 * Usa un selector de rango personalizado (RangeCalendar) en español según la
 * granularidad seleccionada:
 *  - daily: calendario de días (rango primer/último día)
 *  - monthly: selector de meses (traducidos a primer/último día del mes)
 *  - hourly: calendario con hora (fuerza un solo dispositivo, límite 1 mes)
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

  // Flujo guiado: al elegir institución, auto-enfoca el selector de dispositivo.
  const deviceSelectRef = useRef(null);
  const justPickedInstitution = useRef(false);

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

  // Tras cargar dispositivos de una institución recién elegida, enfoca el select.
  useEffect(() => {
    if (justPickedInstitution.current && !loading && selectedInstitution) {
      justPickedInstitution.current = false;
      deviceSelectRef.current?.focus();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading, devices]);

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
          <option value="hourly">Horario</option>
          <option value="daily">Diario</option>
          <option value="monthly">Mensual</option>
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
            justPickedInstitution.current = !!e.target.value;
          }}
          className={`${inputClass} ${!selectedInstitution ? accent.hint : ''}`}
        >
          <option value="">Seleccionar institución</option>
          {institutions.map((institution) => (
            <option key={institution.id} value={institution.id}>
              {institution.name}
            </option>
          ))}
        </select>
        {!selectedInstitution && (
          <span className={`text-xs mt-1 ${accent.text}`}>
            Comienza eligiendo la institución
          </span>
        )}
      </div>

      {/* Filtro de dispositivo */}
      <div className="flex flex-col">
        <label className="text-sm font-medium text-gray-700 mb-1">{deviceLabel}</label>
        <select
          ref={deviceSelectRef}
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

      {/* Selector de rango según granularidad */}
      {timeRange === 'monthly' ? (
        <div className="flex flex-col">
          <label className="text-sm font-medium text-gray-700 mb-1">Rango de Meses</label>
          <RangeCalendar
            mode="month"
            startValue={startMonth}
            endValue={endMonth}
            onChange={(s, e) => { setStartMonth(s); setEndMonth(e); }}
            accentColor={accentColor}
          />
        </div>
      ) : timeRange === 'hourly' ? (
        <div className="flex flex-col">
          <label className="text-sm font-medium text-gray-700 mb-1">Fecha y Hora</label>
          <RangeCalendar
            mode="datetime"
            startValue={startDatetime}
            endValue={endDatetime}
            onChange={(s, e) => { setStartDatetime(s); setEndDatetime(e); }}
            accentColor={accentColor}
            maxRangeDays={31}
          />
        </div>
      ) : (
        <div className="flex flex-col">
          <label className="text-sm font-medium text-gray-700 mb-1">Rango de Fechas</label>
          <RangeCalendar
            mode="day"
            startValue={startDate}
            endValue={endDate}
            onChange={(s, e) => { setStartDate(s); setEndDate(e); }}
            accentColor={accentColor}
          />
        </div>
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
