from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.utils import timezone
from .models import AuthToken
from django.contrib.auth.models import User


class CustomTokenAuthentication(TokenAuthentication):
    """
    Clase de autenticación personalizada que utiliza el modelo AuthToken
    con validación de expiración y metadatos del dispositivo
    """
    model = AuthToken
    
    def authenticate_credentials(self, key):
        """
        Autentica las credenciales del token.

        Nota de seguridad: los AuthenticationFailed (token expirado, usuario
        inactivo, cuenta bloqueada) DEBEN propagarse. Antes iban dentro de un
        `except Exception: pass`/`except Exception` genérico que (a) se tragaba
        el bloqueo de cuenta y (b) filtraba str(e) al cliente. Cualquier error
        inesperado ahora falla cerrado (500), no concede acceso.
        """
        from .models import UserProfile

        try:
            # Buscar el token en la base de datos
            token = self.model.objects.select_related('user').get(
                key=key,
                is_active=True
            )
        except self.model.DoesNotExist:
            raise AuthenticationFailed('Token inválido')

        # Verificar si el token ha expirado
        if token.is_expired():
            # Marcar el token como inactivo
            token.is_active = False
            token.save(update_fields=['is_active'])
            raise AuthenticationFailed('Token expirado')

        # Verificar que el usuario esté activo
        if not token.user.is_active:
            raise AuthenticationFailed('Usuario inactivo')

        # Verificar si la cuenta está bloqueada (el bloqueo SÍ debe cortar el acceso)
        profile, _ = UserProfile.objects.get_or_create(user=token.user)
        if profile.is_locked():
            raise AuthenticationFailed('Cuenta bloqueada temporalmente')

        # Actualizar metadatos de uso (no crítico para la decisión de auth)
        token.last_used = timezone.now()
        token.save(update_fields=['last_used'])
        profile.last_activity = timezone.now()
        profile.save(update_fields=['last_activity'])

        return (token.user, token)
    
    def authenticate_header(self, request):
        """
        Retorna el header de autenticación para el esquema OpenAPI
        """
        return 'Token realm="api"'
