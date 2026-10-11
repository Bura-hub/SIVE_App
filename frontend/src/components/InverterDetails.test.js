import { describe, it, expect } from 'vitest';
import {
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
    const { render, screen, waitFor } = await import('@testing-library/react');
    const { default: InverterDetails } = await import('./InverterDetails');
    global.fetch = vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({ results: [] }) }));
    render(<InverterDetails authToken="t" onLogout={() => {}} username="u" isSuperuser={false}
      navigateTo={() => {}} isSidebarMinimized={false} setIsSidebarMinimized={() => {}} />);
    await waitFor(() => expect(screen.getByText('Detalles de Inversores')).toBeInTheDocument());
  });
});
