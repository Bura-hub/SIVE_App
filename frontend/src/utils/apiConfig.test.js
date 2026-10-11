import { getDefaultFetchOptions, handleApiResponse, REQUIRE_LOGIN_EVENT, requestLogin } from './apiConfig';

beforeEach(() => {
  localStorage.clear();
});

test('sin token no se envía la cabecera Authorization (modo invitado)', () => {
  expect(getDefaultFetchOptions(null).headers).not.toHaveProperty('Authorization');
  expect(getDefaultFetchOptions('').headers).not.toHaveProperty('Authorization');
  expect(getDefaultFetchOptions('abc').headers.Authorization).toBe('Token abc');
});

test('un 401 sin sesión no borra estado ni recarga: avisa que pide iniciar sesión', async () => {
  localStorage.setItem('currentPage', 'dashboard');
  const reload = vi.fn();
  const original = window.location;
  Object.defineProperty(window, 'location', { configurable: true, value: { ...original, reload } });
  try {
    const resp = { ok: false, status: 401, json: () => Promise.resolve({}) };
    await expect(handleApiResponse(resp)).rejects.toMatchObject({ requiresLogin: true, isAuthError: true });
    expect(reload).not.toHaveBeenCalled();
    expect(localStorage.getItem('currentPage')).toBe('dashboard');
  } finally {
    Object.defineProperty(window, 'location', { configurable: true, value: original });
  }
});

test('un 401 con sesión sigue limpiando el token y recargando', async () => {
  localStorage.setItem('authToken', 'caducado');
  const reload = vi.fn();
  const original = window.location;
  Object.defineProperty(window, 'location', { configurable: true, value: { ...original, reload } });
  try {
    const resp = { ok: false, status: 401, json: () => Promise.resolve({}) };
    await expect(handleApiResponse(resp)).rejects.toMatchObject({ isAuthError: true });
    expect(reload).toHaveBeenCalled();
    expect(localStorage.getItem('authToken')).toBeNull();
  } finally {
    Object.defineProperty(window, 'location', { configurable: true, value: original });
  }
});

test('requestLogin emite el evento con el motivo', () => {
  const handler = vi.fn();
  window.addEventListener(REQUIRE_LOGIN_EVENT, handler);
  requestLogin('motivo');
  window.removeEventListener(REQUIRE_LOGIN_EVENT, handler);
  expect(handler).toHaveBeenCalledTimes(1);
  expect(handler.mock.calls[0][0].detail.reason).toBe('motivo');
});
