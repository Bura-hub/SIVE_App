"""
Bloqueo por intentos fallidos e IP del cliente detrás del proxy.

- Un bloqueo vencido deja el contador en cero: un fallo después no vuelve a bloquear 30 minutos.
- El intento que provoca el bloqueo informa la hora de desbloqueo, y la hora sale en la de Colombia.
- La IP del cliente es el último salto de X-Forwarded-For que añade el proxy de confianza (Apache),
  la misma regla de NUM_PROXIES de DRF: sin esto todos los usuarios comparten la IP del gateway de
  Docker, el cupo de 5 intentos por minuto es común a todos y la auditoría registra una sola IP.
"""
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings
from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from authentication.client_ip import get_client_ip
from authentication.middleware import IPSecurityMiddleware
from authentication.models import LoginAttempt, UserProfile

PASSWORD = 'Zephyr$Meadow7Blue'
GATEWAY = '172.44.0.1'


def _login(client, username, password, ip=None):
    extra = {'REMOTE_ADDR': GATEWAY}
    if ip:
        extra['HTTP_X_FORWARDED_FOR'] = ip
    return client.post('/auth/login/', {'username': username, 'password': password}, format='json', **extra)


@override_settings(RATELIMIT_ENABLE=False)
class BloqueoTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='analista', password=PASSWORD)
        self.profile, _ = UserProfile.objects.get_or_create(user=self.user)

    def test_bloqueo_vencido_reinicia_el_contador(self):
        self.profile.failed_login_attempts = 5
        self.profile.locked_until = timezone.now() - timedelta(minutes=1)
        self.profile.save()

        resp = _login(self.client, 'analista', 'Incorrecta9$x')

        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.failed_login_attempts, 1)
        self.assertFalse(self.profile.is_locked())

    def test_el_intento_que_bloquea_informa_la_hora(self):
        for _ in range(4):
            resp = _login(self.client, 'analista', 'Incorrecta9$x')
            self.assertNotIn('locked_until', resp.data)
        resp = _login(self.client, 'analista', 'Incorrecta9$x')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('locked_until', resp.data)

    def test_mensaje_de_bloqueo_en_hora_de_colombia(self):
        self.profile.lock_account()
        resp = _login(self.client, 'analista', PASSWORD)
        self.assertEqual(resp.status_code, status.HTTP_423_LOCKED)
        hora = timezone.localtime(self.profile.locked_until).strftime('%H:%M')
        self.assertIn(hora, resp.data['message'])


class ClientIpTests(TestCase):
    def setUp(self):
        self.rf = RequestFactory()

    def _req(self, xff=None):
        extra = {'REMOTE_ADDR': GATEWAY}
        if xff:
            extra['HTTP_X_FORWARDED_FOR'] = xff
        return self.rf.get('/', **extra)

    def test_toma_el_salto_que_anade_el_proxy(self):
        self.assertEqual(get_client_ip(self._req('190.1.2.3')), '190.1.2.3')

    def test_ignora_lo_que_el_cliente_antepone(self):
        self.assertEqual(get_client_ip(self._req('9.9.9.9, 190.1.2.3')), '190.1.2.3')

    def test_sin_cabecera_usa_remote_addr(self):
        self.assertEqual(get_client_ip(self._req()), GATEWAY)

    def test_sin_proxy_de_confianza_usa_remote_addr(self):
        rf = dict(settings.REST_FRAMEWORK, NUM_PROXIES=0)
        with override_settings(REST_FRAMEWORK=rf):
            self.assertEqual(get_client_ip(self._req('190.1.2.3')), GATEWAY)

    def test_el_middleware_usa_la_misma_regla(self):
        mw = IPSecurityMiddleware(lambda r: None)
        self.assertEqual(mw._get_client_ip(self._req('9.9.9.9, 190.1.2.3')), '190.1.2.3')

    @override_settings(RATELIMIT_ENABLE=False)
    def test_la_auditoria_registra_la_ip_del_cliente(self):
        _login(APIClient(), 'nadie', 'Incorrecta9$x', ip='190.1.2.3')
        self.assertEqual(LoginAttempt.objects.latest('id').ip_address, '190.1.2.3')


@override_settings(RATELIMIT_ENABLE=True)
class LimitePorClienteTests(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_el_cupo_de_intentos_es_de_cada_cliente(self):
        client = APIClient()
        for _ in range(5):
            self.assertNotEqual(_login(client, 'nadie', 'x', ip='190.1.2.3').status_code,
                                status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(_login(client, 'nadie', 'x', ip='190.1.2.3').status_code,
                         status.HTTP_429_TOO_MANY_REQUESTS)
        # Otro cliente detrás del mismo proxy no hereda el cupo agotado.
        self.assertNotEqual(_login(client, 'nadie', 'x', ip='181.4.5.6').status_code,
                            status.HTTP_429_TOO_MANY_REQUESTS)
