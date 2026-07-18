import {
  formatMonthYearLabel, monthInputToStartDate, monthInputToEndDate,
  dateStringToMonthInput, getDefaultMonthlyRange, getDefaultDailyRange,
  formatHourLabel, buildAxisLabel,
} from './dateUtils';

describe('dateUtils nuevas utilidades', () => {
  test('formatMonthYearLabel abreviado', () => {
    expect(formatMonthYearLabel('2026-07-01')).toBe('Jul 2026');
  });
  test('formatMonthYearLabel completo', () => {
    expect(formatMonthYearLabel('2026-07-01', { abbreviated: false })).toBe('Julio 2026');
  });
  test('monthInputToStartDate', () => {
    expect(monthInputToStartDate('2026-07')).toBe('2026-07-01');
  });
  test('monthInputToEndDate maneja fin de mes', () => {
    expect(monthInputToEndDate('2026-02')).toBe('2026-02-28');
    expect(monthInputToEndDate('2026-07')).toBe('2026-07-31');
  });
  test('dateStringToMonthInput', () => {
    expect(dateStringToMonthInput('2026-07-01')).toBe('2026-07');
  });
  test('getDefaultMonthlyRange abarca 6 meses', () => {
    const { startMonth, endMonth } = getDefaultMonthlyRange();
    const [sy, sm] = startMonth.split('-').map(Number);
    const [ey, em] = endMonth.split('-').map(Number);
    const diff = (ey - sy) * 12 + (em - sm);
    expect(diff).toBe(5); // inclusivo => 6 meses
  });
  test('getDefaultDailyRange usa formato YYYY-MM-DD y abarca 30 días', () => {
    const { startDate, endDate } = getDefaultDailyRange();
    expect(startDate).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(endDate).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    const diffDays = Math.round(
      (new Date(endDate + 'T00:00:00') - new Date(startDate + 'T00:00:00')) / 86400000
    );
    expect(diffDays).toBe(30);
  });
  test('formatHourLabel formatea HH:MM', () => {
    const label = formatHourLabel('2026-07-18T14:00:00-05:00');
    expect(label).toMatch(/^\d{2}:\d{2}$/);
  });
  test('buildAxisLabel usa mes en modo mensual', () => {
    expect(buildAxisLabel({ date: '2026-07-01' }, 'monthly')).toBe('Jul 2026');
  });
  test('buildAxisLabel usa hora en modo horario', () => {
    expect(buildAxisLabel({ hour: '2026-07-18T14:00:00-05:00' }, 'hourly')).toMatch(/^\d{2}:\d{2}$/);
  });
});
