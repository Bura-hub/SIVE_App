import { render, screen, waitFor, fireEvent, within } from '@testing-library/react';

// Captura los datos de cada gráfica por su título.
const graficas = {};
vi.mock('./KPI/ChartCard', () => ({
  ChartCard: ({ title, data }) => { graficas[title] = data; return <div data-testid="grafica">{title}</div>; },
}));

import ElectricalDetails from './ElectricalDetails';

// El TDD de corriente (IEEE 519) es el indicador fiable de distorsión de corriente: desde el 22-oct-2026 lo da el
// reporte «Calidad de Potencia», y la gráfica «Calidad de Energía» lo dibuja como cuarta serie.
test('«Calidad de Energía» dibuja el TDD de corriente', async () => {
  global.fetch = vi.fn((url) => {
    const u = String(url);
    const body = u.includes('/api/institutions/') ? [{ id: 5, name: 'HUDN' }]
      : u.includes('/api/electric-meters/list/') ? { devices: [{ scada_id: 'M1', name: 'Medidor 1' }] }
      : u.includes('/api/data-availability/') ? {
        daily_monthly: { min_date: '2025-04-04', max_date: '2026-10-20' }, last_updated: null }
      : { results: [{ date: '2025-08-02', max_current_tdd_pct: 16.9, max_voltage_thd_pct: 7.9,
          max_current_unbalance_pct: 20, max_voltage_unbalance_pct: 1.2 }] };
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body),
      text: () => Promise.resolve(JSON.stringify(body)) });
  });
  render(<ElectricalDetails authToken={null} onLogout={() => {}} username="" isSuperuser={false}
    navigateTo={() => {}} isSidebarMinimized={false} setIsSidebarMinimized={() => {}} />);
  const select = await screen.findByLabelText('Institución');
  await waitFor(() => expect(within(select).getByText('HUDN')).toBeInTheDocument());
  fireEvent.change(select, { target: { value: '5' } });

  await waitFor(() => expect(graficas['Calidad de Energía']).toBeTruthy());
  const tdd = graficas['Calidad de Energía'].datasets.find(d => d.label === 'TDD de Corriente (%)');
  expect(tdd).toBeTruthy();
  expect(tdd.data).toEqual([16.9]);
});
