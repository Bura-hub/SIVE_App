import { densePoints } from './ChartCard';

const serie = (n) => ({
  labels: Array.from({ length: n }, (_, i) => `d${i}`),
  datasets: [
    { label: 'A', data: Array(n).fill(1), pointRadius: 4 },
    { label: 'B', data: Array(n).fill(2), pointRadius: 3, type: 'bar' },
  ],
});

test('en móvil, con muchos puntos, la línea queda sin puntos y el punto tocado sigue visible', () => {
  const r = densePoints(serie(31), { isMobile: true, type: 'line' });
  expect(r.datasets[0].pointRadius).toBe(0);
  expect(r.datasets[0].pointHoverRadius).toBeGreaterThanOrEqual(5);
  expect(r.datasets[1].pointRadius).toBe(3); // las barras no se tocan
});

test('sin cambios en escritorio, con pocos puntos o en barras: devuelve el mismo objeto', () => {
  const d = serie(31);
  expect(densePoints(d, { isMobile: false, type: 'line' })).toBe(d);
  expect(densePoints(d, { isMobile: true, type: 'bar' })).toBe(d);
  const corto = serie(12);
  expect(densePoints(corto, { isMobile: true, type: 'line' })).toBe(corto);
});

test('no muta los datos del llamador', () => {
  const d = serie(31);
  densePoints(d, { isMobile: true, type: 'line' });
  expect(d.datasets[0].pointRadius).toBe(4);
});
