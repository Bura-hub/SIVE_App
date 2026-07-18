import { useCallback, useRef, useState } from 'react';
import { buildApiUrl } from '../utils/apiConfig';

/**
 * Hook compartido por las 3 pantallas de detalle (Eléctricos/Inversores/Estaciones).
 * Encapsula el estado (data/loading/error/filters) y la lógica de fetch: race-guard por
 * secuencia, dedup de filtros, fetch inmediato al elegir institución y debounce (450 ms)
 * en los demás cambios, más el disparo de cálculo (POST) con re-fetch. Extraído verbatim
 * de ElectricalDetails (Ola 5) para de-duplicar las tres pantallas.
 *
 * @param {object} p
 * @param {string} p.indicatorsEndpoint  endpoint GET de indicadores de la categoría
 * @param {string} p.calculateEndpoint   endpoint POST de cálculo de la categoría
 * @param {string} p.authToken           token de la sesión
 * @param {function} [p.onNotify]        (type, message, duration) para las animaciones de transición
 */
export function useDeviceDetail({ indicatorsEndpoint, calculateEndpoint, authToken, onNotify, initialData = null, debounceMs = 450, clearOnFetch = false }) {
  const [data, setData] = useState(initialData);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState({
    timeRange: 'daily',
    institutionId: null,
    deviceId: null,
    startDate: null,
    endDate: null,
  });

  const requestSeqRef = useRef(0);
  const debounceRef = useRef(null);
  const lastFiltersRef = useRef(null);

  const notify = useCallback((type, message, duration) => {
    if (onNotify) onNotify(type, message, duration);
  }, [onNotify]);

  const fetchData = useCallback(async (f) => {
    let seq = 0;
    try {
      seq = ++requestSeqRef.current;
      if (!f || !f.institutionId) return;  // no tocar UI si no hay institución
      if (clearOnFetch) { setData(null); setError(null); }  // blank durante carga
      setLoading(true);
      setError(null);

      const defaultEndDate = new Date();
      const defaultStartDate = new Date();
      defaultStartDate.setDate(defaultStartDate.getDate() - 10);

      const isHourly = (f.timeRange || 'daily') === 'hourly';
      const baseParams = {
        time_range: f.timeRange || 'daily',
        ...(f.institutionId && { institution_id: f.institutionId }),
        ...(f.deviceId && { device_id: f.deviceId }),
      };
      if (isHourly && (f.startDatetime || f.endDatetime)) {
        baseParams.start_datetime = f.startDatetime;
        baseParams.end_datetime = f.endDatetime;
      } else {
        baseParams.start_date = f.startDate || defaultStartDate.toISOString().split('T')[0];
        baseParams.end_date = f.endDate || defaultEndDate.toISOString().split('T')[0];
      }

      const resp = await fetch(buildApiUrl(indicatorsEndpoint, baseParams), {
        headers: { 'Authorization': `Token ${authToken}`, 'Content-Type': 'application/json' },
      });
      if (!resp.ok) {
        const errText = await resp.text();
        throw new Error(errText || resp.statusText);
      }
      const json = await resp.json();
      if (seq === requestSeqRef.current) setData(json);
    } catch (err) {
      if (seq === requestSeqRef.current) setError(err.message || 'Error desconocido');
    } finally {
      if (seq === requestSeqRef.current) setLoading(false);
    }
  }, [authToken, indicatorsEndpoint, clearOnFetch]);  // initialData NO va aquí: es un
  // objeto literal recreado cada render (rompería la estabilidad de fetchData -> loop).

  const handleFiltersChange = useCallback((newFilters) => {
    setFilters(newFilters);

    const prev = lastFiltersRef.current || {};
    const same = prev.timeRange === newFilters.timeRange &&
                 prev.institutionId === newFilters.institutionId &&
                 prev.deviceId === newFilters.deviceId &&
                 prev.startDate === newFilters.startDate &&
                 prev.endDate === newFilters.endDate;
    if (same) return;
    lastFiltersRef.current = newFilters;

    // Al elegir institución, cargar de inmediato.
    if (newFilters.institutionId && (!prev.institutionId || prev.institutionId !== newFilters.institutionId)) {
      fetchData(newFilters);
      return;
    }

    if (debounceRef.current) clearTimeout(debounceRef.current);
    setLoading(false);  // evitar parpadeo mientras se debouncing
    debounceRef.current = setTimeout(() => fetchData(newFilters), debounceMs);
  }, [fetchData, debounceMs]);

  const calculate = useCallback(async () => {
    try {
      if (!filters.institutionId) {
        notify('error', 'Debe seleccionar una institución primero', 3000);
        return;
      }
      if (!filters.startDate || !filters.endDate) {
        notify('error', 'Debe seleccionar fechas de inicio y fin', 3000);
        return;
      }
      setLoading(true);
      setError(null);

      const resp = await fetch(buildApiUrl(calculateEndpoint), {
        method: 'POST',
        headers: { 'Authorization': `Token ${authToken}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          time_range: filters.timeRange,
          start_date: filters.startDate,
          end_date: filters.endDate,
          institution_id: filters.institutionId,
          device_id: filters.deviceId,
        }),
      });
      if (!resp.ok) {
        const errorData = await resp.json();
        throw new Error(errorData.detail || 'Error al calcular datos');
      }
      await resp.json();
      notify('success', 'Cálculo iniciado correctamente', 3000);
      setTimeout(() => fetchData(filters), 2000);
    } catch (err) {
      setError(err.message || 'Error desconocido al calcular datos');
      notify('error', `Error: ${err.message}`, 4000);
    } finally {
      setLoading(false);
    }
  }, [filters, authToken, calculateEndpoint, fetchData, notify]);

  return { data, loading, error, filters, setFilters, fetchData, handleFiltersChange, calculate };
}
