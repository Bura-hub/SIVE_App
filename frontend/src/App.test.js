import { render, screen } from '@testing-library/react';
import App from './App';

test('renderiza el formulario de inicio de sesión', () => {
  render(<App />);
  expect(screen.getByPlaceholderText(/introduce tu usuario/i)).toBeInTheDocument();
  expect(screen.getByPlaceholderText(/introduce tu contraseña/i)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /iniciar sesión/i })).toBeInTheDocument();
});
