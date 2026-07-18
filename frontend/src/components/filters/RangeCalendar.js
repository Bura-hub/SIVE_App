import React, { useState, useEffect, useRef } from 'react';

/**
 * Selector de rango de fechas personalizado, controlado y en español.
 * Reemplaza los inputs nativos (type=date/month/datetime-local) para evitar
 * que el navegador muestre los meses en otro idioma.
 *
 * Props:
 *  - mode: 'day' | 'month' | 'datetime'
 *  - startValue / endValue: string en el formato del modo
 *      day      -> 'YYYY-MM-DD'
 *      month    -> 'YYYY-MM'
 *      datetime -> 'YYYY-MM-DDTHH:MM'
 *  - onChange(startValue, endValue): SOLO se llama cuando el rango queda completo
 *  - accentColor: 'green' | 'red' | 'orange'
 *  - maxRangeDays: (opcional) máximo de días permitidos tras elegir el inicio
 */

// Nombres en español (definidos localmente; dateUtils no los exporta).
const MONTHS_FULL = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
  'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];
const MONTHS_ABBR = ['ene', 'feb', 'mar', 'abr', 'may', 'jun',
  'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
const WEEKDAYS = ['Lu', 'Ma', 'Mi', 'Ju', 'Vi', 'Sá', 'Do'];

// Mapa FIJO de clases Tailwind por acento (no concatenar dinámicamente).
const ACCENT = {
  green: {
    sel: 'bg-green-500 text-white', range: 'bg-green-100',
    hover: 'hover:bg-green-50', ring: 'focus:ring-green-500', text: 'text-green-700',
  },
  red: {
    sel: 'bg-red-500 text-white', range: 'bg-red-100',
    hover: 'hover:bg-red-50', ring: 'focus:ring-red-500', text: 'text-red-700',
  },
  orange: {
    sel: 'bg-orange-500 text-white', range: 'bg-orange-100',
    hover: 'hover:bg-orange-50', ring: 'focus:ring-orange-500', text: 'text-orange-700',
  },
};

const HOURS = Array.from({ length: 24 }, (_, i) => i);
const MINUTES = Array.from({ length: 12 }, (_, i) => i * 5);

const pad = (n) => String(n).padStart(2, '0');
const dayKey = (d) => d.getFullYear() * 10000 + d.getMonth() * 100 + d.getDate();
const monthKey = (d) => d.getFullYear() * 100 + d.getMonth();

// --- Conversión valor <-> Date ---
const parseValue = (str, mode) => {
  if (!str) return null;
  if (mode === 'month') {
    const [y, m] = str.split('-').map(Number);
    return new Date(y, m - 1, 1);
  }
  const [datePart] = str.split('T');
  const [y, m, d] = datePart.split('-').map(Number);
  return new Date(y, m - 1, d);
};

const parseTime = (str) => {
  if (!str || !str.includes('T')) return null;
  const [, t] = str.split('T');
  const [h, m] = t.split(':').map(Number);
  return { h, m };
};

const toValue = (date, mode, time) => {
  if (!date) return '';
  const base = `${date.getFullYear()}-${pad(date.getMonth() + 1)}`;
  if (mode === 'month') return base;
  const dayStr = `${base}-${pad(date.getDate())}`;
  if (mode === 'day') return dayStr;
  return `${dayStr}T${pad(time.h)}:${pad(time.m)}`;
};

// --- Formato para el trigger (en español) ---
const formatOne = (date, mode, time) => {
  if (!date) return '';
  if (mode === 'month') return `${MONTHS_FULL[date.getMonth()]} ${date.getFullYear()}`;
  const base = `${pad(date.getDate())} ${MONTHS_ABBR[date.getMonth()]} ${date.getFullYear()}`;
  if (mode === 'day') return base;
  return `${base} ${pad(time.h)}:${pad(time.m)}`;
};

const ChevronLeft = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
  </svg>
);
const ChevronRight = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
  </svg>
);
const CalendarIcon = () => (
  <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round"
      d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
  </svg>
);

