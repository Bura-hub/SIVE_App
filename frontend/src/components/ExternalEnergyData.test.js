import { render, screen, waitFor } from '@testing-library/react';

vi.mock('./KPI/ChartCard', () => ({ ChartCard: ({ title }) => <div data-testid="grafica">{title}</div> }));

import ExternalEnergyData from './ExternalEnergyData';

test('no pide /savings/ y la vista carga con los demás endpoints', async () => {
  localStorage.removeItem('authToken');
  global.fetch = vi.fn((url) => {
    const u = String(url);
    if (u.includes('/savings/')) {
      return Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) });
    }
    const body = u.includes('/prices/')
      ? { source: 'XM', price_history: [{ date: '2026-10-01', price: 450.2 }] }
      : { source: 'XM' };
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) });
  });
  render(<ExternalEnergyData />);
  await waitFor(() => expect(screen.getByText('Precios de Energía')).toBeInTheDocument());
  expect(screen.queryByText('Error de Conexión XM')).toBeNull();
  const urls = global.fetch.mock.calls.map(([u]) => String(u));
  expect(urls.some((u) => u.includes('/savings/'))).toBe(false);
  expect(urls.some((u) => u.includes('/api/external-energy/prices/'))).toBe(true);
});
