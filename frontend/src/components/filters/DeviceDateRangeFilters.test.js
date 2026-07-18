import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import DeviceDateRangeFilters from './DeviceDateRangeFilters';

beforeEach(() => {
  global.fetch = vi.fn((url) => {
    if (String(url).includes('/institutions/')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(
        [{ id: 1, name: 'Cesmag' }]) });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve(
      { devices: [{ scada_id: 'M1', name: 'Medidor 1' }] }) });
  });
});

test('muestra selector mensual con inputs de tipo month', async () => {
  const onFiltersChange = vi.fn();
  const { container } = render(
    <DeviceDateRangeFilters
      authToken="t" devicesEndpoint="/api/electric-meters/list/"
      deviceIdField="scada_id" deviceLabel="Medidor"
      allOptionLabel="Todos los medidores" accentColor="green"
      onFiltersChange={onFiltersChange} />
  );
  // cambiar a mensual
  const rangeSelect = await screen.findByLabelText(/rango de tiempo/i);
  fireEvent.change(rangeSelect, { target: { value: 'monthly' } });
  await waitFor(() => {
    expect(container.querySelector('input[type="month"]')).toBeInTheDocument();
  });
});

test('modo horario usa datetime-local', async () => {
  render(
    <DeviceDateRangeFilters
      authToken="t" devicesEndpoint="/api/electric-meters/list/"
      deviceIdField="scada_id" deviceLabel="Medidor"
      allOptionLabel="Todos los medidores" accentColor="green"
      onFiltersChange={() => {}} />
  );
  const rangeSelect = await screen.findByLabelText(/rango de tiempo/i);
  fireEvent.change(rangeSelect, { target: { value: 'hourly' } });
  await waitFor(() => {
    expect(document.querySelector('input[type="datetime-local"]')).toBeInTheDocument();
  });
});
