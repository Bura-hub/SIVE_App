import { powerFactorLevel, POWER_FACTOR_LABEL, POWER_FACTOR_DOT } from './powerFactor';

// Los mismos umbrales de la ficha del KPI (utils/kpiInfo.js): ≥0,95 óptimo, 0,90–0,95 bueno, <0,90 mejorable.
test('el factor de potencia se clasifica con los umbrales de la ficha', () => {
  expect(powerFactorLevel(0.95)).toBe('optimo');
  expect(powerFactorLevel(0.99)).toBe('optimo');
  expect(powerFactorLevel(0.90)).toBe('bueno');
  expect(powerFactorLevel(0.949)).toBe('bueno');
  expect(powerFactorLevel(0.899)).toBe('mejorable');
  expect(powerFactorLevel(null)).toBe('mejorable');
  expect(POWER_FACTOR_LABEL.optimo).toBe('Óptimo');
  expect(POWER_FACTOR_DOT.bueno).toBe('bg-yellow-500');
});
