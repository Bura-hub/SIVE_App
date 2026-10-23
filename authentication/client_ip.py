"""
IP del cliente detrás del proxy de confianza.

En producción Apache reenvía a 127.0.0.1:3504 y Docker entrega la petición con REMOTE_ADDR igual
al gateway de la red (por ejemplo 172.44.0.1), el mismo para todos. La IP real es la que Apache
añade al final de X-Forwarded-For. Se usa la misma regla que DRF aplica al limitar por IP
(REST_FRAMEWORK['NUM_PROXIES']): con N proxies de confianza, el N-ésimo salto contando desde el
final. Lo que el cliente anteponga en la cabecera no cuenta, así que no puede falsear su IP.
Con NUM_PROXIES = 0 (despliegue sin proxy) se usa REMOTE_ADDR.
"""
from django.conf import settings


def get_client_ip(request):
    remote_addr = request.META.get('REMOTE_ADDR')
    num_proxies = (getattr(settings, 'REST_FRAMEWORK', {}) or {}).get('NUM_PROXIES') or 0
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if num_proxies <= 0 or not xff:
        return remote_addr
    saltos = [s.strip() for s in xff.split(',') if s.strip()]
    if not saltos:
        return remote_addr
    return saltos[-min(num_proxies, len(saltos))]


def ratelimit_key(group, request):
    """Clave de django-ratelimit: un cupo por cliente, no uno común para todo el proxy."""
    return get_client_ip(request)
