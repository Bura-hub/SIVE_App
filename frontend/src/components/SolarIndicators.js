import React, { useEffect, useMemo, useState } from 'react';
import { ChartCard } from './KPI/ChartCard';
import RangeCalendar from './filters/RangeCalendar';
import { buildApiUrl, fetchWithAuth } from '../utils/apiConfig';
import {
  IconActivity, IconAlertTriangle, IconCheckCircle, IconGauge, IconInfo, IconPower, IconScale, IconShield,
  IconSolarPanel, IconSun, IconTrendingUp, IconZap, IconClose,
} from './icons';

// Pantalla «Indicadores Solares»: indicadores del sistema fotovoltaico de una institución calculados por SIVE
// (GET /api/solar-indicators/). Mismo lenguaje visual que Medidores, Inversores y Estaciones: cabecera con
// degradado, tarjetas KPI con ficha informativa, filtros con el calendario en español, gráficas con ChartCard
// (zoom y pantalla completa) y tabla paginada. Cada cifra lleva su periodo y sus supuestos.

const FECHA_INICIO_DATOS = '2025-04-04';
const FILAS_POR_PAGINA = 20;

const hoyBogota = () => new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Bogota' }).format(new Date());

const vacio = (v) => v === null || v === undefined || Number.isNaN(v);
const num = (v, dec = 1) => (vacio(v)
  ? '—'
  : Number(v).toLocaleString('es-CO', { minimumFractionDigits: dec, maximumFractionDigits: dec }));

const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
const etiquetaPeriodo = (p) => {
  if (/^\d{4}-\d{2}$/.test(p)) {
    const [a, m] = p.split('-');
    return `${MESES[Number(m) - 1]} ${a}`;
  }
  if (/^\d{4}-\d{2}-\d{2}$/.test(p)) {
    const [a, m, d] = p.split('-');
    return `${d} ${MESES[Number(m) - 1]} ${a}`;
  }
  return p;
};

const fetchJson = (path, params) => {
  const token = localStorage.getItem('authToken');
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers.Authorization = `Token ${token}`;
  return fetchWithAuth(buildApiUrl(path, params), { headers });
};

// Paleta fija por tarjeta (clases Tailwind completas, no concatenadas, para que el build las incluya).
const PALETA = {
  amber: { bg: 'bg-amber-50', border: 'border-amber-200', icon: 'bg-amber-100 text-amber-700', value: 'text-amber-700' },
  orange: { bg: 'bg-orange-50', border: 'border-orange-200', icon: 'bg-orange-100 text-orange-700', value: 'text-orange-700' },
  green: { bg: 'bg-green-50', border: 'border-green-200', icon: 'bg-green-100 text-green-700', value: 'text-green-700' },
  teal: { bg: 'bg-teal-50', border: 'border-teal-200', icon: 'bg-teal-100 text-teal-700', value: 'text-teal-700' },
  blue: { bg: 'bg-blue-50', border: 'border-blue-200', icon: 'bg-blue-100 text-blue-700', value: 'text-blue-700' },
  indigo: { bg: 'bg-indigo-50', border: 'border-indigo-200', icon: 'bg-indigo-100 text-indigo-700', value: 'text-indigo-700' },
  purple: { bg: 'bg-purple-50', border: 'border-purple-200', icon: 'bg-purple-100 text-purple-700', value: 'text-purple-700' },
  gray: { bg: 'bg-gray-50', border: 'border-gray-200', icon: 'bg-gray-100 text-gray-600', value: 'text-gray-500' },
};

