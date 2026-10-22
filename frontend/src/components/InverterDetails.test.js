import { describe, it, expect } from 'vitest';
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react';

vi.mock('./KPI/ChartCard', () => ({ ChartCard: ({ title }) => <div data-testid="grafica">{title}</div> }));

import InverterDetails, {
  countActiveInverters,
  activeInvertersChangeText,
  summarizeInverterResults,
  DC_AC_EFFICIENCY_UNAVAILABLE,
  PR_HOURLY_UNAVAILABLE,
} from './InverterDetails';

// Corrección de octubre de 2026: campos reales del serializer y «No disponible» con motivo.
describe('summarizeInverterResults', () => {
  const rows = [
    { total_generated_energy_kwh: 1615.2, max_power_w: 15144, avg_power_factor: 0.992,
      avg_frequency_hz: 59.99, performance_ratio_pct: 74.4, reference_energy_kwh: 1415.0,
      performance_ratio_valid_days: 20, performance_ratio_note: null },
    { total_generated_energy_kwh: 1585.5, max_power_w: 15000, avg_power_factor: 0.994,
      avg_frequency_hz: 59.99, performance_ratio_pct: 75.4, reference_energy_kwh: 820.0,
      performance_ratio_valid_days: 11, performance_ratio_note: null },
  ];

  it('lee avg_power_factor en escala 0–1 y la frecuencia mientras genera', () => {
    const s = summarizeInverterResults(rows, 'monthly');
    expect(s.avgPowerFactor).toBeCloseTo(0.993, 3);
    expect(s.avgFrequencyHz).toBeCloseTo(59.99, 2);
    expect(s.energyKWh).toBeCloseTo(3200.7, 1);
    expect(s.maxPowerKW).toBeCloseTo(15.144, 3);
  });

  it('el PR del rango se pondera por la energía de referencia', () => {
    const s = summarizeInverterResults(rows, 'monthly');
    expect(s.performanceRatioPct).toBeCloseTo((74.4 * 1415 + 75.4 * 820) / 2235, 6);
    expect(s.prValidDays).toBe(31);
    expect(s.prNote).toBeNull();
  });

  it('PR null: no disponible con el motivo del backend, nunca 0', () => {
    const s = summarizeInverterResults([
      { total_generated_energy_kwh: 900, performance_ratio_pct: null, reference_energy_kwh: null,
        performance_ratio_note: 'No disponible: la estación meteorológica de Udenar no es apta para el PR' },
    ], 'daily');
    expect(s.performanceRatioPct).toBeNull();
    expect(s.prNote).toMatch(/Udenar no es apta/);
  });

  it('vista horaria: PR no disponible y energía desde energy_ac_kwh', () => {
    const s = summarizeInverterResults([{ energy_ac_kwh: 6.0 }, { energy_ac_kwh: 5.5 }], 'hourly');
    expect(s.energyKWh).toBeCloseTo(11.5);
    expect(s.performanceRatioPct).toBeNull();
    expect(s.prNote).toBe(PR_HOURLY_UNAVAILABLE);
  });

  it('sin FP ni frecuencia (inversor sin generar): null, no 0', () => {
    const s = summarizeInverterResults([{ avg_power_factor: null, avg_frequency_hz: null }], 'daily');
    expect(s.avgPowerFactor).toBeNull();
    expect(s.avgFrequencyHz).toBeNull();
  });

  it('la eficiencia DC/AC siempre se declara no disponible', () => {
    expect(summarizeInverterResults(rows, 'daily').dcAcEfficiencyNote).toBe(DC_AC_EFFICIENCY_UNAVAILABLE);
    expect(DC_AC_EFFICIENCY_UNAVAILABLE).toMatch(/una entrada MPPT/);
  });
});

describe('InverterDetails, render', () => {
  it('monta sin errores', async () => {
    global.fetch = vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({ results: [] }) }));
    render(<InverterDetails authToken="t" onLogout={() => {}} username="u" isSuperuser={false}
      navigateTo={() => {}} isSidebarMinimized={false} setIsSidebarMinimized={() => {}} />);
    await waitFor(() => expect(screen.getByText('Detalles de Inversores')).toBeInTheDocument());
  });
});

