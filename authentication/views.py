# Importaciones necesarias para documentación de API con drf_spectacular
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiParameter

# Vista base para obtener tokens de autenticación
from rest_framework.authtoken.views import ObtainAuthToken

# Modelo de token de autenticación
from rest_framework.authtoken.models import Token

# Clases y utilidades de respuesta y vistas de DRF
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.viewsets import ViewSet
from rest_framework.exceptions import AuthenticationFailed

# Rate limiting
from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator

# Utilidades de Django
from django.utils import timezone
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

# No logging por seguridad

# Serializadores personalizados para login y logout
from .serializers import (
    LoginRequestSerializer,
    LoginResponseSerializer,
    LogoutResponseSerializer,
    RefreshTokenRequestSerializer,
    RefreshTokenResponseSerializer,
    ChangePasswordSerializer,
    UserProfileSerializer,
    UserRegistrationSerializer,
    SessionInfoSerializer,
    ProfileImageSerializer,
    ProfileImageResponseSerializer
)

# Modelos personalizados
from .models import UserProfile, AuthToken, RefreshToken, LoginAttempt

# Utilidades
import ipaddress
import logging
from datetime import timedelta
from django.conf import settings

logger = logging.getLogger(__name__)


def get_client_ip(request):
    """
    Obtiene la IP del cliente.

    Por defecto usa REMOTE_ADDR. La cabecera X-Forwarded-For es falsificable por
    el cliente, así que solo se usa si el despliegue está detrás de un proxy de
    confianza (settings.TRUST_X_FORWARDED_FOR=True), tomando el último salto
    (el añadido por el proxy más cercano). Evita el spoofing que permitía saltarse
    blacklist/rate-limit y falsear la auditoría.
    """
    if getattr(settings, 'TRUST_X_FORWARDED_FOR', False):
        xff = request.META.get('HTTP_X_FORWARDED_FOR')
        if xff:
            return xff.split(',')[-1].strip()
    return request.META.get('REMOTE_ADDR')


# ========================= Vistas de Autenticación =========================

