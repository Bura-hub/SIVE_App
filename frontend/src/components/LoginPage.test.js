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
