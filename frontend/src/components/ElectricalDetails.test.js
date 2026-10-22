import { render, screen, waitFor, fireEvent, within } from '@testing-library/react';

vi.mock('./KPI/ChartCard', () => ({ ChartCard: ({ title }) => <div data-testid="grafica">{title}</div> }));

import ElectricalDetails from './ElectricalDetails';

test('el banner de disponibilidad nombra la sede elegida y no hay aviso de «10 días»', async () => {
  global.fetch = vi.fn((url) => {
    const u = String(url);
    const body = u.includes('/api/institutions/') ? [{ id: 2, name: 'Cesmag' }]
      : u.includes('/api/electric-meters/list/') ? { devices: [
        { scada_id: 'M1', name: 'Medidor 1' }, { scada_id: 'M2', name: 'Medidor 2' }] }
      : u.includes('/api/data-availability/') ? {
        daily_monthly: { min_date: '2025-04-04', max_date: '2026-10-20' }, last_updated: null }
      : { results: [] };
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body),
      text: () => Promise.resolve(JSON.stringify(body)) });
  });
  render(<ElectricalDetails authToken={null} onLogout={() => {}} username="" isSuperuser={false}
    navigateTo={() => {}} isSidebarMinimized={false} setIsSidebarMinimized={() => {}} />);
  const select = await screen.findByLabelText('Institución');
  await waitFor(() => expect(within(select).getByText('Cesmag')).toBeInTheDocument());
  fireEvent.change(select, { target: { value: '2' } });

  await waitFor(() => expect(screen.getByText(/Cesmag · medidores/)).toBeInTheDocument());
  expect(screen.queryByText(/Esta sede/)).toBeNull();
  expect(screen.queryByText(/10 días/)).toBeNull();
});
