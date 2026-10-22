from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APITestCase

DASHBOARD_URL = '/api/dashboard/summary/'


class DashboardSummaryCacheTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(
            username='tester', password='pw12345'
        )

    def tearDown(self):
        cache.clear()

    def test_guest_reads_cached_summary(self):
        """Modo invitado: sin token se lee el resumen de flota (lectura pública) desde la caché."""
        cache.set('dashboard:summary:v1', {'totalConsumption': {'value': '123'}}, 300)
        with patch('indicators.views.scada_client') as mock_scada:
            response = self.client.get(DASHBOARD_URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['totalConsumption']['value'], '123')
        mock_scada.get_token.assert_not_called()

    def test_invalid_token_gets_401_and_never_cached_data(self):
        """Un token inválido NO se trata como invitado: 401, sin datos cacheados."""
        cache.set('dashboard:summary:v1', {'totalConsumption': {'value': 'SECRETO'}}, 300)
        self.client.credentials(HTTP_AUTHORIZATION='Token no-existe')
        response = self.client.get(DASHBOARD_URL)
        self.assertEqual(response.status_code, 401)

    def test_authenticated_hit_short_circuits_before_scada(self):
        """En cache-hit se devuelven los datos SIN llamar a SCADA."""
        payload = {'totalConsumption': {'value': '123'}, 'hasData': True}
        cache.set('dashboard:summary:v1', payload, 300)
        self.client.force_authenticate(user=self.user)
        with patch('indicators.views.scada_client') as mock_scada:
            response = self.client.get(DASHBOARD_URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['totalConsumption']['value'], '123')
        mock_scada.get_token.assert_not_called()

    def test_titulo_del_kpi_de_inversores(self):
        """El backend manda «Inversores con datos» (C12: con lecturas en las últimas 24 h), no «activos»."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(DASHBOARD_URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['activeInverters']['title'], 'Inversores con datos')
