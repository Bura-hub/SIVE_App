"""
Tests de seguridad de autenticación (Fase 2).

Cubren las correcciones:
- C4a: el bloqueo por intentos fallidos ahora SÍ se activa (increment_failed_attempts
  cableado) y cada intento queda auditado en LoginAttempt.
- C4b: un token de una cuenta bloqueada es rechazado por CustomTokenAuthentication.
- A2: cambio de contraseña y registro validan la política de fortaleza.
- #5: contraseña débil/incorrecta devuelve 400, no 500.
- #6: el logout invalida SOLO el refresh token de la sesión actual.

Ejecutar en el contenedor:
  docker compose -f docker-compose.prod.yml exec backend python manage.py test tests.test_auth_security
"""
from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APIClient

from authentication.models import UserProfile, RefreshToken, LoginAttempt


# El rate limiting por IP interferiría con los múltiples POST de login de los tests.
@override_settings(RATELIMIT_ENABLE=False)
class AuthSecurityTests(TestCase):
    # Contraseñas que cumplen AUTH_PASSWORD_VALIDATORS (>=12, may/min/dígito/especial,
    # sin patrones comunes/secuencias/repeticiones ni similitud con el usuario).
    PASSWORD = 'Zephyr$Meadow7Blue'
    NEW_PASSWORD = 'Violet#River9Dawn'

    def setUp(self):
        self.client = APIClient()
        self.username = 'analyst'
        self.user = User.objects.create_user(
            username=self.username, email='analyst@sive.local', password=self.PASSWORD
        )
        self.profile, _ = UserProfile.objects.get_or_create(user=self.user)

    def _login(self, password):
        return self.client.post(
            '/auth/login/',
            {'username': self.username, 'password': password},
            format='json',
        )

    # ---- C4a: bloqueo por intentos fallidos ----
    def test_account_locks_after_five_failed_attempts(self):
        for _ in range(5):
            resp = self._login('WrongPassword9$')
            self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

        self.profile.refresh_from_db()
        self.assertGreaterEqual(self.profile.failed_login_attempts, 5)
        self.assertTrue(self.profile.is_locked())

        # Auditoría: 5 intentos FAILED registrados
        self.assertEqual(
            LoginAttempt.objects.filter(username=self.username, status=LoginAttempt.FAILED).count(),
            5,
        )

        # Aun con la contraseña correcta, la cuenta bloqueada devuelve 423
        resp = self._login(self.PASSWORD)
        self.assertEqual(resp.status_code, status.HTTP_423_LOCKED)

    def test_successful_login_resets_and_audits(self):
        self._login('WrongPassword9$')
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.failed_login_attempts, 1)

        resp = self._login(self.PASSWORD)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('access_token', resp.data)

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.failed_login_attempts, 0)
        self.assertTrue(
            LoginAttempt.objects.filter(user=self.user, status=LoginAttempt.SUCCESS).exists()
        )

    # ---- C4b: token de cuenta bloqueada rechazado ----
    def test_locked_account_token_is_rejected(self):
        resp = self._login(self.PASSWORD)
        token = resp.data['access_token']

        self.profile.lock_account()

        self.client.credentials(HTTP_AUTHORIZATION='Token ' + token)
        resp2 = self.client.get('/auth/profile/', format='json')
        self.assertEqual(resp2.status_code, status.HTTP_401_UNAUTHORIZED)

    # ---- A2 / #5: fortaleza de contraseña ----
    def test_change_password_rejects_weak(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(
            '/auth/change-password/',
            {'current_password': self.PASSWORD, 'new_password': 'weak', 'confirm_password': 'weak'},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_change_password_accepts_strong(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(
            '/auth/change-password/',
            {
                'current_password': self.PASSWORD,
                'new_password': self.NEW_PASSWORD,
                'confirm_password': self.NEW_PASSWORD,
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_change_password_wrong_current_returns_400(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(
            '/auth/change-password/',
            {
                'current_password': 'NotMyPassword9$',
                'new_password': self.NEW_PASSWORD,
                'confirm_password': self.NEW_PASSWORD,
            },
            format='json',
        )
        # Antes devolvía 500 (ValidationError atrapado por except Exception)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_registration_rejects_weak_password(self):
        resp = self.client.post(
            '/auth/register/',
            {
                'username': 'newbie',
                'email': 'newbie@sive.local',
                'password': 'short',
                'confirm_password': 'short',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # ---- #6: logout solo invalida la sesión actual ----
    def test_logout_only_invalidates_current_session_refresh(self):
        resp_a = self._login(self.PASSWORD)
        token_a = resp_a.data['access_token']
        refresh_a = resp_a.data['refresh_token']

        resp_b = self._login(self.PASSWORD)
        refresh_b = resp_b.data['refresh_token']

        self.client.credentials(HTTP_AUTHORIZATION='Token ' + token_a)
        resp_logout = self.client.post('/auth/logout/', {}, format='json')
        self.assertEqual(resp_logout.status_code, status.HTTP_200_OK)

        # El refresh de la sesión A queda inactivo; el de B (más nueva) sigue activo
        self.assertFalse(RefreshToken.objects.get(token=refresh_a).is_active)
        self.assertTrue(RefreshToken.objects.get(token=refresh_b).is_active)
