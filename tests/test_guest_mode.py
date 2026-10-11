"""Modo invitado: lectura pública de las pantallas de datos.

Un visitante sin sesión ve en solo lectura los datos ya calculados (inicio, dashboard,
medidores, inversores, estaciones, datos externos de XM). Todo lo que escribe, dispara
trabajo (recalcular, sincronizar, tareas), toca la cuenta (perfil) o exporta reportes sigue
exigiendo sesión. El tráfico anónimo de lectura tiene su propio cupo (`anon_read`/`anon_xm`)
para no compartir ni agotar el cupo `anon` del login.
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from core.throttling import GuestAwareAnonRateThrottle

LOCMEM = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
                      'LOCATION': 'guest-mode-tests'}}

DENIED = (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)

# GET abiertos a invitados (pueden responder 400 por parámetros o 5xx si SCADA/XM no
# están en el entorno de pruebas, pero nunca 401/403).
PUBLIC_GET = [
    '/api/dashboard/summary/',
    '/api/dashboard/chart-data/',
    '/api/institutions/',
    '/api/electric-meters/list/',
    '/api/electric-meter-indicators/',
    '/api/inverter-indicators/',
    '/api/inverter-chart-data/',
    '/api/inverters/list/',
    '/api/weather-station-indicators/',
    '/api/weather-station-chart-data/',
    '/api/weather-stations/list/',
    '/api/data-availability/?institution_id=1&category=inverter',
    '/api/solar-indicators/institutions/',
    '/api/solar-indicators/?institution_id=1',
    '/api/external-energy/prices/',
    '/api/external-energy/savings/',
    '/api/external-energy/market-overview/',
    '/api/external-energy/generation/',
    '/api/external-energy/demand/',
    '/api/external-energy/emissions/',
    '/api/external-energy/exports/',
    '/api/external-energy/imports/',
]

# Lo que sigue cerrado al invitado.
CLOSED = [
    ('post', '/api/dashboard/calculate-kpis/'),
    ('post', '/api/dashboard/calculate-daily-data/'),
    ('post', '/api/electric-meters/calculate-new/'),
    ('post', '/api/inverters/calculate/'),
    ('post', '/api/weather-stations/calculate/'),
    ('post', '/api/reports/generate/'),
    ('get', '/api/reports/status/'),
    ('get', '/api/reports/download/'),
    ('get', '/api/reports/history/'),
    ('post', '/api/reports/delete/'),
    ('post', '/api/external-energy/sync/'),
    ('get', '/auth/profile/'),
    ('get', '/auth/sessions/'),
    ('get', '/scada/institutions/'),
    ('get', '/scada/connection-status/'),
    ('get', '/local/devices/'),
    ('get', '/local/measurements/'),
    ('post', '/local/sync-devices/'),
    ('get', '/tasks/active/'),
    ('get', '/tasks/history/'),
    ('post', '/tasks/fetch-historical/'),
    # Un método no seguro sobre una vista de lectura pública también exige sesión.
    ('post', '/api/dashboard/chart-data/'),
    ('delete', '/api/external-energy/prices/'),
]


def _xm_patch():
    """Evita llamar a la API real de XM desde las pruebas."""
    p = patch('external_energy.views.XMEnergyService')
    mock = p.start()
    svc = mock.return_value
    for name in ('fetch_energy_prices', 'fetch_generation_data', 'fetch_demand_data',
                 'fetch_emissions_data', 'fetch_exports_data', 'fetch_imports_data'):
        getattr(svc, name).return_value = []
    return p


@override_settings(CACHES=LOCMEM)
class GuestReadAccessTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.xm = _xm_patch()

    def tearDown(self):
        self.xm.stop()

    def test_public_get_endpoints_open_to_guest(self):
        for url in PUBLIC_GET:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertNotIn(response.status_code, DENIED, url)

    def test_guest_can_read_xm_prices(self):
        response = self.client.get('/api/external-energy/prices/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_closed_endpoints_reject_guest(self):
        for method, url in CLOSED:
            with self.subTest(method=method, url=url):
                response = getattr(self.client, method)(url)
                self.assertIn(response.status_code, DENIED, f'{method.upper()} {url}')

    def test_invalid_token_is_still_rejected_on_public_view(self):
        # Una cabecera con token inválido NO se trata como invitado: 401 como siempre,
        # para que el frontend detecte la sesión caducada.
        self.client.credentials(HTTP_AUTHORIZATION='Token no-existe')
        response = self.client.get('/api/institutions/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


@override_settings(CACHES=LOCMEM)
class GuestThrottleTests(APITestCase):
    RATES = {'anon': '2/day', 'user': '1000/day', 'anon_read': '3/min', 'anon_xm': '1/min'}

    def setUp(self):
        cache.clear()
        self.xm = _xm_patch()
        self.rates = patch.object(GuestAwareAnonRateThrottle, 'THROTTLE_RATES', self.RATES)
        self.rates.start()

    def tearDown(self):
        self.rates.stop()
        self.xm.stop()

    def test_guest_read_has_its_own_quota(self):
        # Más lecturas que el cupo `anon` (2/día): no lo consumen.
        for _ in range(3):
            self.assertNotEqual(self.client.get('/api/inverters/list/').status_code,
                                status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(self.client.get('/api/inverters/list/').status_code,
                         status.HTTP_429_TOO_MANY_REQUESTS)

    def test_xm_live_views_have_stricter_quota(self):
        self.assertEqual(self.client.get('/api/external-energy/demand/').status_code,
                         status.HTTP_200_OK)
        self.assertEqual(self.client.get('/api/external-energy/demand/?range=week').status_code,
                         status.HTTP_429_TOO_MANY_REQUESTS)

    def test_authenticated_user_not_limited_by_guest_quota(self):
        user = get_user_model().objects.create_user(
            username='lector', email='lector@example.com', password='clave-super-larga-123')
        self.client.force_authenticate(user=user)
        for _ in range(5):
            self.assertNotEqual(self.client.get('/api/inverters/list/').status_code,
                                status.HTTP_429_TOO_MANY_REQUESTS)
