"""
Renovación del token de acceso (/auth/refresh/).

El serializador valida el token de refresco (existe y está activo, no ha expirado, su usuario está activo) y responde
400 en cualquier otro caso. La vista usa el token ya validado: antes lo volvía a buscar y repetía la comprobación del
usuario inactivo con un 403 que nunca se alcanzaba.

Se ejecuta con: python manage.py test tests.test_auth_refresh
"""

from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from authentication.models import AuthToken, RefreshToken

URL = '/auth/refresh/'


class RefreshTokenViewTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='refresco', password='x')
        self.refresh = RefreshToken.create_refresh_token(self.user)
        # Cada prueba parte sin el cupo de 10/min por IP del decorador ratelimit.
        patcher = mock.patch('django_ratelimit.decorators.is_ratelimited', return_value=False)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_valido_da_un_token_nuevo_emparejado(self):
        r = self.client.post(URL, {'refresh_token': self.refresh.token}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['refresh_token'], self.refresh.token)
        nuevo = AuthToken.objects.get(key=r.data['access_token'])
        self.assertEqual(nuevo.user, self.user)
        self.assertEqual(nuevo.refresh_token, self.refresh)

    def test_inexistente_da_400(self):
        r = self.client.post(URL, {'refresh_token': 'no-existe'}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_expirado_da_400(self):
        RefreshToken.objects.filter(pk=self.refresh.pk).update(expires_at=timezone.now() - timedelta(days=1))
        r = self.client.post(URL, {'refresh_token': self.refresh.token}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_usuario_inactivo_da_400_y_no_crea_token(self):
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        antes = AuthToken.objects.count()
        r = self.client.post(URL, {'refresh_token': self.refresh.token}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('no está activo', str(r.data))
        self.assertEqual(AuthToken.objects.count(), antes)

    def test_la_vista_no_vuelve_a_buscar_el_token(self):
        # El serializador hace la única consulta del token; la vista no repite RefreshToken.objects.get.
        with mock.patch.object(RefreshToken.objects, 'get', wraps=RefreshToken.objects.get) as get:
            r = self.client.post(URL, {'refresh_token': self.refresh.token}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(get.call_count, 1)
