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

const baseProps = {
  authToken: 't',
  devicesEndpoint: '/api/electric-meters/list/',
  deviceIdField: 'scada_id',
  deviceLabel: 'Medidor',
  allOptionLabel: 'Todos los medidores',
  accentColor: 'green',
};

test('el selector de granularidad lista Horario, Diario y Mensual en ese orden', async () => {
  render(<DeviceDateRangeFilters {...baseProps} onFiltersChange={() => {}} />);
  const rangeSelect = await screen.findByLabelText(/rango de tiempo/i);
  const options = Array.from(rangeSelect.querySelectorAll('option')).map((o) => o.value);
  expect(options).toEqual(['hourly', 'daily', 'monthly']);
  // El valor por defecto sigue siendo diario.
  expect(rangeSelect.value).toBe('daily');
});

test('modo diario muestra el trigger del selector de rango de fechas', async () => {
  render(<DeviceDateRangeFilters {...baseProps} onFiltersChange={() => {}} />);
  await screen.findByLabelText(/rango de tiempo/i);
  expect(screen.getByLabelText('Seleccionar rango de fechas')).toBeInTheDocument();
});

test('al cambiar a mensual aparece el trigger del selector de rango de meses', async () => {
  render(<DeviceDateRangeFilters {...baseProps} onFiltersChange={() => {}} />);
  const rangeSelect = await screen.findByLabelText(/rango de tiempo/i);
  fireEvent.change(rangeSelect, { target: { value: 'monthly' } });
  await waitFor(() => {
    expect(screen.getByLabelText('Seleccionar rango de meses')).toBeInTheDocument();
  });
});

test('modo horario muestra el trigger del selector con hora', async () => {
  render(<DeviceDateRangeFilters {...baseProps} onFiltersChange={() => {}} />);
  const rangeSelect = await screen.findByLabelText(/rango de tiempo/i);
  fireEvent.change(rangeSelect, { target: { value: 'hourly' } });
  await waitFor(() => {
    expect(screen.getByLabelText('Seleccionar rango de fechas')).toBeInTheDocument();
  });
});

test('muestra la ayuda para elegir institución cuando no hay ninguna seleccionada', async () => {
  render(<DeviceDateRangeFilters {...baseProps} onFiltersChange={() => {}} />);
  await screen.findByLabelText(/rango de tiempo/i);
  expect(screen.getByText(/comienza eligiendo la institución/i)).toBeInTheDocument();
});
