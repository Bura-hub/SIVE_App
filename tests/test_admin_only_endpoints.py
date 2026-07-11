"""Tests de endurecimiento de endpoints "admin-only" (bloque C de la auditoría).

Las pestañas «Datos Externos» (external_energy) y «Exportar Reportes» (indicators) se
gatean en el frontend por `is_superuser`, pero ese gating es cosmético (localStorage). Estos
tests verifican el control REAL en el servidor: un usuario autenticado NO superusuario recibe
403, y un superusuario NO recibe 403 (200 o el código de negocio que corresponda).

El permiso aplicado es `core.permissions.IsSuperUser` (comprueba `is_superuser`, no `is_staff`).
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase


# `energy_prices` (y otras vistas de external_energy) usan @cache_page. Con la caché real,
# una respuesta 200 cacheada por el superusuario podría servirse a un usuario normal
# saltándose el chequeo de permiso. Se fuerza DummyCache para que @cache_page sea inerte y
# cada request ejecute realmente la vista y su permiso.
@override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.dummy.DummyCache'}})
class AdminOnlyEndpointsTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.normal_user = User.objects.create_user(
            username='usuario_normal', email='normal@example.com', password='clave-super-larga-123'
        )
        cls.super_user = User.objects.create_superuser(
            username='admin', email='admin@example.com', password='clave-super-larga-123'
        )

    # -------------------------------------------------------------------------
    # external_energy — pantalla «Datos Externos»
    # -------------------------------------------------------------------------
    def test_external_energy_prices_forbidden_for_normal_user(self):
        self.client.force_authenticate(user=self.normal_user)
        response = self.client.get('/api/external-energy/prices/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_external_energy_prices_allowed_for_superuser(self):
        self.client.force_authenticate(user=self.super_user)
        # Se mockea el servicio de XM para no golpear la API externa; la vista debe
        # responder 200 con datos vacíos aunque XM no esté disponible.
        with patch('external_energy.views.XMEnergyService') as mock_service:
            mock_service.return_value.fetch_energy_prices.return_value = []
            response = self.client.get('/api/external-energy/prices/')
        self.assertNotEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # -------------------------------------------------------------------------
    # indicators — pantalla «Exportar Reportes»
    # -------------------------------------------------------------------------
    def test_report_history_forbidden_for_normal_user(self):
        self.client.force_authenticate(user=self.normal_user)
        response = self.client.get('/api/reports/history/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_report_history_allowed_for_superuser(self):
        self.client.force_authenticate(user=self.super_user)
        response = self.client.get('/api/reports/history/')
        self.assertNotEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_report_generate_forbidden_for_normal_user(self):
        self.client.force_authenticate(user=self.normal_user)
        response = self.client.post('/api/reports/generate/', {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_report_generate_not_forbidden_for_superuser(self):
        self.client.force_authenticate(user=self.super_user)
        # Cuerpo vacío -> la vista responde 400 (campos requeridos), pero NUNCA 403.
        # Lo relevante es que el permiso deja pasar al superusuario.
        response = self.client.post('/api/reports/generate/', {}, format='json')
        self.assertNotEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # -------------------------------------------------------------------------
    # Sin autenticar -> 401/403 (nunca 200)
    # -------------------------------------------------------------------------
    def test_anonymous_is_rejected(self):
        response = self.client.get('/api/external-energy/prices/')
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )
