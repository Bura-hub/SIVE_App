import { render, screen, fireEvent, act } from '@testing-library/react';
import LoginPage, { PASSWORD_RECOVERY_MESSAGE } from './LoginPage';

test('«¿Olvidó su contraseña?» da solo el contacto institucional', () => {
  const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});
  render(<LoginPage onLoginSuccess={() => {}} />);
  fireEvent.click(screen.getByRole('button', { name: /Olvidó su contraseña/ }));
  expect(alertSpy).toHaveBeenCalledWith(
    'Para recuperar tu contraseña, escribe a wilachic@udenar.edu.co (Grupo de Investigación en '
    + 'Ingeniería Eléctrica y Electrónica, GIIEE, Universidad de Nariño).');
  expect(PASSWORD_RECOVERY_MESSAGE).not.toMatch(/gmail|Teléfono|\d{3}\)|Horario/);
  alertSpy.mockRestore();
});

test('el aviso de bloqueo da la hora en español («a. m.»/«p. m.»), no «AM»/«PM»', () => {
  localStorage.setItem('loginFailedAttempts', '5');
  localStorage.setItem('loginBlockUntil', new Date(Date.now() + 10 * 60 * 1000).toISOString());
  try {
    render(<LoginPage onLoginSuccess={() => {}} />);
    const aviso = screen.getByText(/Bloqueado hasta:/).textContent;
    expect(aviso).toMatch(/[ap]\.\s?m\./);
    expect(aviso).not.toMatch(/\b[AP]M\b/);
  } finally {
    localStorage.removeItem('loginFailedAttempts');
    localStorage.removeItem('loginBlockUntil');
  }
});

// El bloqueo que se muestra es el del servidor (30 min tras 5 intentos), con su hora, y se levanta solo.
function respuestaLogin(status, body) {
  return vi.fn().mockResolvedValue({ ok: false, status, json: () => Promise.resolve(body) });
}

async function intentarLogin() {
  fireEvent.change(document.getElementById('username'), { target: { value: 'analista' } });
  fireEvent.change(document.getElementById('password'), { target: { value: 'Incorrecta9$x' } });
  await act(async () => { fireEvent.submit(document.getElementById('password').form); });
}

test('el intento que bloquea muestra la hora de desbloqueo que da el servidor', async () => {
  const hasta = new Date(Date.now() + 30 * 60 * 1000);
  global.fetch = respuestaLogin(401, { error: 'Credenciales inválidas', locked_until: hasta.toISOString() });
  try {
    render(<LoginPage onLoginSuccess={() => {}} />);
    await intentarLogin();
    const hora = hasta.toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit' });
    expect(await screen.findByText(new RegExp(`bloqueada hasta las ${hora.replace(/\./g, '\\.').replace(/\s/g, '\\s')}`))).toBeTruthy();
    expect(screen.getByText(/Bloqueado hasta:/)).toBeTruthy();
  } finally {
    localStorage.removeItem('loginFailedAttempts');
    localStorage.removeItem('loginBlockUntil');
  }
});

test('la cuenta bloqueada (423) da la hora del servidor y no minutos negativos', async () => {
  const hasta = new Date(Date.now() + 10 * 60 * 1000);
  global.fetch = respuestaLogin(423, { error: 'Cuenta bloqueada', locked_until: hasta.toISOString() });
  try {
    render(<LoginPage onLoginSuccess={() => {}} />);
    await intentarLogin();
    expect(await screen.findByText(/bloqueada hasta las/)).toBeTruthy();
    await intentarLogin();
    const aviso = await screen.findByText(/Intenta de nuevo en/);
    expect(aviso.textContent).not.toMatch(/-\d/);
  } finally {
    localStorage.removeItem('loginFailedAttempts');
    localStorage.removeItem('loginBlockUntil');
  }
});

test('el bloqueo se levanta solo al vencer, sin recargar la página', () => {
  vi.useFakeTimers();
  localStorage.setItem('loginFailedAttempts', '5');
  localStorage.setItem('loginBlockUntil', new Date(Date.now() + 60 * 1000).toISOString());
  try {
    render(<LoginPage onLoginSuccess={() => {}} />);
    expect(screen.getByText(/Bloqueado hasta:/)).toBeTruthy();
    act(() => { vi.advanceTimersByTime(61 * 1000); });
    expect(screen.queryByText(/Bloqueado hasta:/)).toBeNull();
    expect(localStorage.getItem('loginBlockUntil')).toBeNull();
  } finally {
    vi.useRealTimers();
    localStorage.removeItem('loginFailedAttempts');
    localStorage.removeItem('loginBlockUntil');
  }
});
