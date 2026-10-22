import { changeBadgeClass } from './Dashboard';

// El color del cambio frente al mes anterior depende del indicador, no solo del signo.
const GOOD = 'text-green-700 bg-green-100';
const BAD = 'text-red-700 bg-red-100';
const NEUTRAL = 'text-gray-600 bg-gray-100';

test('más demanda es malo; menos demanda es bueno', () => {
  expect(changeBadgeClass('totalConsumption', '+5.23% vs mes pasado')).toBe(BAD);
  expect(changeBadgeClass('totalConsumption', '-3.10% vs mes pasado')).toBe(GOOD);
});

test('más generación es bueno; menos generación es malo', () => {
  expect(changeBadgeClass('totalGeneration', '+12.00% vs mes pasado')).toBe(GOOD);
  expect(changeBadgeClass('totalGeneration', '-12.00% vs mes pasado')).toBe(BAD);
  expect(changeBadgeClass('averageInstantaneousPower', '+1.5%')).toBe(GOOD);
});

test('el balance es mejor si sube', () => {
  expect(changeBadgeClass('energyBalance', '+4.0%')).toBe(GOOD);
  expect(changeBadgeClass('energyBalance', '-4.0%')).toBe(BAD);
});

test('el clima es neutro en ambos sentidos', () => {
  for (const key of ['irradiance', 'avgDailyTemp', 'relativeHumidity', 'windSpeed']) {
    expect(changeBadgeClass(key, '+8.0% vs mes pasado')).toBe(NEUTRAL);
    expect(changeBadgeClass(key, '-8.0% vs mes pasado')).toBe(NEUTRAL);
  }
});

test('0 %, sin porcentaje o indicador desconocido: neutro', () => {
  expect(changeBadgeClass('totalConsumption', '+0.00% vs mes pasado')).toBe(NEUTRAL);
  expect(changeBadgeClass('totalConsumption', 'Datos disponibles')).toBe(NEUTRAL);
  expect(changeBadgeClass('otro', '+5%')).toBe(NEUTRAL);
  expect(changeBadgeClass('totalGeneration', undefined)).toBe(NEUTRAL);
});
