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

test('informa al padre del nombre de la institución y de su lista de dispositivos', async () => {
  const onInstitutionNameChange = vi.fn();
  const onDevicesLoaded = vi.fn();
  render(<DeviceDateRangeFilters {...baseProps} onFiltersChange={() => {}}
    onInstitutionNameChange={onInstitutionNameChange} onDevicesLoaded={onDevicesLoaded} />);
  const select = await screen.findByLabelText('Institución');
  await waitFor(() => expect(screen.getByRole('option', { name: 'Cesmag' })).toBeInTheDocument());
  fireEvent.change(select, { target: { value: '1' } });
  await waitFor(() => expect(onInstitutionNameChange).toHaveBeenLastCalledWith('Cesmag'));
  await waitFor(() => expect(onDevicesLoaded).toHaveBeenLastCalledWith([{ scada_id: 'M1', name: 'Medidor 1' }]));

  fireEvent.change(select, { target: { value: '' } });
  await waitFor(() => expect(onInstitutionNameChange).toHaveBeenLastCalledWith(null));
  expect(onDevicesLoaded).toHaveBeenLastCalledWith(null);
});

test('si falla la lista de dispositivos, el total queda desconocido (null), no en cero', async () => {
  global.fetch = vi.fn((url) => (String(url).includes('/institutions/')
    ? Promise.resolve({ ok: true, json: () => Promise.resolve([{ id: 1, name: 'Cesmag' }]) })
    : Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) })));
  const onDevicesLoaded = vi.fn();
  const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
  render(<DeviceDateRangeFilters {...baseProps} onFiltersChange={() => {}} onDevicesLoaded={onDevicesLoaded} />);
  const select = await screen.findByLabelText('Institución');
  await waitFor(() => expect(screen.getByRole('option', { name: 'Cesmag' })).toBeInTheDocument());
  fireEvent.change(select, { target: { value: '1' } });
  await waitFor(() => expect(onDevicesLoaded).toHaveBeenCalled());
  expect(onDevicesLoaded).toHaveBeenLastCalledWith(null);
  spy.mockRestore();
});

test('en vista mensual el selector no deja pasar de 12 meses (tope de 366 días de la API)', async () => {
  render(<DeviceDateRangeFilters {...baseProps} onFiltersChange={() => {}} />);
  const rangeSelect = await screen.findByLabelText(/rango de tiempo/i);
  fireEvent.change(rangeSelect, { target: { value: 'monthly' } });
  fireEvent.click(await screen.findByLabelText('Seleccionar rango de meses'));
  fireEvent.click(screen.getByRole('button', { name: 'Ene' }));       // enero del año a la vista
  expect(screen.getByRole('button', { name: 'Dic' })).toBeEnabled();  // 12 meses
  fireEvent.click(screen.getByRole('button', { name: 'Siguiente' }));
  expect(screen.getByRole('button', { name: 'Ene' })).toBeDisabled(); // 13 meses
});
