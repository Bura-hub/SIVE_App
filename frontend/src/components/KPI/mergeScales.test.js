import { mergeScales } from './ChartCard';

const base = { scales: { x: { ticks: { color: 'a' } }, y: { ticks: { color: 'a', callback: () => 'base' } } } };

test('añade ejes nuevos completos (p. ej. y1 a la derecha)', () => {
  const r = mergeScales(base, { scales: { y1: { position: 'right', max: 100 } } });
  expect(r.scales.y1.position).toBe('right');
  expect(r.scales.y1.max).toBe(100);
});

test('de x e y solo toma límites y título; en y, el formato de las marcas', () => {
  const cb = () => 'y';
  const r = mergeScales(base, { scales: {
    x: { ticks: { callback: (v) => v }, title: { text: 'X' } },
    y: { min: 0, max: 1, ticks: { callback: cb, stepSize: 0.2 }, grid: { color: 'z' } },
  } });
  expect(r.scales.x.ticks).toBe(base.scales.x.ticks);      // el callback de x del llamador se ignora
  expect(r.scales.x.title.text).toBe('X');
  expect(r.scales.y.min).toBe(0);
  expect(r.scales.y.max).toBe(1);
  expect(r.scales.y.ticks.callback).toBe(cb);
  expect(r.scales.y.ticks.stepSize).toBe(0.2);
  expect(r.scales.y.grid).toBeUndefined();                 // el estilo de la rejilla sigue siendo el de ChartCard
});

test('sin escalas del llamador devuelve las opciones base', () => {
  expect(mergeScales(base, {})).toBe(base);
});