// Ficha informativa de cada tarjeta (botón del ícono).
const INFO = {
  generacion: {
    titulo: 'Energía generada',
    definicion: 'Energía AC entregada por el inversor de la planta en el periodo.',
    calculo: 'Σ potencia AC × 2 min por hora. Si la hora tiene al menos 15 de sus 30 lecturas, las que faltan se reponen con la media de las presentes; con menos no se repone nada.',
    fuente: 'Inversor de la institución (conector SCADA MTE, reconciliado cada noche).',
  },
  rendimiento: {
    titulo: 'Rendimiento específico',
    definicion: 'Energía generada por cada kWp instalado: permite comparar plantas de distinto tamaño.',
    calculo: 'Energía generada / potencia instalada (17,55 kWp: 30 módulos de 585 Wp).',
    fuente: 'Generación del inversor y capacidad instalada del proyecto.',
  },
  factor_capacidad: {
    titulo: 'Factor de capacidad',
    definicion: 'Fracción de la energía que la planta habría dado funcionando a potencia nominal todo el periodo.',
    calculo: 'Energía generada / (kWp × horas del periodo).',
    fuente: 'Generación del inversor y capacidad instalada.',
  },
  diseno: {
    titulo: 'Producción frente a lo esperado',
    definicion: 'Generación real comparada con la producción esperada según el diseño del sistema.',
    calculo: 'Energía generada / (59,4 kWh/día × días del periodo). La producción esperada sale del Informe Técnico 2: 4,5 kWh/m²/día de irradiación y 20 % de pérdidas.',
    fuente: 'Generación del inversor e Informe Técnico 2.',
  },
  pr: {
    titulo: 'Performance Ratio',
    definicion: 'Energía real frente a la que daría la planta sin pérdidas con la irradiación medida.',
    calculo: 'Σ energía AC / Σ (irradiación diaria × kWp). Solo días con ≥ 80 % de lecturas de la estación y del inversor, a ±25 % de la estación de referencia (Alvernia) y en meses sin sesgo de la estación mayor del 10 %.',
    fuente: 'Estación meteorológica de la institución (irradiancia horizontal, no en el plano de los módulos).',
  },
  eficiencia: {
    titulo: 'Eficiencia del inversor',
    definicion: 'Relación entre la potencia AC entregada y la DC recibida.',
    calculo: 'No se calcula: el inversor solo reporta la potencia DC de una de sus entradas MPPT (dcPower ≈ 0,55 × acPower).',
    fuente: 'Inversor de la institución.',
  },
  demanda: {
    titulo: 'Demanda del circuito medido',
    definicion: 'Energía demandada por el circuito del Medidor 1 de la institución (no es el consumo total de la institución).',
    calculo: 'Media de la potencia del Medidor 1 en cada hora con ≥ 15 de 30 lecturas. En medidores en el punto de conexión se suma la generación aguas abajo.',
    fuente: 'Medidor 1 de la institución (conector SCADA MTE).',
  },
  cobertura: {
    titulo: 'Cobertura solar',
    definicion: 'Parte de la demanda del circuito medido que cubrió la generación solar.',
    calculo: 'Generación / demanda del Medidor 1, en las horas con medidor válido.',
    fuente: 'Inversor y Medidor 1.',
  },
  autoconsumo: {
    titulo: 'Autoconsumo',
    definicion: 'Parte de la generación consumida en sitio; el resto se exporta a la red.',
    calculo: 'Medidor en el punto de conexión: exportación = parte negativa de la potencia del Medidor 1. Medidor de carga: toda la generación se consume en sitio mientras el medidor importe.',
    fuente: 'Inversor y Medidor 1.',
  },
  ahorro: {
    titulo: 'Ahorro estimado',
    definicion: 'Valor de la energía solar que la institución dejó de comprar.',
    calculo: 'Energía autoconsumida × CU mensual del comercializador (nivel de tensión 2, sin contribución). Meses sin tarifa publicada: la última disponible, marcada como extrapolada.',
    fuente: 'Tarifas publicadas por el comercializador (ASC o Cedenar).',
  },
  co2: {
    titulo: 'CO₂ evitado',
    definicion: 'Emisiones que se habrían producido generando esa energía en el sistema interconectado.',
    calculo: 'Generación × 0,112 kgCO₂/kWh (factor del SIN, UPME Res. 0705/2024). Árboles: 545 por cada 12 t (Informe Técnico 2).',
    fuente: 'Generación del inversor y factor de emisión de la UPME.',
  },
  disponibilidad: {
    titulo: 'Disponibilidad de datos',
    definicion: 'Qué tan completa es la información del inversor en el periodo.',
    calculo: 'Horas de sol (06:00–18:00) con al menos una lectura del inversor / horas de sol del periodo. La cobertura de lecturas es lecturas recibidas / esperadas (30 por hora).',
    fuente: 'Lecturas del inversor guardadas en SIVE.',
  },
};

const TarjetaSkeleton = () => (
  <div className="bg-white rounded-xl shadow-lg border border-amber-100 p-6 overflow-hidden relative">
    <div className="animate-pulse">
      <div className="flex items-center justify-between mb-4">
        <div className="w-12 h-12 bg-amber-100 rounded-lg" />
        <div className="w-20 h-4 bg-amber-100 rounded" />
      </div>
      <div className="w-32 h-5 bg-amber-100 rounded mb-2" />
      <div className="flex items-baseline">
        <div className="w-24 h-8 bg-amber-100 rounded" />
        <div className="w-16 h-6 bg-amber-100 rounded ml-2" />
      </div>
      <div className="mt-3 pt-3 border-t border-amber-50"><div className="w-28 h-3 bg-amber-100 rounded" /></div>
    </div>
  </div>
);