const RangeCalendar = ({
  mode,
  startValue,
  endValue,
  onChange,
  accentColor = 'green',
  maxRangeDays,
}) => {
  const accent = ACCENT[accentColor] || ACCENT.green;

  const [open, setOpen] = useState(false);
  const [rangeStart, setRangeStart] = useState(null);
  const [rangeEnd, setRangeEnd] = useState(null);
  const [selecting, setSelecting] = useState('start'); // 'start' | 'end'
  const [startTime, setStartTime] = useState({ h: 0, m: 0 });
  const [endTime, setEndTime] = useState({ h: 23, m: 0 });
  const [viewDate, setViewDate] = useState(new Date());
  const containerRef = useRef(null);

  // Al abrir, inicializa el borrador desde las props (valores confirmados).
  useEffect(() => {
    if (!open) return;
    const s = parseValue(startValue, mode);
    const e = parseValue(endValue, mode);
    setRangeStart(s);
    setRangeEnd(e);
    setSelecting('start');
    if (mode === 'datetime') {
      const st = parseTime(startValue);
      const et = parseTime(endValue);
      if (st) setStartTime(st);
      if (et) setEndTime(et);
    }
    setViewDate(s || new Date());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  // Cierre al hacer clic fuera y con la tecla Escape.
  useEffect(() => {
    if (!open) return;
    const onDoc = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    const onKey = (e) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDoc);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const emit = (s, e, st = startTime, et = endTime) => {
    onChange(toValue(s, mode, st), toValue(e, mode, et));
  };

  const keyOf = mode === 'month' ? monthKey : dayKey;

  const isDisabled = (date) => {
    if (maxRangeDays && selecting === 'end' && rangeStart) {
      const max = new Date(rangeStart);
      max.setDate(max.getDate() + maxRangeDays);
      return dayKey(date) < dayKey(rangeStart) || dayKey(date) > dayKey(max);
    }
    return false;
  };

  // Selección de una fecha (día o mes) según el patrón secuencial tipo Avianca.
  const handlePick = (date) => {
    if (selecting === 'start' || !rangeStart) {
      setRangeStart(date);
      setRangeEnd(null);
      setSelecting('end');
      return;
    }
    // selecting === 'end'
    if (keyOf(date) < keyOf(rangeStart)) {
      // Fin anterior al inicio -> se trata como nuevo inicio.
      setRangeStart(date);
      setRangeEnd(null);
      setSelecting('end');
      return;
    }
    setRangeEnd(date);
    setSelecting('start');
    emit(rangeStart, date);
    if (mode !== 'datetime') {
      setOpen(false);
    }
  };

  const changeStartTime = (h, m) => {
    const nt = { h, m };
    setStartTime(nt);
    if (rangeStart && rangeEnd) emit(rangeStart, rangeEnd, nt, endTime);
  };
  const changeEndTime = (h, m) => {
    const nt = { h, m };
    setEndTime(nt);
    if (rangeStart && rangeEnd) emit(rangeStart, rangeEnd, startTime, nt);
  };

  // --- Etiqueta del trigger (desde las props confirmadas) ---
  const triggerLabel = () => {
    const s = parseValue(startValue, mode);
    const e = parseValue(endValue, mode);
    if (s && e) {
      const st = parseTime(startValue) || startTime;
      const et = parseTime(endValue) || endTime;
      return `${formatOne(s, mode, st)} — ${formatOne(e, mode, et)}`;
    }
    if (s) {
      const st = parseTime(startValue) || startTime;
      return `${formatOne(s, mode, st)} — Selecciona la fecha de fin`;
    }
    return 'Selecciona la fecha de fin';
  };

  const triggerAria = mode === 'month'
    ? 'Seleccionar rango de meses'
    : 'Seleccionar rango de fechas';

  // --- Grillas ---
  const buildDayCells = () => {
    const year = viewDate.getFullYear();
    const month = viewDate.getMonth();
    const first = new Date(year, month, 1);
    const offset = (first.getDay() + 6) % 7; // semana inicia lunes
    const gridStart = new Date(year, month, 1 - offset);
    const cells = [];
    for (let i = 0; i < 42; i++) {
      const d = new Date(gridStart);
      d.setDate(gridStart.getDate() + i);
      cells.push(d);
    }
    return cells;
  };

  const dayCellClass = (d) => {
    const inMonth = d.getMonth() === viewDate.getMonth();
    const disabled = isDisabled(d);
    const isStart = rangeStart && dayKey(d) === dayKey(rangeStart);
    const isEnd = rangeEnd && dayKey(d) === dayKey(rangeEnd);
    const between = rangeStart && rangeEnd &&
      dayKey(d) > dayKey(rangeStart) && dayKey(d) < dayKey(rangeEnd);
    let cls = 'w-9 h-9 flex items-center justify-center text-sm rounded-lg transition-colors ';
    if (disabled) {
      cls += 'opacity-30 cursor-not-allowed text-gray-400';
    } else if (isStart || isEnd) {
      cls += `${accent.sel} font-semibold`;
    } else if (between) {
      cls += `${accent.range} text-gray-800`;
    } else {
      cls += `${accent.hover} ${inMonth ? 'text-gray-800' : 'text-gray-300'}`;
    }
    return cls;
  };

  const monthCellClass = (d) => {
    const isStart = rangeStart && monthKey(d) === monthKey(rangeStart);
    const isEnd = rangeEnd && monthKey(d) === monthKey(rangeEnd);
    const between = rangeStart && rangeEnd &&
      monthKey(d) > monthKey(rangeStart) && monthKey(d) < monthKey(rangeEnd);
    let cls = 'py-2 text-sm rounded-lg transition-colors ';
    if (isStart || isEnd) cls += `${accent.sel} font-semibold`;
    else if (between) cls += `${accent.range} text-gray-800`;
    else cls += `${accent.hover} text-gray-700`;
    return cls;
  };

  const prevPeriod = () => {
    if (mode === 'month') {
      setViewDate(new Date(viewDate.getFullYear() - 1, 0, 1));
    } else {
      setViewDate(new Date(viewDate.getFullYear(), viewDate.getMonth() - 1, 1));
    }
  };
  const nextPeriod = () => {
    if (mode === 'month') {
      setViewDate(new Date(viewDate.getFullYear() + 1, 0, 1));
    } else {
      setViewDate(new Date(viewDate.getFullYear(), viewDate.getMonth() + 1, 1));
    }
  };

  const headerLabel = mode === 'month'
    ? `${viewDate.getFullYear()}`
    : `${MONTHS_FULL[viewDate.getMonth()]} ${viewDate.getFullYear()}`;

  const inputClass =
    'px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 ' +
    `${accent.ring} focus:border-transparent`;

  return (
    <div className="relative inline-block" ref={containerRef}>
      <button
        type="button"
        aria-haspopup="dialog"
        aria-label={triggerAria}
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className={`${inputClass} bg-white text-left flex items-center gap-2 min-w-[16rem] text-sm text-gray-700`}
      >
        <CalendarIcon />
        <span className="truncate">{triggerLabel()}</span>
      </button>

      {open && (
        <div
          role="dialog"
          className="absolute z-50 mt-2 bg-white rounded-2xl shadow-xl border border-gray-100 p-4"
        >
          {/* Encabezado de navegación */}
          <div className="flex items-center justify-between mb-3">
            <button
              type="button"
              onClick={prevPeriod}
              aria-label="Anterior"
              className="p-1.5 rounded-lg text-gray-600 hover:bg-gray-100"
            >
              <ChevronLeft />
            </button>
            <span className="text-sm font-semibold text-gray-800 capitalize">{headerLabel}</span>
            <button
              type="button"
              onClick={nextPeriod}
              aria-label="Siguiente"
              className="p-1.5 rounded-lg text-gray-600 hover:bg-gray-100"
            >
              <ChevronRight />
            </button>
          </div>

          {mode === 'month' ? (
            <div className="grid grid-cols-3 gap-2 w-56">
              {MONTHS_FULL.map((name, idx) => {
                const d = new Date(viewDate.getFullYear(), idx, 1);
                return (
                  <button
                    key={name}
                    type="button"
                    onClick={() => handlePick(d)}
                    className={monthCellClass(d)}
                  >
                    {MONTHS_ABBR[idx].charAt(0).toUpperCase() + MONTHS_ABBR[idx].slice(1)}
                  </button>
                );
              })}
            </div>
          ) : (
            <>
              <div className="grid grid-cols-7 gap-1 mb-1">
                {WEEKDAYS.map((w) => (
                  <div key={w} className="w-9 text-center text-xs font-medium text-gray-500">
                    {w}
                  </div>
                ))}
              </div>
              <div className="grid grid-cols-7 gap-1">
                {buildDayCells().map((d, i) => {
                  const disabled = isDisabled(d);
                  return (
                    <button
                      key={i}
                      type="button"
                      disabled={disabled}
                      onClick={() => !disabled && handlePick(d)}
                      className={dayCellClass(d)}
                    >
                      {d.getDate()}
                    </button>
                  );
                })}
              </div>
            </>
          )}

          {mode === 'datetime' && (
            <div className="mt-4 pt-3 border-t border-gray-100 space-y-2">
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm text-gray-600">Hora inicio</span>
                <div className="flex items-center gap-1">
                  <select
                    aria-label="Hora inicio"
                    value={startTime.h}
                    onChange={(e) => changeStartTime(Number(e.target.value), startTime.m)}
                    className={`${inputClass} py-1 text-sm`}
                  >
                    {HOURS.map((h) => <option key={h} value={h}>{pad(h)}</option>)}
                  </select>
                  <span className="text-gray-500">:</span>
                  <select
                    aria-label="Minuto inicio"
                    value={startTime.m}
                    onChange={(e) => changeStartTime(startTime.h, Number(e.target.value))}
                    className={`${inputClass} py-1 text-sm`}
                  >
                    {MINUTES.map((m) => <option key={m} value={m}>{pad(m)}</option>)}
                  </select>
                </div>
              </div>
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm text-gray-600">Hora fin</span>
                <div className="flex items-center gap-1">
                  <select
                    aria-label="Hora fin"
                    value={endTime.h}
                    onChange={(e) => changeEndTime(Number(e.target.value), endTime.m)}
                    className={`${inputClass} py-1 text-sm`}
                  >
                    {HOURS.map((h) => <option key={h} value={h}>{pad(h)}</option>)}
                  </select>
                  <span className="text-gray-500">:</span>
                  <select
                    aria-label="Minuto fin"
                    value={endTime.m}
                    onChange={(e) => changeEndTime(endTime.h, Number(e.target.value))}
                    className={`${inputClass} py-1 text-sm`}
                  >
                    {MINUTES.map((m) => <option key={m} value={m}>{pad(m)}</option>)}
                  </select>
                </div>
              </div>
            </div>
          )}

          {maxRangeDays && (
            <p className={`mt-3 text-xs ${accent.text}`}>
              Rango máximo de {maxRangeDays} días.
            </p>
          )}
        </div>
      )}
    </div>
  );
};

export default RangeCalendar;