@extend_schema(
    tags=["Autenticación"],
    request=LoginRequestSerializer,
    responses={200: LoginResponseSerializer, 400: "Bad Request", 429: "Too Many Requests"},
    examples=[
        OpenApiExample(
            "Ejemplo de login exitoso",
            value={
                "username": "admin",
                "password": "SecurePass123!",
                "remember_device": True
            }
        )
    ],
    description="Obtiene tokens de acceso y refresco para el usuario especificado."
)
@method_decorator(ratelimit(key='ip', rate='5/m', method='POST'), name='post')
class LoginView(ObtainAuthToken):
    """
    Vista de login mejorada con rate limiting, logging de seguridad y tokens de refresco
    """
    
    def post(self, request, *args, **kwargs):
        """
        Maneja la solicitud POST para iniciar sesión.

        Aplica el bloqueo por intentos fallidos (antes era código muerto:
        increment_failed_attempts nunca se llamaba) y registra cada intento en
        LoginAttempt para auditoría.
        """
        client_ip = get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        username = request.data.get('username', '')

        # Bloqueo previo: si el usuario existe y está bloqueado, cortar ANTES de autenticar.
        existing_user = User.objects.filter(username=username).first()
        if existing_user is not None:
            profile, _ = UserProfile.objects.get_or_create(user=existing_user)
            if profile.is_locked():
                return self._locked_response(existing_user, username, client_ip, user_agent, profile)

        try:
            serializer = self.serializer_class(data=request.data, context={'request': request})

            # Credenciales inválidas: contar el intento fallido (y bloquear al superar el umbral).
            if not serializer.is_valid():
                self._register_failed_attempt(existing_user, username, client_ip, user_agent)
                return Response({
                    'error': 'Credenciales inválidas',
                    'message': 'Usuario o contraseña incorrectos'
                }, status=status.HTTP_401_UNAUTHORIZED)

            user = serializer.validated_data['user']
            profile, _ = UserProfile.objects.get_or_create(user=user)

            # Doble verificación de bloqueo (por si el estado cambió tras la validación).
            if profile.is_locked():
                return self._locked_response(user, username, client_ip, user_agent, profile)

            # Verificar si requiere cambio de contraseña
            if profile.require_password_change:
                return Response({
                    'error': 'Cambio de contraseña requerido',
                    'message': 'Debes cambiar tu contraseña antes de continuar',
                    'require_password_change': True
                }, status=status.HTTP_403_FORBIDDEN)

            # Crear tokens
            access_token, refresh_token = self._create_tokens(user, request)

            # Login exitoso: resetear intentos y actualizar/auditar.
            profile.reset_failed_attempts()
            profile.last_login_ip = client_ip
            profile.last_activity = timezone.now()
            profile.save(update_fields=['last_login_ip', 'last_activity'])
            LoginAttempt.objects.create(
                user=user, username=username or user.username,
                ip_address=client_ip or '0.0.0.0', user_agent=user_agent,
                status=LoginAttempt.SUCCESS
            )

            # Preparar respuesta
            response_data = {
                'access_token': access_token.key,
                'refresh_token': refresh_token.token,
                'user_id': user.pk,
                'username': user.username,
                'email': user.email,
                'is_superuser': user.is_superuser,
                'expires_in': int((access_token.expires_at - timezone.now()).total_seconds()),
                'profile': self._get_user_profile(user),
                'settings': {
                    'require_password_change': profile.require_password_change,
                    'last_password_change': profile.password_changed_at,
                    'created_at': profile.created_at,
                }
            }

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception:
            logger.exception('Error interno en login')
            return Response({'error': 'Error interno del servidor'},
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _register_failed_attempt(self, user, username, client_ip, user_agent):
        """Registra un intento fallido: incrementa el contador (atómico, si el
        usuario existe) y crea el LoginAttempt de auditoría."""
        if user is not None:
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.increment_failed_attempts()
        LoginAttempt.objects.create(
            user=user, username=username or '', ip_address=client_ip or '0.0.0.0',
            user_agent=user_agent, status=LoginAttempt.FAILED,
            failure_reason='Credenciales inválidas'
        )

    def _locked_response(self, user, username, client_ip, user_agent, profile):
        """Registra el intento sobre cuenta bloqueada y devuelve 423."""
        LoginAttempt.objects.create(
            user=user, username=username or (user.username if user else ''),
            ip_address=client_ip or '0.0.0.0', user_agent=user_agent,
            status=LoginAttempt.LOCKED, failure_reason='Cuenta bloqueada'
        )
        return Response({
            'error': 'Cuenta bloqueada',
            'message': f'Tu cuenta está bloqueada hasta {profile.locked_until.strftime("%H:%M")}',
            'locked_until': profile.locked_until
        }, status=status.HTTP_423_LOCKED)

    def _create_tokens(self, user, request):
        """
        Crea tokens de acceso y refresco para el usuario (emparejados, para que el
        logout pueda invalidar solo el refresh token de esta sesión).
        """
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        client_ip = get_client_ip(request)
        device_name = self._detect_device_name(user_agent)

        # Crear refresco (90 días) primero, para emparejarlo con el token de acceso.
        refresh_token = RefreshToken.create_refresh_token(user, days_valid=90)

        # Crear token de acceso (30 días)
        access_token = AuthToken.create_token(
            user=user,
            name=device_name,
            user_agent=user_agent,
            ip_address=client_ip,
            days_valid=30,
            refresh_token=refresh_token
        )

        return access_token, refresh_token
    
    def _get_client_ip(self, request):
        """Obtiene la IP del cliente (delega en get_client_ip, que ignora
        X-Forwarded-For salvo tras un proxy de confianza)."""
        return get_client_ip(request)
    
    def _detect_device_name(self, user_agent):
        """
        Detecta el tipo de dispositivo basado en el User Agent
        """
        user_agent_lower = user_agent.lower()
        
        if 'mobile' in user_agent_lower or 'android' in user_agent_lower or 'iphone' in user_agent_lower:
            return 'Dispositivo móvil'
        elif 'tablet' in user_agent_lower or 'ipad' in user_agent_lower:
            return 'Tablet'
        elif 'windows' in user_agent_lower:
            return 'PC Windows'
        elif 'mac' in user_agent_lower:
            return 'Mac'
        elif 'linux' in user_agent_lower:
            return 'Linux'
        else:
            return 'Navegador web'
    
    def _get_user_profile(self, user):
        """
        Obtiene información del perfil del usuario
        """
        try:
            profile = user.profile
            return {
                'avatar': profile.avatar.url if profile.avatar else None,
                'bio': profile.bio,
                'two_factor_enabled': profile.two_factor_enabled,
                'theme_preference': profile.theme_preference,
                'language': profile.language,
            }
        except UserProfile.DoesNotExist:
            return None
    



@extend_schema(
    tags=["Autenticación"],
    responses={200: LogoutResponseSerializer},
    examples=[
        OpenApiExample(
            "Ejemplo de logout exitoso",
            value={"detail": "Logout exitoso", "logout_time": "2024-01-01T12:00:00Z"}
        )
    ],
    description="Invalida el token del usuario autenticado y cierra la sesión."
)
class LogoutView(APIView):
    """
    Vista de logout mejorada con logging y limpieza de tokens
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Maneja la solicitud POST para cerrar sesión
        """
        try:
            user = request.user
            client_ip = self._get_client_ip(request)
            
            # No logging por seguridad
            
            # Invalidar token actual
            if hasattr(request, 'auth') and request.auth:
                token = request.auth
                token.is_active = False
                token.save(update_fields=['is_active'])

                # Invalidar SOLO el refresh token emparejado con esta sesión.
                # Antes se usaba created__gte, que invalidaba las sesiones MÁS
                # nuevas de otros dispositivos.
                if token.refresh_token_id:
                    RefreshToken.objects.filter(pk=token.refresh_token_id).update(is_active=False)
            
            # Logout exitoso
            return Response({
                "detail": "Logout exitoso",
                "logout_time": timezone.now()
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            # No logging por seguridad
            return Response({
                "error": "Error durante el logout"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _get_client_ip(self, request):
        """Obtiene la IP del cliente (delega en get_client_ip, que ignora
        X-Forwarded-For salvo tras un proxy de confianza)."""
        return get_client_ip(request)


@extend_schema(
    tags=["Autenticación"],
    request=RefreshTokenRequestSerializer,
    responses={200: RefreshTokenResponseSerializer},
    description="Renueva el token de acceso usando un token de refresco válido."
)
@method_decorator(ratelimit(key='ip', rate='10/m', method='POST'), name='post')
class RefreshTokenView(APIView):
    """
    Vista para renovar tokens de acceso usando tokens de refresco
    """
    permission_classes = [AllowAny]

    def post(self, request):
        """
        Renueva el token de acceso
        """
        # La validación (raise_exception=True) va FUERA del try: un refresh token
        # inválido/expirado debe devolver 400 (vía DRF), no 500.
        serializer = RefreshTokenRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        refresh_token_value = serializer.validated_data['refresh_token']

        try:
            refresh_token = RefreshToken.objects.get(
                token=refresh_token_value,
                is_active=True
            )
            user = refresh_token.user

            # Verificar que el usuario esté activo
            if not user.is_active:
                return Response({
                    'error': 'Usuario inactivo'
                }, status=status.HTTP_403_FORBIDDEN)

            # Nuevo token de acceso, emparejado con el mismo refresh token
            new_access_token = AuthToken.create_token(
                user=user,
                name='Renovado',
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                ip_address=get_client_ip(request),
                days_valid=30,
                refresh_token=refresh_token
            )

            return Response({
                'access_token': new_access_token.key,
                'refresh_token': refresh_token_value,  # Mantener el mismo refresh token
                'expires_in': int((new_access_token.expires_at - timezone.now()).total_seconds()),
                'token_type': 'Bearer'
            }, status=status.HTTP_200_OK)

        except RefreshToken.DoesNotExist:
            return Response({
                'error': 'Token de refresco inválido'
            }, status=status.HTTP_400_BAD_REQUEST)

        except Exception:
            logger.exception('Error interno al refrescar token')
            return Response({
                'error': 'Error interno del servidor'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _get_client_ip(self, request):
        """Obtiene la IP del cliente (delega en get_client_ip, que ignora
        X-Forwarded-For salvo tras un proxy de confianza)."""
        return get_client_ip(request)


@extend_schema(
    tags=["Autenticación"],
    request=ChangePasswordSerializer,
    responses={200: "Contraseña cambiada exitosamente"},
    description="Permite al usuario cambiar su contraseña."
)
class ChangePasswordView(APIView):
    """
    Vista para cambiar contraseña
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Cambia la contraseña del usuario
        """
        # Validación fuera del try: contraseña actual incorrecta o nueva contraseña
        # débil deben devolver 400 (vía DRF), no 500.
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        try:
            user = request.user
            new_password = serializer.validated_data['new_password']
            
            # Cambiar contraseña
            user.set_password(new_password)
            user.save()
            
            # Actualizar campos del perfil relacionados con la contraseña
            try:
                profile = UserProfile.objects.get(user=user)
                profile.password_changed_at = timezone.now()
                profile.require_password_change = False
                profile.save(update_fields=['password_changed_at', 'require_password_change'])
            except UserProfile.DoesNotExist:
                # Si no existe el perfil, lo creamos
                profile = UserProfile.objects.create(
                    user=user,
                    password_changed_at=timezone.now(),
                    require_password_change=False
                )
            
            # Invalidar todos los tokens existentes
            AuthToken.objects.filter(user=user).update(is_active=False)
            RefreshToken.objects.filter(user=user).update(is_active=False)
            
            # No logging por seguridad
            
            return Response({
                'message': 'Contraseña cambiada exitosamente',
                'password_changed_at': profile.password_changed_at
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            # No logging por seguridad
            return Response({
                'error': 'Error al cambiar la contraseña'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    tags=["Autenticación"],
    responses={200: UserProfileSerializer},
    description="Obtiene y actualiza el perfil del usuario autenticado."
)
class UserProfileView(APIView):
    """
    Vista para gestionar el perfil del usuario
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Obtiene el perfil del usuario
        """
        try:
            profile, created = UserProfile.objects.get_or_create(user=request.user)
            serializer = UserProfileSerializer(profile)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception:
            logger.exception('Error al obtener el perfil')
            return Response({
                'error': 'Error al obtener el perfil'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def put(self, request):
        """
        Actualiza el perfil del usuario
        """
        try:
            profile, created = UserProfile.objects.get_or_create(user=request.user)
            
            # Preparar datos para actualización
            update_data = request.data.copy()
            
            # Manejar campos del usuario por separado
            user_fields = ['first_name', 'last_name', 'email']
            profile_fields = ['bio', 'date_of_birth', 'phone_number', 'theme_preference', 
                           'language', 'notification_preferences']
            
            # Actualizar campos del usuario
            user = request.user
            for field in user_fields:
                if field in update_data:
                    setattr(user, field, update_data[field])
            
            # Validar y guardar usuario
            user.full_clean()
            user.save()
            
            # Actualizar campos del perfil
            for field in profile_fields:
                if field in update_data:
                    setattr(profile, field, update_data[field])

            # Validar el perfil (p. ej. phone_regex) antes de guardar: save() por sí
            # solo no ejecuta los validadores del modelo.
            profile.full_clean()
            profile.save()

            # Serializar respuesta
            serializer = UserProfileSerializer(profile)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except ValidationError as e:
            return Response({
                'error': 'Datos de perfil inválidos',
                'details': e.message_dict if hasattr(e, 'message_dict') else e.messages
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception('Error al actualizar el perfil')
            return Response({
                'error': 'Error al actualizar el perfil'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    tags=["Autenticación"],
    responses={200: SessionInfoSerializer},
    description="Obtiene información sobre la sesión actual y dispositivos activos."
)
class SessionInfoView(APIView):
    """
    Vista para obtener información de la sesión
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Obtiene información de la sesión actual
        """
        try:
            serializer = SessionInfoSerializer(request.user, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            # No logging por seguridad
            return Response({
                'error': 'Error al obtener información de la sesión'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    tags=["Autenticación"],
    request=UserRegistrationSerializer,
    responses={201: "Usuario registrado exitosamente"},
    description="Registra un nuevo usuario en el sistema."
)
@method_decorator(ratelimit(key='ip', rate='3/h', method='POST'), name='post')
class UserRegistrationView(APIView):
    """
    Vista para registro de usuarios
    """
    permission_classes = [AllowAny]

    def post(self, request):
        """
        Registra un nuevo usuario
        """
        # Validación fuera del try: datos inválidos (contraseña débil, email
        # duplicado, etc.) deben devolver 400 (vía DRF), no 500.
        serializer = UserRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                user = serializer.save()
            return Response({
                'message': 'Usuario registrado exitosamente',
                'user_id': user.pk,
                'username': user.username,
                'email': user.email
            }, status=status.HTTP_201_CREATED)
        except Exception:
            logger.exception('Error al registrar el usuario')
            return Response({
                'error': 'Error al registrar el usuario'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    tags=["Autenticación"],
    responses={200: "Sesión cerrada en todos los dispositivos"},
    description="Cierra la sesión del usuario en todos los dispositivos."
)
class LogoutAllDevicesView(APIView):
    """
    Vista para cerrar sesión en todos los dispositivos
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Cierra sesión en todos los dispositivos
        """
        try:
            user = request.user
            
            # Invalidar todos los tokens del usuario
            AuthToken.objects.filter(user=user).update(is_active=False)
            RefreshToken.objects.filter(user=user).update(is_active=False)
            
            # Log del logout masivo
            # No logging por seguridad
            
            return Response({
                'message': 'Sesión cerrada en todos los dispositivos',
                'logout_time': timezone.now()
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            # No logging por seguridad
            return Response({
                'error': 'Error al cerrar sesión en todos los dispositivos'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ========================= Vista de Imagen de Perfil =========================

@extend_schema(
    tags=["Perfil de Usuario"],
    request=ProfileImageSerializer,
    responses={200: ProfileImageResponseSerializer, 400: "Bad Request", 401: "Unauthorized"},
    description="Gestiona la imagen de perfil del usuario autenticado."
)
@method_decorator(ratelimit(key='user', rate='10/h', method='POST'), name='post')
class ProfileImageView(APIView):
    """
    Vista para gestionar la imagen de perfil del usuario
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """
        Sube una nueva imagen de perfil
        """
        try:
            # Usar request.FILES para archivos subidos
            data = {'profile_image': request.FILES.get('profile_image')}
            if not data['profile_image']:
                return Response({
                    'error': 'No se proporcionó imagen de perfil'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            serializer = ProfileImageSerializer(data=data)
            serializer.is_valid(raise_exception=True)
            
            user = request.user
            profile, created = UserProfile.objects.get_or_create(user=user)
            
            # Eliminar imagen anterior si existe
            if profile.avatar:
                try:
                    import os
                    if os.path.exists(profile.avatar.path):
                        os.remove(profile.avatar.path)
                except Exception:
                    pass  # Ignorar errores al eliminar archivo anterior
            
            # Guardar nueva imagen
            profile.avatar = serializer.validated_data['profile_image']
            profile.save()
            
            # Validar dimensiones después de guardar
            try:
                from PIL import Image
                with Image.open(profile.avatar.path) as img:
                    width, height = img.size
                    
                    # Verificar dimensiones mínimas
                    if width < 100 or height < 100:
                        # Eliminar imagen si no cumple dimensiones
                        profile.avatar.delete()
                        profile.save()
                        return Response({
                            'error': 'La imagen debe tener al menos 100x100 píxeles'
                        }, status=status.HTTP_400_BAD_REQUEST)
                    
                    # Verificar dimensiones máximas
                    if width > 2000 or height > 2000:
                        # Eliminar imagen si no cumple dimensiones
                        profile.avatar.delete()
                        profile.save()
                        return Response({
                            'error': 'La imagen no puede ser mayor a 2000x2000 píxeles'
                        }, status=status.HTTP_400_BAD_REQUEST)
                        
            except Exception as dim_error:
                print(f"Error validando dimensiones: {dim_error}")
                # Continuar sin validación de dimensiones
                width, height = None, None
            
            # Construir respuesta con manejo seguro de dimensiones
            try:
                # Intentar obtener dimensiones de la imagen
                width = getattr(profile.avatar, 'width', None)
                height = getattr(profile.avatar, 'height', None)
                
                # Si no están disponibles, intentar obtenerlas del archivo
                if width is None or height is None:
                    try:
                        from PIL import Image
                        with Image.open(profile.avatar.path) as img:
                            width, height = img.size
                    except Exception as dim_error:
                        print(f"Error obteniendo dimensiones: {dim_error}")
                        width, height = None, None
                
                # Construir URL correcta para archivos media
                base_url = f"{request.scheme}://{request.get_host()}"
                media_url = f"{base_url}/media/{profile.avatar.name}"
                
                response_data = {
                    'profile_image_url': media_url,
                    'profile_image_name': profile.avatar.name,
                    'uploaded_at': profile.updated_at,
                    'file_size': profile.avatar.size,
                    'dimensions': {
                        'width': width,
                        'height': height
                    }
                }
            except Exception as response_error:
                print(f"Error construyendo respuesta: {response_error}")
                # Respuesta básica si hay error obteniendo dimensiones
                base_url = f"{request.scheme}://{request.get_host()}"
                media_url = f"{base_url}/media/{profile.avatar.name}"
                response_data = {
                    'profile_image_url': media_url,
                    'profile_image_name': profile.avatar.name,
                    'uploaded_at': profile.updated_at,
                    'file_size': profile.avatar.size,
                    'dimensions': {
                        'width': None,
                        'height': None
                    }
                }
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception:
            logger.exception('Error en ProfileImageView.post')
            return Response({
                'error': 'Error al subir la imagen de perfil'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def delete(self, request):
        """
        Elimina la imagen de perfil actual
        """
        try:
            user = request.user
            profile, created = UserProfile.objects.get_or_create(user=user)
            
            if profile.avatar:
                # Eliminar archivo físico
                try:
                    import os
                    if os.path.exists(profile.avatar.path):
                        os.remove(profile.avatar.path)
                except Exception:
                    pass
                
                # Limpiar campo en base de datos
                profile.avatar = None
                profile.save()
                
                return Response({
                    'message': 'Imagen de perfil eliminada exitosamente'
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'message': 'No hay imagen de perfil para eliminar'
                }, status=status.HTTP_404_NOT_FOUND)
                
        except Exception:
            logger.exception('Error en ProfileImageView.delete')
            return Response({
                'error': 'Error al eliminar la imagen de perfil'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def get(self, request):
        """
        Obtiene información de la imagen de perfil actual
        """
        try:
            user = request.user
            profile, created = UserProfile.objects.get_or_create(user=user)
            
            if profile.avatar:
                try:
                    # Intentar obtener dimensiones de la imagen
                    width = getattr(profile.avatar, 'width', None)
                    height = getattr(profile.avatar, 'height', None)
                    
                    # Si no están disponibles, intentar obtenerlas del archivo
                    if width is None or height is None:
                        try:
                            from PIL import Image
                            with Image.open(profile.avatar.path) as img:
                                width, height = img.size
                        except Exception as dim_error:
                            print(f"Error obteniendo dimensiones en GET: {dim_error}")
                            width, height = None, None
                    
                    response_data = {
                        'profile_image_url': request.build_absolute_uri(profile.avatar.url),
                        'profile_image_name': profile.avatar.name,
                        'uploaded_at': profile.updated_at,
                        'file_size': profile.avatar.size,
                        'dimensions': {
                            'width': width,
                            'height': height
                        }
                    }
                    return Response(response_data, status=status.HTTP_200_OK)
                except Exception as response_error:
                    print(f"Error construyendo respuesta en GET: {response_error}")
                    # Respuesta básica si hay error obteniendo dimensiones
                    response_data = {
                        'profile_image_url': request.build_absolute_uri(profile.avatar.url),
                        'profile_image_name': profile.avatar.name,
                        'uploaded_at': profile.updated_at,
                        'file_size': profile.avatar.size,
                        'dimensions': {
                            'width': None,
                            'height': None
                        }
                    }
                    return Response(response_data, status=status.HTTP_200_OK)
            else:
                # 200 con null para que el frontend no reciba 404 (evita error en consola)
                return Response({
                    'profile_image_url': None,
                    'profile_image_name': None,
                    'message': 'No hay imagen de perfil configurada'
                }, status=status.HTTP_200_OK)
                
        except Exception:
            logger.exception('Error en ProfileImageView.get')
            return Response({
                'error': 'Error al obtener información de la imagen de perfil'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


