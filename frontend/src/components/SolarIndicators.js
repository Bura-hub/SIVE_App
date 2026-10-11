import React, { useEffect, useMemo, useState } from 'react';
import {
  Chart as ChartJS, BarElement, CategoryScale, Legend, LinearScale, LineElement, PointElement, Tooltip,
} from 'chart.js';
import { Bar } from 'react-chartjs-2';
import { buildApiUrl, fetchWithAuth } from '../utils/apiConfig';
import { IconSun } from './icons';

ChartJS.register(BarElement, CategoryScale, LinearScale, LineElement, PointElement, Tooltip, Legend);

// Pantalla «Indicadores solares»: indicadores del sistema fotovoltaico de una institución calculados por SIVE
// (GET /api/solar-indicators/). Cada cifra lleva periodo, unidad y supuesto visible.

const FECHA_INICIO_DATOS = '2025-04-04';

const hoyBogota = () =>
  new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Bogota' }).format(new Date());

const num = (v, dec = 1) =>
  v === null || v === undefined || Number.isNaN(v)
    ? '—'
    : Number(v).toLocaleString('es-CO', { minimumFractionDigits: dec, maximumFractionDigits: dec });

const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
const etiquetaPeriodo = (p) => {
  if (/^\d{4}-\d{2}$/.test(p)) {
    const [a, m] = p.split('-');
    return `${MESES[Number(m) - 1]} ${a}`;
  }
  return p;
};

const fetchJson = (path, params) => {
  const token = localStorage.getItem('authToken');
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers.Authorization = `Token ${token}`;
  return fetchWithAuth(buildApiUrl(path, params), { headers });
};

export const Tarjeta = ({ titulo, valor, unidad, detalle, nota }) => (
  <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm flex flex-col gap-1" data-testid="tarjeta-solar">
    <span className="text-xs font-medium uppercase tracking-wide text-gray-500">{titulo}</span>
    <span className="text-2xl font-semibold text-gray-900">
      {valor}
      {unidad && valor !== '—' && <span className="text-sm font-normal text-gray-500 ml-1">{unidad}</span>}
    </span>
    {detalle && <span className="text-xs text-gray-600">{detalle}</span>}
    {nota && <span className="text-xs text-amber-700">{nota}</span>}
  </div>
);

