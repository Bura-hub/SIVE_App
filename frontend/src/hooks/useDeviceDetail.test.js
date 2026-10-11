import { renderHook, act } from '@testing-library/react';
import { useDeviceDetail } from './useDeviceDetail';

beforeEach(() => {
  global.fetch = vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({ results: [] }) }));
});

test('modo horario envia start_datetime/end_datetime', async () => {
  const { result } = renderHook(() => useDeviceDetail({
    indicatorsEndpoint: '/api/electric-meter-indicators/',
    calculateEndpoint: '/api/x/', authToken: 't',
  }));
  await act(async () => {
    result.current.fetchData({
      timeRange: 'hourly', institutionId: 1, deviceId: 'M1',
      startDatetime: '2026-07-01T00:00', endDatetime: '2026-07-14T23:59',
    });
  });
  const calledUrl = String(global.fetch.mock.calls[0][0]);
  expect(calledUrl).toContain('start_datetime=');
  expect(calledUrl).toContain('end_datetime=');
  expect(calledUrl).not.toContain('start_date=');
});

test('modo invitado: el GET va sin Authorization y recalcular pide iniciar sesión', async () => {
  const onRequireLogin = vi.fn();
  window.addEventListener('sive:require-login', onRequireLogin);
  const { result } = renderHook(() => useDeviceDetail({
    indicatorsEndpoint: '/api/electric-meter-indicators/',
    calculateEndpoint: '/api/x/', authToken: null,
  }));
  await act(async () => {
    result.current.fetchData({ timeRange: 'daily', institutionId: 1 });
  });
  expect(global.fetch.mock.calls[0][1].headers).not.toHaveProperty('Authorization');
  global.fetch.mockClear();
  await act(async () => { await result.current.calculate(); });
  window.removeEventListener('sive:require-login', onRequireLogin);
  expect(global.fetch).not.toHaveBeenCalled();
  expect(onRequireLogin).toHaveBeenCalledTimes(1);
});
