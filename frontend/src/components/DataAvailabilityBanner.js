import { useState, useEffect } from 'react';
import { ENDPOINTS, buildApiUrl, getDefaultFetchOptions, fetchWithAuth } from '../utils/apiConfig';
import { formatMonthYearLabel, formatAPIDateForDisplay, toColombiaTime } from '../utils/dateUtils';

const CATEGORY_LABELS = {
  electricMeter: 'medidores',
  inverter: 'inversores',
  weatherStation: 'estaciones meteorológicas',
};

// Icono de calendario (Heroicons outline), coherente con el resto de la app.
const CalendarIcon = ({ className }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round"
      d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
  </svg>
);

// Icono de aviso (Heroicons outline) para el estado sin datos.
const WarningIcon = ({ className }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round"
      d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
  </svg>
);

/**
 * Banner informativo con el rango real de datos disponibles por sede + categoría.
 * Sigue el patrón visual de los banners del Dashboard (icono en círculo + rounded-xl).
 */
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

  const catLabel = CATEGORY_LABELS[category] || category;

  if (loading) {
    return (
      <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl flex items-center gap-3 min-w-0"
        role="status" aria-busy="true">
        <div className="flex-shrink-0 w-10 h-10 rounded-full bg-slate-200 flex items-center justify-center">
          <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-slate-500"></div>
        </div>
        <p className="text-sm text-slate-600">Consultando disponibilidad de datos…</p>
      </div>
    );
  }

  const dm = info?.daily_monthly;
  const hasData = dm && dm.min_date && dm.max_date;

  const nowColombia = toColombiaTime(new Date());
  const todayISO =
    `${nowColombia.getFullYear()}-${String(nowColombia.getMonth() + 1).padStart(2, '0')}-` +
    `${String(nowColombia.getDate()).padStart(2, '0')}`;
  const today = formatAPIDateForDisplay(todayISO);

  if (!hasData) {
    return (
      <div className="p-4 bg-amber-50 border border-amber-200 rounded-xl flex items-start gap-3 min-w-0"
        role="alert">
        <div className="flex-shrink-0 w-10 h-10 rounded-full bg-amber-200 flex items-center justify-center">
          <WarningIcon className="w-5 h-5 text-amber-700" />
        </div>
        <div className="min-w-0">
          <p className="font-semibold text-amber-800">Sin datos disponibles</p>
          <p className="text-sm text-amber-700 break-words">
            No hay datos para {institutionName || 'esta sede'} ({catLabel}). Selecciona otra sede o categoría.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-4 bg-blue-50 border border-blue-200 rounded-xl flex items-start gap-3 min-w-0"
      role="status">
      <div className="flex-shrink-0 w-10 h-10 rounded-full bg-blue-200 flex items-center justify-center">
        <CalendarIcon className="w-5 h-5 text-blue-700" />
      </div>
      <div className="min-w-0">
        <p className="font-semibold text-blue-800">Datos disponibles</p>
        <p className="text-sm text-blue-700 break-words">
          {institutionName || 'Esta sede'} · {catLabel}:{' '}
          <span className="font-semibold">{formatMonthYearLabel(dm.min_date)}</span>
          {' – '}
          <span className="font-semibold">{formatMonthYearLabel(dm.max_date)}</span>
        </p>
        <p className="text-xs text-blue-600 mt-1">
          {info?.last_updated && <>Actualizado el {formatAPIDateForDisplay(info.last_updated)} · </>}
          Día de corte: {today} (el periodo actual puede estar incompleto).
        </p>
      </div>
    </div>
  );
}
