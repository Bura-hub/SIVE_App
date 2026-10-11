import { render, screen, fireEvent, act } from '@testing-library/react';
import App from './App';
import { requestLogin } from './utils/apiConfig';

beforeEach(() => {
  localStorage.clear();
});

test('sin sesión entra como invitado, sin mostrar el login', () => {
  render(<App />);
  expect(screen.getAllByText('Invitado').length).toBeGreaterThan(0);
  expect(screen.queryByPlaceholderText(/introduce tu usuario/i)).not.toBeInTheDocument();
});

test('el botón «Iniciar sesión» despliega el login normal y se puede volver como invitado', () => {
  render(<App />);
  fireEvent.click(screen.getAllByRole('button', { name: /^iniciar sesión$/i })[0]);
  expect(screen.getByPlaceholderText(/introduce tu usuario/i)).toBeInTheDocument();
  expect(screen.getByPlaceholderText(/introduce tu contraseña/i)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /iniciar sesión/i })).toBeInTheDocument();

  fireEvent.click(screen.getByRole('button', { name: /continuar como invitado/i }));
  expect(screen.queryByPlaceholderText(/introduce tu usuario/i)).not.toBeInTheDocument();
  expect(screen.getAllByText('Invitado').length).toBeGreaterThan(0);
});

test('Exportar Reportes aparece con candado para el invitado y abre el login con el motivo', () => {
  render(<App />);
  fireEvent.click(screen.getByRole('button', { name: /exportar reportes: inicia sesión/i }));
  expect(screen.getByPlaceholderText(/introduce tu usuario/i)).toBeInTheDocument();
  expect(screen.getByText('Inicia sesión como administrador para exportar reportes.')).toBeInTheDocument();
});

test('requestLogin() desde cualquier componente despliega el login', () => {
  render(<App />);
  act(() => { requestLogin('Inicia sesión para recalcular los datos.'); });
  expect(screen.getByText('Inicia sesión para recalcular los datos.')).toBeInTheDocument();
  expect(screen.getByPlaceholderText(/introduce tu usuario/i)).toBeInTheDocument();
});

test('con sesión no aparece «Invitado» y Datos Externos está visible', () => {
  localStorage.setItem('authToken', 'tok');
  localStorage.setItem('username', 'ana');
  localStorage.setItem('isSuperuser', 'false');
  render(<App />);
  expect(screen.queryByText('Invitado')).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Datos Externos' })).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /exportar reportes/i })).not.toBeInTheDocument();
});
