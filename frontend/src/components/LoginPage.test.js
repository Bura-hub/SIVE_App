import { render, screen, fireEvent } from '@testing-library/react';
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