const SolarIndicators = () => {
  const [instituciones, setInstituciones] = useState([]);
  const [institucionId, setInstitucionId] = useState('');
  const [desde, setDesde] = useState(FECHA_INICIO_DATOS);
  const [hasta, setHasta] = useState(hoyBogota());
  const [granularidad, setGranularidad] = useState('month');
  const [datos, setDatos] = useState(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchJson('/api/solar-indicators/institutions/')
      .then((lista) => {
        setInstituciones(lista);
        const hudn = lista.find((i) => i.name === 'HUDN');
        setInstitucionId(String((hudn || lista[0] || {}).id || ''));
      })
      .catch((e) => !e.isAuthError && setError(e.message));
  }, []);

  useEffect(() => {
    if (!institucionId) return;
    setCargando(true);
    setError(null);
    fetchJson('/api/solar-indicators/', {
      institution_id: institucionId, start_date: desde, end_date: hasta, granularity: granularidad,
    })
      .then(setDatos)
      .catch((e) => { if (!e.isAuthError) { setError(e.message); setDatos(null); } })
      .finally(() => setCargando(false));
  }, [institucionId, desde, hasta, granularidad]);

  const t = datos?.total;
  const periodoTexto = datos ? `${datos.rango.desde} a ${datos.rango.hasta}` : '';

  const grafica = useMemo(() => {
    if (!datos) return null;
    const etiquetas = datos.periodos.map((p) => etiquetaPeriodo(p.periodo));
    return {
      data: {
        labels: etiquetas,
        datasets: [
          {
            type: 'bar', label: 'Generación (kWh)', yAxisID: 'y',
            data: datos.periodos.map((p) => p.generacion_kwh), backgroundColor: 'rgba(245, 158, 11, 0.75)',
          },
          {
            type: 'bar', label: 'Diseño (kWh)', yAxisID: 'y',
            data: datos.periodos.map((p) => p.diseno_kwh), backgroundColor: 'rgba(148, 163, 184, 0.45)',
          },
          {
            type: 'line', label: 'Performance Ratio', yAxisID: 'pr',
            data: datos.periodos.map((p) => p.performance_ratio), borderColor: 'rgb(37, 99, 235)',
            backgroundColor: 'rgb(37, 99, 235)', spanGaps: false,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        scales: {
          y: { beginAtZero: true, title: { display: true, text: 'kWh' } },
          pr: { position: 'right', min: 0, max: 1.2, grid: { drawOnChartArea: false },
                title: { display: true, text: 'PR' } },
        },
      },
    };
  }, [datos]);

  return (
    <div className="p-4 md:p-6 space-y-6">
      <header className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-amber-100 text-amber-700"><IconSun className="w-6 h-6" /></div>
          <div>
            <h1 className="text-2xl font-semibold text-gray-900">Indicadores solares</h1>
            <p className="text-sm text-gray-600">
              Sistema fotovoltaico{datos ? ` de ${datos.institucion.nombre}` : ''} · {periodoTexto}
            </p>
          </div>
        </div>
        <div className="grid grid-cols-2 md:flex gap-2 text-sm">
          <label className="flex flex-col">
            <span className="text-gray-500">Institución</span>
            <select aria-label="Institución" className="border rounded-lg px-2 py-1" value={institucionId}
                    onChange={(e) => setInstitucionId(e.target.value)}>
              {instituciones.map((i) => <option key={i.id} value={i.id}>{i.name}</option>)}
            </select>
          </label>
          <label className="flex flex-col">
            <span className="text-gray-500">Agrupar por</span>
            <select aria-label="Agrupar por" className="border rounded-lg px-2 py-1" value={granularidad}
                    onChange={(e) => setGranularidad(e.target.value)}>
              <option value="day">Día</option>
              <option value="month">Mes</option>
              <option value="year">Año</option>
            </select>
          </label>
          <label className="flex flex-col">
            <span className="text-gray-500">Desde</span>
            <input type="date" className="border rounded-lg px-2 py-1" value={desde} min={FECHA_INICIO_DATOS}
                   onChange={(e) => setDesde(e.target.value)} />
          </label>
          <label className="flex flex-col">
            <span className="text-gray-500">Hasta</span>
            <input type="date" className="border rounded-lg px-2 py-1" value={hasta}
                   onChange={(e) => setHasta(e.target.value)} />
          </label>
        </div>
      </header>

      {error && <div className="p-3 rounded-lg bg-red-50 text-red-700 text-sm" role="alert">{error}</div>}
      {cargando && <div className="text-sm text-gray-500">Calculando indicadores…</div>}

      {t && (
        <>
          <section className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <Tarjeta titulo="Energía generada" valor={num(t.generacion_kwh, 0)} unidad="kWh"
                     detalle={`${num(t.generacion_kwh / 1000, 2)} MWh en ${t.dias} días`} />
            <Tarjeta titulo="Rendimiento específico" valor={num(t.rendimiento_especifico_kwh_kwp, 0)} unidad="kWh/kWp"
                     detalle={`${num(t.rendimiento_especifico_kwh_kwp / Math.max(t.dias, 1), 2)} kWh/kWp por día · ${datos.parametros.kwp} kWp`} />
            <Tarjeta titulo="Factor de capacidad" valor={num(t.factor_capacidad * 100, 1)} unidad="%" />
            <Tarjeta titulo="Producción frente al diseño" valor={num(t.produccion_vs_diseno_pct, 1)} unidad="%"
                     detalle={`Diseño: ${datos.parametros.diseno_kwh_dia} kWh/día`} />
            <Tarjeta titulo="Performance Ratio" valor={num(t.performance_ratio, 2)}
                     detalle={t.performance_ratio !== null ? `${t.pr_dias_validos} días con estación válida · irradiancia horizontal` : undefined}
                     nota={t.performance_ratio === null ? t.pr_motivo : undefined} />
            <Tarjeta titulo="Eficiencia del inversor" valor="—" nota={t.eficiencia_inversor_motivo} />
            <Tarjeta titulo="Demanda del circuito medido" valor={num(t.demanda_kwh, 0)} unidad="kWh"
                     detalle={`Media ${num(t.demanda_media_kw, 2)} kW · pico horario ${num(t.demanda_pico_horaria_kw, 2)} kW`} />
            <Tarjeta titulo="Cobertura solar" valor={num(t.cobertura_solar_pct, 1)} unidad="%"
                     detalle="Generación / demanda del Medidor 1" />
            <Tarjeta titulo="Autoconsumo" valor={num(t.autoconsumo_pct, 1)} unidad="%"
                     detalle={`Exportada: ${num(t.exportada_kwh, 0)} kWh`} />
            <Tarjeta titulo="Ahorro estimado" valor={num(t.ahorro_cop / 1e6, 2)} unidad="MCOP"
                     detalle={`CU ${datos.parametros.comercializador.toUpperCase()} medio ${num(datos.parametros.cu_medio_cop_kwh, 1)} COP/kWh`}
                     nota={t.tarifa_extrapolada ? 'Incluye meses con tarifa extrapolada' : undefined} />
            <Tarjeta titulo="CO₂ evitado" valor={num(t.co2_evitado_kg / 1000, 2)} unidad="t"
                     detalle={`≈ ${num(t.arboles_equivalentes, 0)} árboles`} />
            <Tarjeta titulo="Disponibilidad de datos" valor={num(t.disponibilidad_datos_pct, 1)} unidad="%"
                     detalle={`Horas de sol con lectura del inversor · muestras ${num(t.cobertura_muestras_pct, 1)} %`} />
          </section>

          {grafica && (
            <section className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
              <h2 className="text-sm font-semibold text-gray-700 mb-2">Generación, diseño y Performance Ratio</h2>
              <div className="h-72"><Bar data={grafica.data} options={grafica.options} /></div>
            </section>
          )}

          <section className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-gray-50 text-gray-600">
                <tr>
                  {['Periodo', 'Generación kWh', 'kWh/kWp', 'F. capacidad %', 'vs diseño %', 'PR', 'Demanda kWh',
                    'Pico kW', 'Cobertura %', 'Ahorro COP', 'CO₂ kg', 'Disponib. %'].map((h) => (
                    <th key={h} className="px-3 py-2 text-left font-medium whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {datos.periodos.map((p) => (
                  <tr key={p.periodo} className="border-t">
                    <td className="px-3 py-1.5 whitespace-nowrap">{etiquetaPeriodo(p.periodo)}</td>
                    <td className="px-3 py-1.5">{num(p.generacion_kwh, 1)}</td>
                    <td className="px-3 py-1.5">{num(p.rendimiento_especifico_kwh_kwp, 1)}</td>
                    <td className="px-3 py-1.5">{num(p.factor_capacidad * 100, 1)}</td>
                    <td className="px-3 py-1.5">{num(p.produccion_vs_diseno_pct, 1)}</td>
                    <td className="px-3 py-1.5" title={p.pr_motivo || ''}>{num(p.performance_ratio, 2)}</td>
                    <td className="px-3 py-1.5">{num(p.demanda_kwh, 0)}</td>
                    <td className="px-3 py-1.5">{num(p.demanda_pico_horaria_kw, 2)}</td>
                    <td className="px-3 py-1.5">{num(p.cobertura_solar_pct, 1)}</td>
                    <td className="px-3 py-1.5">{num(p.ahorro_cop, 0)}</td>
                    <td className="px-3 py-1.5">{num(p.co2_evitado_kg, 0)}</td>
                    <td className="px-3 py-1.5">{num(p.disponibilidad_datos_pct, 1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section className="text-xs text-gray-600 space-y-1">
            <h2 className="font-semibold text-gray-700">Cómo se calculan</h2>
            <ul className="list-disc pl-5 space-y-0.5">
              {datos.supuestos.map((s) => <li key={s}>{s}</li>)}
            </ul>
          </section>
        </>
      )}
    </div>
  );
};

export default SolarIndicators;
