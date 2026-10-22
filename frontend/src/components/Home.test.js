import { render, screen, fireEvent } from '@testing-library/react';
import Home from './Home';

// La portada lista los mismos módulos que el menú lateral (Sidebar), con el mismo criterio:
// Datos Externos es de lectura pública; Exportar Reportes solo lo usan administradores
// (el invitado lo ve y, al pulsarlo, App despliega el login).
const moduleNames = () => screen.getAllByRole('button')
  .map((b) => b.getAttribute('aria-label'))
  .filter(Boolean);

test('invitado: siete módulos, con Indicadores Solares y Datos Externos', () => {
  render(<Home navigateTo={() => {}} isSuperuser={false} authToken={null} />);
  expect(moduleNames()).toEqual([
    'Dashboard', 'Medidores', 'Inversores', 'Estaciones',
    'Indicadores Solares', 'Datos Externos', 'Exportar Reportes',
  ]);
  expect(screen.getByText('07')).toBeInTheDocument();
  expect(screen.getByText('Siete módulos, una lectura integral')).toBeInTheDocument();
  expect(screen.queryByText('06')).toBeNull();
});

test('usuario sin permisos: Datos Externos sí, Exportar Reportes no', () => {
  render(<Home navigateTo={() => {}} isSuperuser={false} authToken="t" />);
  const names = moduleNames();
  expect(names).toContain('Datos Externos');
  expect(names).toContain('Indicadores Solares');
  expect(names).not.toContain('Exportar Reportes');
  expect(screen.getByText('06')).toBeInTheDocument();
  expect(screen.getByText('Seis módulos, una lectura integral')).toBeInTheDocument();
});

test('administrador: los siete módulos', () => {
  render(<Home navigateTo={() => {}} isSuperuser authToken="t" />);
  expect(moduleNames()).toHaveLength(7);
  expect(screen.getByText('07')).toBeInTheDocument();
});

test('la fila de Indicadores Solares navega a su pantalla', () => {
  const navigateTo = vi.fn();
  render(<Home navigateTo={navigateTo} isSuperuser={false} authToken={null} />);
  fireEvent.click(screen.getByRole('button', { name: 'Indicadores Solares' }));
  expect(navigateTo).toHaveBeenCalledWith('solarIndicators');
});

test('Datos Externos ya no promete el ahorro', () => {
  render(<Home navigateTo={() => {}} isSuperuser={false} authToken={null} />);
  expect(screen.queryByText(/precios de bolsa, ahorros/)).toBeNull();
});
