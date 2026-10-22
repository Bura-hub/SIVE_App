import { render, screen, fireEvent } from '@testing-library/react';
import RangeCalendar from './RangeCalendar';

test('onChange solo se llama cuando el rango queda completo (modo day)', () => {
  const onChange = vi.fn();
  render(
    <RangeCalendar
      mode="day"
      startValue="2026-07-10"
      endValue="2026-07-20"
      onChange={onChange}
      accentColor="green"
    />
  );

  // Abrir el popover.
  fireEvent.click(screen.getByLabelText('Seleccionar rango de fechas'));

  // Primer clic (inicio): NO debe emitir. (Días 10-28 son únicos de julio en
  // la grilla, evitando colisión con días de meses contiguos.)
  fireEvent.click(screen.getByRole('button', { name: '12' }));
  expect(onChange).not.toHaveBeenCalled();

  // Segundo clic (fin): SÍ emite una vez con el rango completo.
  fireEvent.click(screen.getByRole('button', { name: '18' }));
  expect(onChange).toHaveBeenCalledTimes(1);
  const [start, end] = onChange.mock.calls[0];
  expect(start).toBe('2026-07-12');
  expect(end).toBe('2026-07-18');
});

test('modo month emite valores YYYY-MM al completar el rango', () => {
  const onChange = vi.fn();
  render(
    <RangeCalendar
      mode="month"
      startValue="2026-03"
      endValue="2026-05"
      onChange={onChange}
      accentColor="red"
    />
  );

  fireEvent.click(screen.getByLabelText('Seleccionar rango de meses'));
  fireEvent.click(screen.getByRole('button', { name: 'Feb' }));
  expect(onChange).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Jun' }));
  expect(onChange).toHaveBeenCalledTimes(1);
  expect(onChange.mock.calls[0]).toEqual(['2026-02', '2026-06']);
});

test('modo month con maxRangeDays=366 no deja elegir un fin a más de 12 meses del inicio', () => {
  const onChange = vi.fn();
  render(
    <RangeCalendar mode="month" startValue="2025-10" endValue="2026-03"
      onChange={onChange} accentColor="green" maxRangeDays={366} />
  );
  fireEvent.click(screen.getByLabelText('Seleccionar rango de meses'));
  fireEvent.click(screen.getByRole('button', { name: 'Oct' }));       // inicio: octubre de 2025
  fireEvent.click(screen.getByRole('button', { name: 'Siguiente' })); // 2026
  // Octubre de 2026 termina el 31-oct, 395 días después del 1-oct-2025: el servidor lo rechaza.
  expect(screen.getByRole('button', { name: 'Oct' })).toBeDisabled();
  fireEvent.click(screen.getByRole('button', { name: 'Oct' }));
  expect(onChange).not.toHaveBeenCalled();
  // Septiembre de 2026 (12 meses) sí.
  expect(screen.getByRole('button', { name: 'Sep' })).toBeEnabled();
  fireEvent.click(screen.getByRole('button', { name: 'Sep' }));
  expect(onChange.mock.calls[0]).toEqual(['2025-10', '2026-09']);
});

test('maxRangeDays=30 deja el fin a 30 días del inicio y no a 31', () => {
  render(
    <RangeCalendar mode="day" startValue="2026-07-01" endValue="2026-07-05"
      onChange={() => {}} accentColor="green" maxRangeDays={30} />
  );
  fireEvent.click(screen.getByLabelText('Seleccionar rango de fechas'));
  fireEvent.click(screen.getByRole('button', { name: '12' }));        // 12-jul
  fireEvent.click(screen.getByRole('button', { name: 'Siguiente' })); // agosto
  expect(screen.getByRole('button', { name: '11' })).toBeEnabled();   // 11-ago: +30
  expect(screen.getByRole('button', { name: '12' })).toBeDisabled();  // 12-ago: +31
});

test('con maxRangeDays una fecha anterior al inicio sigue sirviendo como nuevo inicio', () => {
  const onChange = vi.fn();
  render(
    <RangeCalendar mode="day" startValue="2026-07-01" endValue="2026-07-05"
      onChange={onChange} accentColor="green" maxRangeDays={30} />
  );
  fireEvent.click(screen.getByLabelText('Seleccionar rango de fechas'));
  fireEvent.click(screen.getByRole('button', { name: '20' }));       // inicio: 20-jul
  expect(screen.getByRole('button', { name: '14' })).toBeEnabled();  // 14-jul, anterior
  fireEvent.click(screen.getByRole('button', { name: '14' }));       // nuevo inicio
  fireEvent.click(screen.getByRole('button', { name: '16' }));
  expect(onChange.mock.calls[0]).toEqual(['2026-07-14', '2026-07-16']);
});