export const Tarjeta = ({ clave, titulo, valor, unidad, detalle, nota, icono, color = 'amber', onInfo }) => {
  const c = PALETA[valor === '—' ? 'gray' : color] || PALETA.amber;
  return (
    <div data-testid="tarjeta-solar"
         className={`${c.bg} p-6 rounded-xl shadow-md border ${c.border} transform hover:scale-[1.02] transition duration-300 hover:shadow-lg relative flex flex-col`}>
      <div className="flex items-center justify-between mb-4">
        <button type="button" onClick={() => onInfo && onInfo(clave)} title="Acerca de este indicador"
                aria-label={`Acerca de ${titulo}`}
                className={`p-2 rounded-lg ${c.icon} hover:scale-110 transition-transform duration-150`}>
          {icono}
        </button>
        <IconInfo className="w-4 h-4 text-gray-400" />
      </div>
      <h3 className="text-lg font-semibold text-gray-800 mb-2">{titulo}</h3>
      <div className="flex items-baseline flex-wrap">
        <p className={`text-3xl font-bold ${c.value}`}>{valor}</p>
        {unidad && valor !== '—' && <span className="ml-2 text-lg text-gray-600">{unidad}</span>}
      </div>
      <div className="mt-auto pt-3 border-t border-gray-100 space-y-1">
        {detalle && <p className="text-xs text-gray-600">{detalle}</p>}
        {nota && (
          <p className="text-xs text-amber-800 flex items-start gap-1">
            <IconAlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
            <span>{nota}</span>
          </p>
        )}
      </div>
    </div>
  );
};

const FichaIndicador = ({ clave, onClose }) => {
  const f = INFO[clave];
  if (!f) return null;
  return (
    <div role="dialog" aria-modal="true" aria-label="Información del indicador"
         className="absolute inset-0 bg-white/95 backdrop-blur-sm rounded-2xl border-2 border-amber-200 shadow-2xl z-20 p-6 lg:p-8 overflow-y-auto">
      <div className="flex justify-between items-start mb-6">
        <h3 className="font-bold text-gray-800 text-2xl">{f.titulo}</h3>
        <button type="button" onClick={onClose} title="Cerrar" aria-label="Cerrar"
                className="p-2 rounded-full bg-gray-100 hover:bg-gray-200 transition-colors duration-150">
          <IconClose className="w-6 h-6 text-gray-600" />
        </button>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 lg:gap-6">
        <div className="bg-blue-50 p-4 rounded-xl border border-blue-200">
          <span className="text-base font-semibold text-blue-800">Definición</span>
          <p className="text-sm text-blue-700 mt-2 leading-relaxed">{f.definicion}</p>
        </div>
        <div className="bg-green-50 p-4 rounded-xl border border-green-200">
          <span className="text-base font-semibold text-green-800">Cómo se calcula</span>
          <p className="text-sm text-green-700 mt-2 leading-relaxed">{f.calculo}</p>
        </div>
        <div className="bg-purple-50 p-4 rounded-xl border border-purple-200">
          <span className="text-base font-semibold text-purple-800">Fuente de datos</span>
          <p className="text-sm text-purple-700 mt-2 leading-relaxed">{f.fuente}</p>
        </div>
      </div>
    </div>
  );
};

// Opciones base de las gráficas: las mismas de las demás pantallas (leyenda, tooltip en español, zoom con rueda y
// arrastre; Ctrl + arrastrar para desplazar).
const OPCIONES_BASE = {
  responsive: true,
  maintainAspectRatio: false,
  interaction: { mode: 'index', intersect: false },
  plugins: {
    legend: {
      display: true, position: 'top', align: 'start',
      labels: { usePointStyle: true, padding: 20, font: { size: 13, weight: '600' }, color: '#374151' },
    },
    title: { display: false },
    tooltip: {
      enabled: true, mode: 'index', intersect: false,
      backgroundColor: 'rgba(0, 0, 0, 0.85)', titleColor: '#ffffff', bodyColor: '#ffffff',
      borderColor: 'rgba(255, 255, 255, 0.1)', borderWidth: 1, cornerRadius: 12, padding: 16, displayColors: true,
      callbacks: {
        label: (ctx) => {
          const v = ctx.parsed.y;
          return `${ctx.dataset.label}: ${v === null || v === undefined ? '—' : new Intl.NumberFormat('es-CO', { maximumFractionDigits: 2 }).format(v)}`;
        },
      },
    },
    zoom: {
      pan: { enabled: true, mode: 'x', modifierKey: 'ctrl' },
      zoom: {
        wheel: { enabled: true, speed: 0.1 }, pinch: { enabled: true }, mode: 'x',
        drag: { enabled: true, backgroundColor: 'rgba(245, 158, 11, 0.1)', borderColor: 'rgba(245, 158, 11, 0.3)', borderWidth: 1 },
      },
    },
  },
  scales: {
    x: { grid: { display: false }, ticks: { color: '#6B7280', maxRotation: 45 } },
    y: { beginAtZero: true, grid: { color: 'rgba(0, 0, 0, 0.05)' }, ticks: { color: '#6B7280' } },
  },
};

const conTituloY = (titulo, extra = {}) => ({
  ...OPCIONES_BASE,
  scales: {
    ...OPCIONES_BASE.scales,
    y: { ...OPCIONES_BASE.scales.y, ...extra, title: { display: true, text: titulo, color: '#6B7280' } },
  },
});

