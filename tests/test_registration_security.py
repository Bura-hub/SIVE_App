"""
Tests de seguridad del REGISTRO (bloque B de la auditoría del flujo "Crear una cuenta").

Cubren:
- Anti mass-assignment: is_staff/is_superuser enviados en el body NO se asignan.
- Email único case-insensitive -> 400/409.
- Contraseña que falla la política del servidor -> 400 con la clave 'password'.
- Longitudes mínimas (username>=3, first_name>=2, last_name>=2) rechazadas en el servidor.
- Rate limit real (429) en el registro (test aislado; limpia la caché).

Ejecutar en el contenedor:
  docker compose -f docker-compose.prod.yml exec backend python manage.py test tests.test_registration_security
"""
from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APIClient


# El rate limiting por IP interferiría con los múltiples POST de registro; se
# desactiva para las pruebas funcionales y se reactiva solo en el test de 429.
@override_settings(RATELIMIT_ENABLE=False)
class RegistrationSecurityTests(TestCase):
    # Contraseña que cumple AUTH_PASSWORD_VALIDATORS (>=12, may/min/dígito/especial,
    # sin patrones comunes/secuencias/repeticiones ni similitud con el usuario).
    STRONG_PASSWORD = 'Zephyr$Meadow7Blue'

    def setUp(self):
        self.client = APIClient()
        cache.clear()

    def _payload(self, **overrides):
        data = {
            'username': 'nuevo_usuario',
            'email': 'nuevo@sive.local',
            'first_name': 'Nuevo',
            'last_name': 'Usuario',
            'password': self.STRONG_PASSWORD,
            'confirm_password': self.STRONG_PASSWORD,
        }
        data.update(overrides)
        return data

    def _register(self, payload):
        return self.client.post('/auth/register/', payload, format='json')

    # ---- (a) anti mass-assignment ----
    def test_register_ignores_is_staff_and_is_superuser(self):
        payload = self._payload(is_staff=True, is_superuser=True)
        resp = self._register(payload)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)

        user = User.objects.get(username='nuevo_usuario')
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    # ---- (b) email único case-insensitive ----
    def test_duplicate_email_case_insensitive_is_rejected(self):
        User.objects.create_user(
            username='existente', email='dup@sive.local', password=self.STRONG_PASSWORD
        )
        payload = self._payload(username='otro', email='DUP@SIVE.LOCAL')
        resp = self._register(payload)
        self.assertIn(resp.status_code, (status.HTTP_400_BAD_REQUEST, status.HTTP_409_CONFLICT), resp.data)
        # No debe haberse creado el segundo usuario.
        self.assertFalse(User.objects.filter(username='otro').exists())

    # ---- (c) contraseña débil rechazada por el servidor ----
    def test_weak_password_returns_400_with_password_key(self):
        payload = self._payload(password='corta', confirm_password='corta')
        resp = self._register(payload)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', resp.data)

    # ---- (d) longitudes mínimas ----
    def test_short_username_is_rejected(self):
        payload = self._payload(username='ab')
        resp = self._register(payload)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('username', resp.data)

    def test_short_first_name_is_rejected(self):
        payload = self._payload(first_name='A')
        resp = self._register(payload)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('first_name', resp.data)

    def test_short_last_name_is_rejected(self):
        payload = self._payload(last_name='B')
        resp = self._register(payload)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('last_name', resp.data)

    # ---- registro válido de referencia ----
    def test_valid_registration_succeeds(self):
        resp = self._register(self._payload())
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertTrue(User.objects.filter(username='nuevo_usuario').exists())


class RegistrationRateLimitTest(TestCase):
    """
    Verifica que el rate limit del registro devuelve 429 (bug: sin block=True el
    decorador solo marcaba request.limited y dejaba pasar).

    Aislado y con la caché limpia: el conteo de django-ratelimit vive en la caché,
    así que un residuo de otro test lo volvería frágil. La tasa configurada es 3/h
    por IP; el 4.º POST dentro de la ventana debe ser 429.
    """
    STRONG_PASSWORD = 'Zephyr$Meadow7Blue'

    def setUp(self):
        self.client = APIClient()
        cache.clear()

    def tearDown(self):
        cache.clear()

    @override_settings(RATELIMIT_ENABLE=True)
    def test_registration_is_rate_limited_after_threshold(self):
        # Payloads inválidos (contraseñas que no coinciden) para no crear usuarios;
        # el chequeo de request.limited ocurre ANTES de validar, y el decorador
        # cuenta cada POST igualmente.
        payload = {
            'username': 'rl_user',
            'email': 'rl@sive.local',
            'first_name': 'Rate',
            'last_name': 'Limit',
            'password': self.STRONG_PASSWORD,
            'confirm_password': 'no-coincide',
        }
        # 3 permitidos (3/h), el 4.º limitado.
        for _ in range(3):
            resp = self.client.post('/auth/register/', payload, format='json')
            self.assertNotEqual(resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

        resp = self.client.post('/auth/register/', payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS, resp.data)
