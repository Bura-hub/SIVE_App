import { describe, it, expect } from 'vitest';
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react';

vi.mock('./KPI/ChartCard', () => ({ ChartCard: ({ title }) => <div data-testid="grafica">{title}</div> }));

import WeatherStationDetails from './WeatherStationDetails';
import { fmtOrNA, valueOrNull, pvPowerFromRow, stationPrWarning } from './WeatherStationDetails';

// Corrección de octubre de 2026: null = no medido -> «No disponible»; potencia FV sin
// confundir kWh/m² con W/m²; estación de Udenar marcada como no apta para el PR.
describe('WeatherStationDetails, valores no disponibles', () => {
  it('null se muestra «No disponible», un 0 medido se muestra 0', () => {
    expect(fmtOrNA(null, 2)).toBe('No disponible');
    expect(fmtOrNA(undefined, 1)).toBe('No disponible');
    expect(fmtOrNA(0, 2)).toBe('0,00');
    expect(valueOrNull(null)).toBeNull();
    expect(valueOrNull(3.5)).toBe(3.5);
  });
});

describe('pvPowerFromRow', () => {
  it('diario: usa theoretical_pv_power_w, no la irradiación en kWh/m² como W/m²', () => {
    // Antes: 4,09 kWh/m² pasados como 4,09 W/m² -> 0,7 W.
    expect(pvPowerFromRow({ daily_irradiance_kwh_m2: 4.09, theoretical_pv_power_w: 58.0 }, 'daily')).toBe(58.0);
  });

  it('diario sin potencia del backend: no disponible (null), no un valor inventado', () => {
    expect(pvPowerFromRow({ daily_irradiance_kwh_m2: 4.09, theoretical_pv_power_w: null }, 'daily')).toBeNull();
  });

  it('horario: avg_irradiance_wm2 en W/m² × 17 %', () => {
    expect(pvPowerFromRow({ avg_irradiance_wm2: 600, avg_temperature_c: 25 }, 'hourly')).toBeCloseTo(102);
    expect(pvPowerFromRow({ avg_irradiance_wm2: null }, 'hourly')).toBeNull();
  });
});

describe('stationPrWarning (C16)', () => {
  it('marca la estación de Udenar como no apta para el PR', () => {
    expect(stationPrWarning([{ institution_name: 'Udenar' }])).toMatch(/no se usa para el Performance Ratio/);
  });
  it('no marca las demás', () => {
    expect(stationPrWarning([{ institution_name: 'HUDN' }, { institution_name: 'Mariana' }])).toBeNull();
    expect(stationPrWarning(undefined)).toBeNull();
  });
});

describe('WeatherStationDetails, render', () => {
  it('monta sin errores', async () => {
    global.fetch = vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({ results: [] }) }));
    const { container } = render(<WeatherStationDetails authToken="t" onLogout={() => {}} username="u"
      isSuperuser={false} navigateTo={() => {}} isSidebarMinimized={false} setIsSidebarMinimized={() => {}} />);
    await waitFor(() => expect(container.querySelector('header')).not.toBeNull());
  });
});

const mockFetchWeather = () => {
  global.fetch = vi.fn((url) => {
    const u = String(url);
    const body = u.includes('/api/institutions/') ? [{ id: 5, name: 'HUDN' }]
      : u.includes('/api/weather-stations/list/') ? { devices: [{ id: 11, name: 'Estación HUDN' }] }
      : u.includes('/api/data-availability/') ? {
        daily_monthly: { min_date: '2025-04-04', max_date: '2026-10-20' }, last_updated: null }
      : u.includes('/api/weather-station-indicators/') ? { results: [
        { date: '2026-10-02', time_range: 'daily', institution_name: 'HUDN', device_name: 'Estación HUDN',
          avg_temperature_c: null, daily_irradiance_kwh_m2: 4.1, daily_hsp_hours: 4.1,
          avg_wind_speed_kmh: 5.0, avg_humidity_pct: 70 },
      ] }
      : { results: [] };
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body),
      text: () => Promise.resolve(JSON.stringify(body)) });
  });
};

describe('WeatherStationDetails con una sede elegida', () => {
  it('temperatura sin dato: «No disponible» sin «°C», y el banner nombra la sede', async () => {
    mockFetchWeather();
    render(<WeatherStationDetails authToken={null} onLogout={() => {}} username="" isSuperuser={false}
      navigateTo={() => {}} isSidebarMinimized={false} setIsSidebarMinimized={() => {}} />);
    const select = await screen.findByLabelText('Institución');
    await waitFor(() => expect(within(select).getByText('HUDN')).toBeInTheDocument());
    fireEvent.change(select, { target: { value: '5' } });

    const temperatureCard = () => screen.queryAllByText('Temperatura Ambiente')
      .map((h) => h.closest('div.rounded-xl'))
      .find((c) => c && within(c).queryByText('No disponible'));
    await waitFor(() => expect(temperatureCard()).toBeTruthy());
    const card = temperatureCard();
    expect(within(card).queryByText('°C')).toBeNull();

    await waitFor(() => expect(screen.getByText(/HUDN · estaciones meteorológicas/)).toBeInTheDocument());
    expect(screen.queryByText(/Esta sede/)).toBeNull();
    expect(screen.queryByText(/10 días/)).toBeNull();
  });
});