const conEjeDerecho = (tituloIzq, tituloDer, maxDer) => ({
  ...conTituloY(tituloIzq),
  scales: {
    ...conTituloY(tituloIzq).scales,
    y1: {
      position: 'right', beginAtZero: true, ...(maxDer ? { max: maxDer } : {}),
      grid: { drawOnChartArea: false }, ticks: { color: '#6B7280' },
      title: { display: true, text: tituloDer, color: '#6B7280' },
    },
  },
});

const ENCABEZADOS = ['Periodo', 'Generación (kWh)', 'Esperado (kWh)', 'Frente a lo esperado (%)', 'kWh/kWp',
  'F. capacidad (%)', 'PR', 'Demanda M1 (kWh)', 'Pico (kW)', 'Cobertura (%)', 'Ahorro (COP)', 'CO₂ (kg)',
  'Disponibilidad (%)'];

const SolarIndicators = () => {
  const [instituciones, setInstituciones] = useState([]);
  const [institucionId, setInstitucionId] = useState('');
  const [desde, setDesde] = useState(FECHA_INICIO_DATOS);
  const [hasta, setHasta] = useState(hoyBogota());
  const [granularidad, setGranularidad] = useState('month');
  const [datos, setDatos] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const [ficha, setFicha] = useState(null);
  const [pagina, setPagina] = useState(1);

  useEffect(() => {
    fetchJson('/api/solar-indicators/institutions/')
      .then((lista) => {
        setInstituciones(lista);
        const hudn = lista.find((i) => i.name === 'HUDN');
        setInstitucionId(String((hudn || lista[0] || {}).id || ''));
      })
      .catch((e) => { if (!e.isAuthError) { setError(e.message); setCargando(false); } });
  }, []);

  useEffect(() => {
    if (!institucionId || !desde || !hasta) return;
    setCargando(true);
    setError(null);
    setPagina(1);
    fetchJson('/api/solar-indicators/', {
      institution_id: institucionId, start_date: desde, end_date: hasta, granularity: granularidad,
    })
      .then(setDatos)
      .catch((e) => { if (!e.isAuthError) { setError(e.message); setDatos(null); } })
      .finally(() => setCargando(false));
  }, [institucionId, desde, hasta, granularidad]);

  const t = datos?.total;
  const periodos = useMemo(() => datos?.periodos || [], [datos]);
  const etiquetas = useMemo(() => periodos.map((p) => etiquetaPeriodo(p.periodo)), [periodos]);
  const disenoDia = datos?.parametros?.diseno_kwh_dia;

  // Generación real (barras) frente a la producción esperada según el diseño (línea discontinua).
  const graficaGeneracion = useMemo(() => ({
    labels: etiquetas,
    datasets: [
      { type: 'bar', label: 'Generación real (kWh)', data: periodos.map((p) => p.generacion_kwh),
        backgroundColor: 'rgba(245, 158, 11, 0.8)', borderColor: '#D97706', borderWidth: 1, borderRadius: 6, order: 2 },
      { type: 'line', label: `Esperado según diseño (${num(disenoDia, 1)} kWh/día)`, data: periodos.map((p) => p.diseno_kwh),
        borderColor: '#475569', backgroundColor: '#475569', borderDash: [8, 5], borderWidth: 2, pointRadius: 3,
        pointBackgroundColor: '#475569', fill: false, tension: 0, order: 1 },
    ],
  }), [etiquetas, periodos, disenoDia]);

  const graficaPR = useMemo(() => ({
    labels: etiquetas,
    datasets: [
      { label: 'Performance Ratio', data: periodos.map((p) => p.performance_ratio),
        borderColor: '#2563EB', backgroundColor: 'rgba(37, 99, 235, 0.1)', fill: true, tension: 0.3, pointRadius: 5,
        pointBackgroundColor: '#2563EB', pointBorderColor: '#ffffff', pointBorderWidth: 2, spanGaps: false },
    ],
  }), [etiquetas, periodos]);

  const graficaDemanda = useMemo(() => ({
    labels: etiquetas,
    datasets: [
      { type: 'bar', label: 'Demanda del Medidor 1 (kWh)', yAxisID: 'y', data: periodos.map((p) => p.demanda_kwh),
        backgroundColor: 'rgba(99, 102, 241, 0.65)', borderColor: '#4F46E5', borderWidth: 1, borderRadius: 6, order: 2 },
      { type: 'bar', label: 'Generación (kWh)', yAxisID: 'y', data: periodos.map((p) => p.generacion_kwh),
        backgroundColor: 'rgba(245, 158, 11, 0.8)', borderColor: '#D97706', borderWidth: 1, borderRadius: 6, order: 2 },
      { type: 'line', label: 'Cobertura solar (%)', yAxisID: 'y1', data: periodos.map((p) => p.cobertura_solar_pct),
        borderColor: '#10B981', backgroundColor: '#10B981', tension: 0.3, pointRadius: 4,
        pointBackgroundColor: '#10B981', pointBorderColor: '#ffffff', pointBorderWidth: 2, order: 1 },
    ],
  }), [etiquetas, periodos]);

  const graficaImpacto = useMemo(() => ({
    labels: etiquetas,
    datasets: [
      { type: 'bar', label: 'Ahorro (millones de COP)', yAxisID: 'y',
        data: periodos.map((p) => (vacio(p.ahorro_cop) ? null : p.ahorro_cop / 1e6)),
        backgroundColor: 'rgba(16, 185, 129, 0.75)', borderColor: '#059669', borderWidth: 1, borderRadius: 6, order: 2 },
      { type: 'line', label: 'CO₂ evitado (kg)', yAxisID: 'y1', data: periodos.map((p) => p.co2_evitado_kg),
        borderColor: '#0EA5E9', backgroundColor: '#0EA5E9', tension: 0.3, pointRadius: 4,
        pointBackgroundColor: '#0EA5E9', pointBorderColor: '#ffffff', pointBorderWidth: 2, order: 1 },
    ],
  }), [etiquetas, periodos]);

  const graficaDatos = useMemo(() => ({
    labels: etiquetas,
    datasets: [
      { label: 'Disponibilidad (horas de sol con dato, %)', data: periodos.map((p) => p.disponibilidad_datos_pct),
        borderColor: '#8B5CF6', backgroundColor: 'rgba(139, 92, 246, 0.1)', fill: true, tension: 0.3, pointRadius: 3,
        pointBackgroundColor: '#8B5CF6' },
      { label: 'Cobertura de lecturas (%)', data: periodos.map((p) => p.cobertura_muestras_pct),
        borderColor: '#F59E0B', backgroundColor: 'rgba(245, 158, 11, 0.05)', fill: false, tension: 0.3,
        pointRadius: 3, borderDash: [6, 3], pointBackgroundColor: '#F59E0B' },
    ],
  }), [etiquetas, periodos]);

  const totalPaginas = Math.max(1, Math.ceil(periodos.length / FILAS_POR_PAGINA));
  const filas = periodos.slice((pagina - 1) * FILAS_POR_PAGINA, pagina * FILAS_POR_PAGINA);
  const nombre = datos?.institucion?.nombre;
  const hayPR = periodos.some((p) => !vacio(p.performance_ratio));

  const tarjetas = t ? [
    { clave: 'generacion', titulo: 'Energía generada', valor: num(t.generacion_kwh, 0), unidad: 'kWh',
      detalle: `${num(t.generacion_kwh / 1000, 2)} MWh en ${t.dias} días`, icono: <IconZap className="w-6 h-6" />, color: 'amber' },
    { clave: 'rendimiento', titulo: 'Rendimiento específico', valor: num(t.rendimiento_especifico_kwh_kwp, 0), unidad: 'kWh/kWp',
      detalle: `${num(t.rendimiento_especifico_kwh_kwp / Math.max(t.dias, 1), 2)} kWh/kWp por día · ${datos.parametros.kwp} kWp`,
      icono: <IconSolarPanel className="w-6 h-6" />, color: 'orange' },
    { clave: 'factor_capacidad', titulo: 'Factor de capacidad', valor: num(t.factor_capacidad * 100, 1), unidad: '%',
      detalle: 'Energía / (kWp × horas del periodo)', icono: <IconGauge className="w-6 h-6" />, color: 'amber' },
    { clave: 'diseno', titulo: 'Frente a lo esperado', valor: num(t.produccion_vs_diseno_pct, 1), unidad: '%',
      detalle: `Esperado: ${num(t.diseno_kwh, 0)} kWh (${num(disenoDia, 1)} kWh/día)`, icono: <IconTrendingUp className="w-6 h-6" />, color: 'orange' },
    { clave: 'pr', titulo: 'Performance Ratio', valor: num(t.performance_ratio, 2),
      detalle: t.performance_ratio !== null ? `${t.pr_dias_validos} días válidos · irradiancia horizontal` : undefined,
      nota: t.performance_ratio === null ? 'Sin días válidos de la estación en este periodo (ver la tabla)' : undefined,
      icono: <IconSun className="w-6 h-6" />, color: 'blue' },
    { clave: 'eficiencia', titulo: 'Eficiencia del inversor', valor: '—',
      nota: 'No disponible: el inversor solo reporta una de sus entradas MPPT', icono: <IconPower className="w-6 h-6" />, color: 'gray' },
    { clave: 'demanda', titulo: 'Demanda del circuito', valor: num(t.demanda_kwh, 0), unidad: 'kWh',
      detalle: `Media ${num(t.demanda_media_kw, 2)} kW · pico horario ${num(t.demanda_pico_horaria_kw, 2)} kW`,
      icono: <IconActivity className="w-6 h-6" />, color: 'indigo' },
    { clave: 'cobertura', titulo: 'Cobertura solar', valor: num(t.cobertura_solar_pct, 1), unidad: '%',
      detalle: 'Generación / demanda del Medidor 1', icono: <IconScale className="w-6 h-6" />, color: 'teal' },
    { clave: 'autoconsumo', titulo: 'Autoconsumo', valor: num(t.autoconsumo_pct, 1), unidad: '%',
      detalle: `Exportada: ${num(t.exportada_kwh, 0)} kWh`, icono: <IconCheckCircle className="w-6 h-6" />, color: 'green' },
    { clave: 'ahorro', titulo: 'Ahorro estimado', valor: num(t.ahorro_cop / 1e6, 2), unidad: 'MCOP',
      detalle: `CU ${datos.parametros.comercializador.toUpperCase()} medio ${num(datos.parametros.cu_medio_cop_kwh, 1)} COP/kWh`,
      nota: t.tarifa_extrapolada ? 'Incluye meses con tarifa extrapolada' : undefined, icono: <IconTrendingUp className="w-6 h-6" />, color: 'green' },
    { clave: 'co2', titulo: 'CO₂ evitado', valor: num(t.co2_evitado_kg / 1000, 2), unidad: 't',
      detalle: `≈ ${num(t.arboles_equivalentes, 0)} árboles`, icono: <IconShield className="w-6 h-6" />, color: 'teal' },
    { clave: 'disponibilidad', titulo: 'Disponibilidad de datos', valor: num(t.disponibilidad_datos_pct, 1), unidad: '%',
      detalle: `Cobertura de lecturas ${num(t.cobertura_muestras_pct, 1)} %`, icono: <IconCheckCircle className="w-6 h-6" />, color: 'purple' },
  ] : [];

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Cabecera */}
      <header className="bg-gradient-to-r from-amber-500 to-orange-600 shadow-lg -mx-4 lg:-mx-8 -mt-4 lg:-mt-8">
        <div className="px-4 lg:px-8 py-8 lg:py-12">
          <div className="flex flex-col lg:flex-row lg:items-center space-y-4 lg:space-y-0 lg:space-x-4 pr-16 lg:pr-64">
            <div className="p-3 bg-white/20 rounded-xl self-start lg:self-auto">
              <IconSun className="w-6 h-6 lg:w-8 lg:h-8 text-white" />
            </div>
            <div>
              <h1 className="text-2xl lg:text-4xl font-bold text-white">Indicadores Solares</h1>
              <p className="text-amber-50 mt-1 text-sm lg:text-base">
                Desempeño del sistema fotovoltaico{nombre ? ` de ${nombre}` : ''}: producción, demanda, ahorro e impacto ambiental
              </p>
            </div>
          </div>
        </div>
      </header>

      {/* Tarjetas KPI */}
      <section className="relative bg-white/90 backdrop-blur-sm rounded-2xl shadow-xl border border-white/20 p-4 lg:p-8 -mt-4 lg:-mt-8 mb-6 lg:mb-8">
        {datos && (
          <div className="mb-4 lg:mb-6 flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center px-3 py-1 bg-amber-50 border border-amber-200 rounded-full text-xs font-medium text-amber-800">
              {nombre} · {etiquetaPeriodo(datos.rango.desde)} – {etiquetaPeriodo(datos.rango.hasta)}
            </span>
            <span className="inline-flex items-center px-3 py-1 bg-gray-50 border border-gray-200 rounded-full text-xs text-gray-600">
              {datos.parametros.kwp} kWp instalados · comercializador {datos.parametros.comercializador.toUpperCase()}
            </span>
          </div>
        )}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 lg:gap-6">
          {cargando || !t
            ? Array.from({ length: 8 }).map((_, i) => <TarjetaSkeleton key={i} />)
            : tarjetas.map((k) => <Tarjeta key={k.clave} {...k} onInfo={setFicha} />)}
        </div>
        {error && (
          <div className="text-center mt-4 lg:mt-6" role="alert">
            <div className="inline-flex items-center px-4 py-2 bg-red-50 border border-red-200 rounded-full text-sm text-red-700">
              <IconAlertTriangle className="w-4 h-4 mr-2" />
              {error}
            </div>
          </div>
        )}
        {cargando && (
          <div className="text-center mt-4 lg:mt-6">
            <div className="inline-flex items-center px-4 py-2 bg-amber-50 border border-amber-200 rounded-full text-sm">
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-amber-600 mr-2" />
              <span className="text-amber-800 font-medium">Calculando indicadores…</span>
            </div>
          </div>
        )}
        {ficha && <FichaIndicador clave={ficha} onClose={() => setFicha(null)} />}
      </section>

      {/* Análisis: filtros, gráficas y tabla */}
      <section className="mb-6 lg:mb-8">
        <div className="bg-white/95 backdrop-blur-sm rounded-2xl shadow-xl border border-white/30 overflow-hidden">
          <div className="bg-gradient-to-r from-amber-500 to-orange-600 px-4 lg:px-8 py-4 lg:py-6">
            <div className="flex flex-col lg:flex-row lg:items-center space-y-3 lg:space-y-0 lg:space-x-4">
              <div className="p-2 lg:p-3 bg-white/20 rounded-xl self-start lg:self-auto">
                <IconSolarPanel className="w-6 h-6 lg:w-7 lg:h-7 text-white" />
              </div>
              <div className="flex-1">
                <h2 className="text-lg lg:text-2xl font-bold text-white">Análisis del sistema fotovoltaico</h2>
                <p className="text-amber-50 mt-1 text-sm lg:text-base">Evolución por periodo de la producción, la demanda y el impacto</p>
              </div>
            </div>
          </div>

          <div className="p-4 lg:p-8 space-y-6 lg:space-y-8">
            {/* Filtros */}
            <div className="flex flex-wrap gap-4 items-center bg-white p-4 rounded-lg shadow-sm border border-gray-200">
              <div className="flex flex-col w-full sm:w-auto">
                <label htmlFor="solar-institucion" className="text-sm font-medium text-gray-700 mb-1">Institución</label>
                <select id="solar-institucion" aria-label="Institución" value={institucionId}
                        onChange={(e) => setInstitucionId(e.target.value)}
                        className="w-full sm:w-auto px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent">
                  {instituciones.map((i) => <option key={i.id} value={i.id}>{i.name}</option>)}
                </select>
              </div>
              <div className="flex flex-col w-full sm:w-auto">
                <label htmlFor="solar-granularidad" className="text-sm font-medium text-gray-700 mb-1">Agrupar por</label>
                <select id="solar-granularidad" aria-label="Agrupar por" value={granularidad}
                        onChange={(e) => setGranularidad(e.target.value)}
                        className="w-full sm:w-auto px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent">
                  <option value="day">Día</option>
                  <option value="month">Mes</option>
                  <option value="year">Año</option>
                </select>
              </div>
              <div className="flex flex-col w-full sm:w-auto">
                <span className="text-sm font-medium text-gray-700 mb-1">Rango de Fechas</span>
                <RangeCalendar mode="day" startValue={desde} endValue={hasta} accentColor="amber"
                               onChange={(s, e) => { if (s) setDesde(s); if (e) setHasta(e); }} />
              </div>
              <p className="text-xs text-amber-800 basis-full">
                Datos disponibles desde el 4 de abril de 2025. Pase el cursor por una gráfica para ver los valores;
                use la rueda para acercar y Ctrl + arrastrar para desplazarse.
              </p>
            </div>

            {periodos.length > 0 && (
              <>
                <ChartCard
                  title="Generación frente a lo esperado"
                  description={`Energía generada en cada periodo frente a la producción esperada según el diseño del sistema (${num(disenoDia, 1)} kWh/día, Informe Técnico 2)`}
                  type="bar"
                  data={graficaGeneracion}
                  options={conTituloY('kWh')}
                  height="400px"
                  fullscreenHeight="800px"
                />
                <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 lg:gap-6 xl:gap-8 w-full">
                  <ChartCard
                    title="Demanda y cobertura solar"
                    description="Demanda del circuito del Medidor 1 y parte cubierta por la generación"
                    type="bar"
                    data={graficaDemanda}
                    options={conEjeDerecho('kWh', 'Cobertura (%)', 100)}
                    height="350px"
                    fullscreenHeight="700px"
                  />
                  <ChartCard
                    title="Performance Ratio"
                    description={hayPR
                      ? 'Solo periodos con días válidos de la estación meteorológica (contrastada con Alvernia)'
                      : 'Sin días válidos de la estación en este rango: los motivos están en la tabla'}
                    type="line"
                    data={graficaPR}
                    options={conTituloY('PR', { max: 1.2 })}
                    height="350px"
                    fullscreenHeight="700px"
                  />
                  <ChartCard
                    title="Ahorro y CO₂ evitado"
                    description="Ahorro con la tarifa del comercializador y emisiones evitadas"
                    type="bar"
                    data={graficaImpacto}
                    options={conEjeDerecho('Millones de COP', 'kg CO₂')}
                    height="350px"
                    fullscreenHeight="700px"
                  />
                  <ChartCard
                    title="Calidad de los datos"
                    description="Horas de sol con lectura del inversor y lecturas recibidas frente a las esperadas"
                    type="line"
                    data={graficaDatos}
                    options={conTituloY('%', { max: 100 })}
                    height="350px"
                    fullscreenHeight="700px"
                  />
                </div>

                {/* Tabla */}
                <div className="bg-white rounded-2xl shadow-lg border border-gray-100 overflow-hidden">
                  <div className="px-4 lg:px-6 py-4 border-b border-gray-100 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                    <div>
                      <h3 className="text-base lg:text-lg xl:text-xl font-bold text-gray-800">Indicadores por periodo</h3>
                      <p className="text-gray-600 mt-1 text-sm">Pase el cursor por un PR vacío para ver por qué no se calculó</p>
                    </div>
                    <div className="px-3 lg:px-4 py-2 bg-gradient-to-r from-amber-500 to-orange-600 text-white text-sm font-semibold rounded-lg shadow-sm self-start">
                      {periodos.length} periodos
                      {totalPaginas > 1 && <span className="ml-2 text-xs opacity-90">(página {pagina} de {totalPaginas})</span>}
                    </div>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-100">
                      <thead className="bg-gradient-to-r from-amber-50 to-orange-100">
                        <tr>
                          {ENCABEZADOS.map((h) => (
                            <th key={h} className="px-3 xl:px-4 py-3 text-left text-xs font-bold text-amber-800 uppercase tracking-wider whitespace-nowrap border-b border-amber-100">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="bg-white divide-y divide-gray-50">
                        {filas.map((p) => (
                          <tr key={p.periodo} className="hover:bg-amber-50 transition-colors duration-150">
                            <td className="px-3 xl:px-4 py-3 whitespace-nowrap text-sm font-medium text-gray-900">{etiquetaPeriodo(p.periodo)}</td>
                            <td className="px-3 xl:px-4 py-3 whitespace-nowrap text-sm text-gray-800 font-semibold">{num(p.generacion_kwh, 1)}</td>
                            <td className="px-3 xl:px-4 py-3 whitespace-nowrap text-sm text-gray-500">{num(p.diseno_kwh, 0)}</td>
                            <td className="px-3 xl:px-4 py-3 whitespace-nowrap text-sm text-gray-700">{num(p.produccion_vs_diseno_pct, 1)}</td>
                            <td className="px-3 xl:px-4 py-3 whitespace-nowrap text-sm text-gray-700">{num(p.rendimiento_especifico_kwh_kwp, 1)}</td>
                            <td className="px-3 xl:px-4 py-3 whitespace-nowrap text-sm text-gray-700">{num(p.factor_capacidad * 100, 1)}</td>
                            <td className="px-3 xl:px-4 py-3 whitespace-nowrap text-sm text-gray-700" title={p.pr_motivo || ''}>
                              {vacio(p.performance_ratio)
                                ? <span className="text-gray-400 underline decoration-dotted cursor-help">—</span>
                                : num(p.performance_ratio, 2)}
                            </td>
                            <td className="px-3 xl:px-4 py-3 whitespace-nowrap text-sm text-gray-700">{num(p.demanda_kwh, 0)}</td>
                            <td className="px-3 xl:px-4 py-3 whitespace-nowrap text-sm text-gray-700">{num(p.demanda_pico_horaria_kw, 2)}</td>
                            <td className="px-3 xl:px-4 py-3 whitespace-nowrap text-sm text-gray-700">{num(p.cobertura_solar_pct, 1)}</td>
                            <td className="px-3 xl:px-4 py-3 whitespace-nowrap text-sm text-gray-700">{num(p.ahorro_cop, 0)}</td>
                            <td className="px-3 xl:px-4 py-3 whitespace-nowrap text-sm text-gray-700">{num(p.co2_evitado_kg, 0)}</td>
                            <td className="px-3 xl:px-4 py-3 whitespace-nowrap text-sm">
                              <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${
                                vacio(p.disponibilidad_datos_pct) ? 'bg-gray-100 text-gray-500'
                                  : p.disponibilidad_datos_pct >= 95 ? 'bg-green-100 text-green-800'
                                    : p.disponibilidad_datos_pct >= 80 ? 'bg-amber-100 text-amber-800' : 'bg-red-100 text-red-800'}`}>
                                {num(p.disponibilidad_datos_pct, 1)}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {totalPaginas > 1 && (
                    <div className="px-4 lg:px-6 py-3 border-t border-gray-100 flex items-center justify-between">
                      <button type="button" onClick={() => setPagina((n) => Math.max(1, n - 1))} disabled={pagina === 1}
                              className="px-3 py-1.5 text-sm font-medium rounded-lg border border-amber-200 text-amber-800 hover:bg-amber-50 disabled:opacity-40 disabled:cursor-not-allowed">
                        Anterior
                      </button>
                      <span className="text-sm text-gray-600">Página {pagina} de {totalPaginas}</span>
                      <button type="button" onClick={() => setPagina((n) => Math.min(totalPaginas, n + 1))} disabled={pagina === totalPaginas}
                              className="px-3 py-1.5 text-sm font-medium rounded-lg border border-amber-200 text-amber-800 hover:bg-amber-50 disabled:opacity-40 disabled:cursor-not-allowed">
                        Siguiente
                      </button>
                    </div>
                  )}
                </div>
              </>
            )}

            {datos && (
              <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4 lg:p-6">
                <div className="flex items-center gap-2 mb-3">
                  <IconInfo className="w-5 h-5 text-amber-700" />
                  <h2 className="font-semibold text-amber-900">Cómo se calculan estos indicadores</h2>
                </div>
                <ul className="list-disc pl-5 space-y-1 text-sm text-amber-900/90">
                  {datos.supuestos.map((s) => <li key={s}>{s}</li>)}
                </ul>
              </div>
            )}
          </div>
        </div>
      </section>
    </div>
  );
};

export default SolarIndicators;
