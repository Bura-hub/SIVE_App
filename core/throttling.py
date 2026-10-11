"""Throttling del modo invitado.

El modo invitado abre en solo lectura (GET) las pantallas de datos. Para que no sea una puerta
de abuso, el tráfico anónimo de esas vistas tiene su propio cupo por IP (`anon_read`), y las
vistas que consultan XM en vivo un cupo más estricto (`anon_xm`). El resto del tráfico anónimo
(login, registro, refresco) sigue con el cupo `anon` de siempre, así que abrir la lectura no
afloja la protección del inicio de sesión. Los usuarios autenticados no pasan por aquí: los
limita `UserRateThrottle`.
"""

from rest_framework.permissions import SAFE_METHODS
from rest_framework.throttling import AnonRateThrottle


def _is_public_read_view(view):
    return any(getattr(p, 'public_read', False) for p in view.get_permissions())


class GuestAwareAnonRateThrottle(AnonRateThrottle):
    """AnonRateThrottle que usa el alcance `anon_read` en lecturas públicas (modo invitado)."""

    read_scope = 'anon_read'

    def allow_request(self, request, view):
        if request.user and request.user.is_authenticated:
            return True
        if request.method in SAFE_METHODS and _is_public_read_view(view):
            # Cupo propio (y clave de caché propia, que incluye el alcance) para la lectura
            # de invitados; no consume ni comparte el cupo `anon` del login.
            self.scope = self.read_scope
            self.rate = self.get_rate()
            self.num_requests, self.duration = self.parse_rate(self.rate)
        return super().allow_request(request, view)


class GuestXMAnonRateThrottle(GuestAwareAnonRateThrottle):
    """Cupo más estricto para invitados en las vistas que pueden llamar a la API de XM."""

    read_scope = 'anon_xm'
