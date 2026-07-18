import { render, screen, waitFor } from '@testing-library/react';
import DataAvailabilityBanner from './DataAvailabilityBanner';

test('muestra el rango disponible', async () => {
  global.fetch = vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({
    daily_monthly: { min_date: '2024-01-15', max_date: '2026-07-18' },
    hourly: { min_date: '2026-06-18T00:00:00-05:00', max_date: '2026-07-18T00:00:00-05:00' },
    last_updated: '2026-07-18',
  }) }));
  render(<DataAvailabilityBanner authToken="t" institutionId={1}
    category="electricMeter" institutionName="Cesmag" />);
  await waitFor(() => {
    expect(screen.getByText(/Datos disponibles/i)).toBeInTheDocument();
  });
  expect(screen.getByText(/Cesmag/)).toBeInTheDocument();
});

test('sin datos muestra aviso', async () => {
  global.fetch = vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({
    daily_monthly: { min_date: null, max_date: null },
    hourly: { min_date: null, max_date: null }, last_updated: null,
  }) }));
  render(<DataAvailabilityBanner authToken="t" institutionId={1}
    category="electricMeter" institutionName="Cesmag" />);
  await waitFor(() => {
    expect(screen.getByText(/Sin datos disponibles/i)).toBeInTheDocument();
  });
});
