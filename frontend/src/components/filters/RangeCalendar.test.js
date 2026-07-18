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
