import { useState, useEffect } from 'react';
import { ENDPOINTS, buildApiUrl, getDefaultFetchOptions, fetchWithAuth } from '../utils/apiConfig';
import { formatMonthYearLabel, formatAPIDateForDisplay, toColombiaTime } from '../utils/dateUtils';

const CATEGORY_LABELS = {
  electricMeter: 'medidores',
  inverter: 'inversores',
  weatherStation: 'estaciones meteorológicas',
};

export default function DataAvailabilityBanner({ authToken, institutionId, category, institutionName }) {
  const [info, setInfo] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!institutionId || !category) { setInfo(null); return; }
    let cancelled = false;
    setLoading(true);
    const url = buildApiUrl(ENDPOINTS.dataAvailability, { institution_id: institutionId, category });
    fetchWithAuth(url, getDefaultFetchOptions(authToken))
      .then((data) => { if (!cancelled) setInfo(data); })
      .catch(() => { if (!cancelled) setInfo(null); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [authToken, institutionId, category]);

  if (!institutionId) return null;
  if (loading) return <div className="text-sm text-gray-500">Cargando disponibilidad…</div>;

  const dm = info?.daily_monthly;
  const hasData = dm && dm.min_date && dm.max_date;
  const catLabel = CATEGORY_LABELS[category] || category;
  const nowColombia = toColombiaTime(new Date());
  const todayISO =
    `${nowColombia.getFullYear()}-${String(nowColombia.getMonth() + 1).padStart(2, '0')}-` +
    `${String(nowColombia.getDate()).padStart(2, '0')}`;
  const today = formatAPIDateForDisplay(todayISO);

  if (!hasData) {
    return (
      <div className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-2">
        📅 Sin datos disponibles para {institutionName || 'esta sede'} ({catLabel}).
      </div>
    );
  }

  return (
    <div className="text-sm text-blue-800 bg-blue-50 border border-blue-200 rounded px-3 py-2">
      📅 Datos disponibles para {institutionName || 'esta sede'} ({catLabel}):{' '}
      <strong>{formatMonthYearLabel(dm.min_date)}</strong> –{' '}
      <strong>{formatMonthYearLabel(dm.max_date)}</strong>
      {info?.last_updated && <> · actualizado {formatAPIDateForDisplay(info.last_updated)}</>}
      <span className="block text-xs text-blue-600 mt-1">
        Día de corte de la consulta: {today} (el periodo actual puede estar incompleto).
      </span>
    </div>
  );
}
