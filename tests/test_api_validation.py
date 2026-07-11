"""
Tests de validación de API y health check. Protegen los arreglos de las olas 2 y 3:
- resolve_indicators_date_range: ventana por defecto, tope de rango y formato inválido.
- fechas inválidas -> 400 (no 500) en los endpoints de gráficos.
- /health/: checks DUROS -> 200/503; BLANDOS -> 'degraded' pero 200.

Las vistas se invocan DIRECTAMENTE con (API)RequestFactory en vez de por URL: así se
evita el prefijo FORCE_SCRIPT_NAME (=/sive en prod) que reverse() incrusta y que el
cliente de test no resuelve. ALLOWED_HOSTS incluye 'testserver' para get_host().
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, RequestFactory, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from core.health_views import health_check
from indicators.services.formatting import auto_energy_unit, format_energy_value
from indicators.services.kpi import calculate_kpi_metrics, summarize_inverter_status
from indicators.tasks import colombia_day_range
from indicators.views import (
    ChartDataView,
    InverterChartDataView,
    InverterIndicatorsView,
    WeatherStationIndicatorsView,
    resolve_indicators_date_range,
    INDICATORS_DEFAULT_RANGE_DAYS,
)


class DateRangeResolverTests(TestCase):
    """Unit tests del helper de rango (función pura, sin HTTP)."""

    def test_sin_fechas_usa_ventana_por_defecto(self):
        start, end, err = resolve_indicators_date_range(None, None)
        self.assertIsNone(err)
        self.assertEqual((end - start).days, INDICATORS_DEFAULT_RANGE_DAYS)

    def test_formato_invalido_devuelve_error(self):
        start, _, err = resolve_indicators_date_range('2026-13-99', '2026-01-01')
        self.assertIsNotNone(err)
        self.assertIsNone(start)

    def test_rango_invertido_devuelve_error(self):
        _, _, err = resolve_indicators_date_range('2026-07-10', '2026-01-01')
        self.assertIsNotNone(err)

    def test_rango_excesivo_devuelve_error(self):
        # Supera INDICATORS_MAX_RANGE_DAYS (366): ~6 años.
        _, _, err = resolve_indicators_date_range('2020-01-01', '2026-01-01')
        self.assertIsNotNone(err)

    def test_rango_valido(self):
        start, end, err = resolve_indicators_date_range('2026-07-01', '2026-07-10')
        self.assertIsNone(err)
        self.assertEqual(start, date(2026, 7, 1))
        self.assertEqual(end, date(2026, 7, 10))


class EnergyFormattingTests(TestCase):
    """services/formatting.py: escalado de unidades de energía (usado por ChartDataView
    y ConsumptionSummaryView tras la extracción de la Ola 5)."""

    def test_auto_energy_unit(self):
        self.assertEqual(auto_energy_unit(500), ("kWh", 1))
        self.assertEqual(auto_energy_unit(5_000), ("MWh", 1_000))
        self.assertEqual(auto_energy_unit(5_000_000), ("GWh", 1_000_000))

    def test_format_kwh_escala_y_conserva_signo(self):
        self.assertEqual(format_energy_value(1_500, "kWh"), ("1.50", "MWh"))
        self.assertEqual(format_energy_value(-2_000_000, "kWh"), ("-2.00", "GWh"))
        self.assertEqual(format_energy_value(500, "kWh"), ("500.00", "kWh"))

    def test_format_watts_y_otras_unidades(self):
        self.assertEqual(format_energy_value(1_500, "W"), ("1.50", "kW"))
        self.assertEqual(format_energy_value(23.456, "°C"), ("23.5", "°C"))
        self.assertEqual(format_energy_value(80.0, "%RH"), ("80.0", "%"))


class KpiMetricsTests(TestCase):
    """services/kpi.py: calculate_kpi_metrics (extraído de ConsumptionSummaryView, Ola 5)."""

    def test_consumo_con_aumento(self):
        r = calculate_kpi_metrics(1500, 1000, "Consumo total", "kWh")
        self.assertEqual(r['value'], "1.50")
        self.assertEqual(r['unit'], "MWh")
        self.assertEqual(r['status'], "positivo")  # +50%
        self.assertIn("50.00%", r['change'])

    def test_balance_superavit_y_deficit(self):
        self.assertEqual(
            calculate_kpi_metrics(100, 50, "Balance", "kWh", is_balance=True)['description'], "Superávit")
        self.assertEqual(
            calculate_kpi_metrics(-100, 50, "Balance", "kWh", is_balance=True)['description'], "Déficit")

    def test_humedad_optima(self):
        r = calculate_kpi_metrics(50, 50, "Humedad", "%RH", is_humidity=True)
        self.assertEqual(r['status'], "optimo")

    def test_summarize_inverter_status(self):
        self.assertEqual(
            summarize_inverter_status([{'status': 'online'}, {'status': 'online'}])['status'], 'estable')
        r = summarize_inverter_status([{'status': 'online'}, {'status': 'offline'}])
        self.assertEqual(r['status'], 'critico')
        self.assertEqual(r['description'], '1 inactivos')
        self.assertEqual(r['active'], 1)
        self.assertEqual(summarize_inverter_status([])['status'], 'normal')


class ColombiaDayRangeTests(TestCase):
    """colombia_day_range: frontera [inicio 00:00, fin+1día 00:00) en hora de Bogotá.
    El límite superior EXCLUSIVO debe incluir el día 'end' completo (equivale al lookup
    date__date__range inclusivo). Bogotá no tiene DST, así que los timedelta son exactos."""

    def test_un_dia_abarca_24h(self):
        s, e = colombia_day_range(date(2026, 7, 1), date(2026, 7, 1))
        self.assertEqual(e - s, timedelta(days=1))
        self.assertEqual(s.hour, 0)

    def test_limite_superior_exclusivo_incluye_el_dia_final(self):
        s, e = colombia_day_range(date(2026, 7, 1), date(2026, 7, 10))
        self.assertEqual(e - s, timedelta(days=10))  # 10 días inclusivos (1..10)
        self.assertEqual(e.date(), date(2026, 7, 11))  # tope = inicio del día siguiente

    def test_es_timezone_aware(self):
        s, e = colombia_day_range(date(2026, 7, 1), date(2026, 7, 1))
        self.assertIsNotNone(s.tzinfo)
        self.assertIsNotNone(e.tzinfo)


@override_settings(ALLOWED_HOSTS=['testserver'])
class ChartDataValidationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='tester_chart', password='x')
        self.factory = APIRequestFactory()

    def _get(self, params, authed=True):
        req = self.factory.get('/api/dashboard/chart-data/', params)
        if authed:
            force_authenticate(req, user=self.user)
        return ChartDataView.as_view()(req)

    def test_fecha_invalida_da_400(self):
        self.assertEqual(self._get({'start_date': '2026-13-99', 'end_date': '2026-01-01'}).status_code, 400)

    def test_rango_invertido_da_400(self):
        self.assertEqual(self._get({'start_date': '2026-07-10', 'end_date': '2026-01-01'}).status_code, 400)

    def test_valido_da_200(self):
        self.assertEqual(self._get({'start_date': '2026-07-01', 'end_date': '2026-07-10'}).status_code, 200)

    def test_sin_auth_no_autorizado(self):
        self.assertIn(self._get({}, authed=False).status_code, (401, 403))


@override_settings(ALLOWED_HOSTS=['testserver'])
class InverterChartDataValidationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='tester_inv', password='x')
        self.factory = APIRequestFactory()

    def _get(self, params):
        req = self.factory.get('/api/inverter-chart-data/', params)
        force_authenticate(req, user=self.user)
        return InverterChartDataView.as_view()(req)

    def test_falta_institution_da_400(self):
        self.assertEqual(self._get({}).status_code, 400)

    def test_fecha_invalida_da_400(self):
        self.assertEqual(self._get({'institution_id': '1', 'start_date': 'bad'}).status_code, 400)

    def test_valido_da_200(self):
        self.assertEqual(self._get({'institution_id': '1'}).status_code, 200)


@override_settings(ALLOWED_HOSTS=['testserver'])
class InverterIndicatorsViewTests(TestCase):
    """Contrato de InverterIndicatorsView (exige institution_id; usa apply_device_filter)."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(username='tii', password='x')
        self.factory = APIRequestFactory()

    def _get(self, params):
        req = self.factory.get('/api/inverter-indicators/', params)
        force_authenticate(req, user=self.user)
        return InverterIndicatorsView.as_view()(req)

    def test_falta_institution_da_400(self):
        self.assertEqual(self._get({}).status_code, 400)

    def test_valido_da_200(self):
        self.assertEqual(self._get({'institution_id': '1'}).status_code, 200)

    def test_device_id_entero_y_scada_id(self):
        # Ambas ramas de apply_device_filter (dígito -> device_id; texto -> scada_id).
        self.assertEqual(self._get({'institution_id': '1', 'device_id': '5'}).status_code, 200)
        self.assertEqual(self._get({'institution_id': '1', 'device_id': 'abc-uuid'}).status_code, 200)


@override_settings(ALLOWED_HOSTS=['testserver'])
class WeatherIndicatorsViewTests(TestCase):
    """Contrato de WeatherStationIndicatorsView (NO exige institución; valida time_range)."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(username='twi', password='x')
        self.factory = APIRequestFactory()

    def _get(self, params):
        req = self.factory.get('/api/weather-station-indicators/', params)
        force_authenticate(req, user=self.user)
        return WeatherStationIndicatorsView.as_view()(req)

    def test_time_range_invalido_da_400(self):
        self.assertEqual(self._get({'time_range': 'bogus'}).status_code, 400)

    def test_sin_params_da_200(self):
        self.assertEqual(self._get({}).status_code, 200)


@override_settings(ALLOWED_HOSTS=['testserver'])
class HealthCheckTests(TestCase):
    def test_health_responde_200_con_checks_duros_ok(self):
        req = RequestFactory().get('/health/')
        resp = health_check(req)
        self.assertEqual(resp.status_code, 200)
        import json
        checks = json.loads(resp.content)['checks']
        self.assertEqual(checks['database'], 'ok')
        self.assertEqual(checks['cache'], 'ok')
        self.assertIn('data_freshness', checks)
