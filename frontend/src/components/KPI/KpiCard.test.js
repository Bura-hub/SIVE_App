import { render, screen } from '@testing-library/react';
import { KpiCard } from './KpiCard';

// El Dashboard pasa cifras numéricas: la tarjeta las escribe con coma decimal, como el resto de la interfaz.
test('una cifra numérica se muestra con coma decimal', () => {
  render(<KpiCard title="Generación" value={29.24} unit="MWh" status="normal" />);
  expect(screen.getByText('29,24')).toBeTruthy();
});

test('un texto ya formateado se muestra tal cual', () => {
  render(<KpiCard title="Eficiencia" value="No disponible" unit="" status="normal" />);
  expect(screen.getByText('No disponible')).toBeTruthy();
});
