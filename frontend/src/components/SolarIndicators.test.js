import { render, screen, waitFor } from '@testing-library/react';

vi.mock('./KPI/ChartCard', () => ({ ChartCard: ({ title }) => <div data-testid="grafica">{title}</div> }));

import SolarIndicators from './SolarIndicators';

const periodo = {
  periodo: '2025-07', dias: 31, generacion_kwh: 1615.2, generacion_acumulada_kwh: 1615.2,
  rendimiento_especifico_kwh_kwp: 92.0, factor_capacidad: 0.124, diseno_kwh: 1841.4, produccion_vs_diseno_pct: 87.7,
  performance_ratio: 0.744, pr_dias_validos: 20, pr_motivo: null, eficiencia_inversor: null,
  eficiencia_inversor_motivo: 'No disponible: el inversor solo reporta la potencia DC de una entrada MPPT',
  demanda_kwh: 6481.6, demanda_media_kw: 8.7, demanda_pico_horaria_kw: 12.0, cobertura_solar_pct: 24.9,
  autoconsumo_kwh: 1615.2, autoconsumo_pct: 100, exportada_kwh: 0, ahorro_cop: 1136500, tarifa_extrapolada: false,
  co2_evitado_kg: 180.9, arboles_equivalentes: 8.2, disponibilidad_datos_pct: 99.5, cobertura_muestras_pct: 99.1,
};

const respuesta = {
  institucion: { id: 5, nombre: 'HUDN' },
  rango: { desde: '2025-07-01', hasta: '2025-07-31', granularidad: 'month' },
  periodos: [periodo],
  total: { ...periodo, periodo: 'total', pr_motivo: null },
  parametros: { kwp: 17.55, diseno_kwh_dia: 59.4, comercializador: 'asc', cu_medio_cop_kwh: 703.6 },
  supuestos: ['Capacidad instalada: 17.55 kWp (30 módulos de 585 Wp).'],
};

test('muestra los indicadores del HUDN y explica la eficiencia no disponible', async () => {
  localStorage.removeItem('authToken');   // modo invitado: sin cabecera Authorization
  global.fetch = vi.fn((url) => Promise.resolve({
    ok: true,
    json: () => Promise.resolve(String(url).includes('/institutions/')
      ? [{ id: 2, name: 'Cesmag' }, { id: 5, name: 'HUDN' }]
      : respuesta),
  }));
  render(<SolarIndicators />);
  await waitFor(() => expect(screen.getByText('Energía generada')).toBeInTheDocument());
  expect(screen.getByText(/sistema fotovoltaico de HUDN/)).toBeInTheDocument();
  expect(screen.getByText('Generación frente a lo esperado')).toBeInTheDocument();
  expect(screen.getAllByTestId('tarjeta-solar')).toHaveLength(12);
  expect(screen.getAllByText(/entradas MPPT/).length).toBeGreaterThan(0);
  expect(screen.getAllByText('jul 2025').length).toBeGreaterThan(0);
  const llamada = global.fetch.mock.calls.find(([u]) => String(u).includes('/api/solar-indicators/?'));
  expect(String(llamada[0])).toContain('institution_id=5');
  expect(llamada[1].headers.Authorization).toBeUndefined();
});
