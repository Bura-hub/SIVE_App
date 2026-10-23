import { scaleUnit, formatNumber } from './unitUtils';

// Las tarjetas muestran cifras cortas: la unidad sube de prefijo (kWh → MWh → GWh, kW → MW) y la coma es decimal.
test('la energía y la potencia suben de unidad para dar cifras pequeñas', () => {
  expect(scaleUnit(10029.7, 'kWh')).toEqual({ value: '10,03', unit: 'MWh' });
  expect(scaleUnit(999.5, 'kWh')).toEqual({ value: '999,50', unit: 'kWh' });
  expect(scaleUnit(2500000, 'kWh', 1)).toEqual({ value: '2,5', unit: 'GWh' });
  expect(scaleUnit(22.38, 'kW')).toEqual({ value: '22,38', unit: 'kW' });
  expect(scaleUnit(1500, 'kW', 1)).toEqual({ value: '1,5', unit: 'MW' });
});

test('una unidad sin escala o un valor ausente no se tocan', () => {
  expect(scaleUnit(55.3, '%', 1)).toEqual({ value: '55,3', unit: '%' });
  expect(scaleUnit(null, 'kWh')).toEqual({ value: '0,00', unit: 'kWh' });
});

test('formatNumber usa coma decimal', () => {
  expect(formatNumber(0.913, 2)).toBe('0,91');
  expect(formatNumber(76.66, 1)).toBe('76,7');
});