// Hallazgo de octubre: con «Todos los inversores» el backend consolida cada periodo en una
// fila con device_name='Todos', y la tarjeta decía «1 · de 1 total».
describe('countActiveInverters', () => {
  it('con la vista consolidada cuenta summary.devices, no las filas «Todos»', () => {
    const data = {
      summary: { devices: [{ device__name: 'Inversor 1' }, { device__name: 'Inversor 2' }] },
      results: [{ device: null, device_name: 'Todos' }, { device: null, device_name: 'Todos' }],
    };
    expect(countActiveInverters(data)).toBe(2);
  });

  it('sin summary, cuenta los dispositivos de las filas e ignora «Todos»', () => {
    expect(countActiveInverters({ results: [
      { device: 7, device_name: 'Inversor 1' }, { device: 7, device_name: 'Inversor 1' },
      { device: 8, device_name: 'Inversor 2' },
    ] })).toBe(2);
    expect(countActiveInverters({ results: [{ device: null, device_name: 'Todos' }] })).toBe(0);
    expect(countActiveInverters(null)).toBe(0);
  });

  it('el total sale de la institución, no del mismo conteo', () => {
    expect(activeInvertersChangeText(2, 3)).toBe('de 3 en la institución');
    expect(activeInvertersChangeText(2, null)).toBe('Con registros en el rango');
  });
});

const mockFetchInverters = () => {
  global.fetch = vi.fn((url) => {
    const u = String(url);
    const body = u.includes('/api/institutions/') ? [{ id: 5, name: 'HUDN' }]
      : u.includes('/api/inverters/list/') ? { devices: [
        { scada_id: 'I1', name: 'Inversor 1' }, { scada_id: 'I2', name: 'Inversor 2' },
        { scada_id: 'I3', name: 'Inversor 3' }], total_count: 3 }
      : u.includes('/api/data-availability/') ? {
        daily_monthly: { min_date: '2025-04-04', max_date: '2026-10-20' }, last_updated: null }
      : u.includes('/api/inverter-indicators/') ? {
        summary: { devices: [{ device__name: 'Inversor 1' }, { device__name: 'Inversor 2' }] },
        results: [
          { date: '2026-10-02', time_range: 'daily', device: null, device_name: 'Todos',
            institution_name: 'HUDN', total_generated_energy_kwh: 120, max_power_w: 15000 },
          { date: '2026-10-01', time_range: 'daily', device: null, device_name: 'Todos',
            institution_name: 'HUDN', total_generated_energy_kwh: 110, max_power_w: 14000 },
        ] }
      : { results: [] };
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body),
      text: () => Promise.resolve(JSON.stringify(body)) });
  });
};

describe('InverterDetails con «Todos los inversores»', () => {
  it('cuenta los inversores con registros y el total de la institución, y nombra la sede', async () => {
    mockFetchInverters();
    render(<InverterDetails authToken={null} onLogout={() => {}} username="" isSuperuser={false}
      navigateTo={() => {}} isSidebarMinimized={false} setIsSidebarMinimized={() => {}} />);
    const select = await screen.findByLabelText('Institución');
    await waitFor(() => expect(within(select).getByText('HUDN')).toBeInTheDocument());
    fireEvent.change(select, { target: { value: '5' } });

    await waitFor(() => expect(screen.getAllByText('de 3 en la institución').length).toBeGreaterThan(0));
    const card = screen.getByText('Inversores Activos').closest('div.rounded-xl');
    expect(within(card).getByText('2')).toBeInTheDocument();
    expect(screen.queryByText(/de 1 total/)).toBeNull();

    // Banner de disponibilidad con el nombre de la institución elegida.
    await waitFor(() => expect(screen.getByText(/HUDN · inversores/)).toBeInTheDocument());
    expect(screen.queryByText(/Esta sede/)).toBeNull();
    expect(screen.queryByText(/10 días/)).toBeNull();
  });
});
