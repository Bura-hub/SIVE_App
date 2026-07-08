# Importa el módulo de serializadores de Django REST Framework
from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from django.contrib.auth.models import User
from .models import UserProfile, AuthToken, RefreshToken, LoginAttempt
from .validators import CustomPasswordValidator
import ipaddress
import re

# ========================= Serializador de Solicitud de Login =========================

class LoginRequestSerializer(serializers.Serializer):
    # Campo de nombre de usuario (requerido)
    username = serializers.CharField(
        help_text="Nombre de usuario registrado",
        max_length=150
    )

    # Campo de contraseña del usuario (requerido)
    password = serializers.CharField(
        help_text="Contraseña del usuario",
        write_only=True,
        style={'input_type': 'password'}
    )

    # Campo opcional para recordar el dispositivo
    remember_device = serializers.BooleanField(
        default=False,
        help_text="Recordar este dispositivo para futuros logins"
    )

    class Meta:
        # Nombre de referencia para la documentación OpenAPI/Swagger
        ref_name = "LoginRequest"

    def validate(self, attrs):
        """
        Validación personalizada para el login
        """
        username = attrs.get('username')
        password = attrs.get('password')
        
        if username and password:
            # Verificar si el usuario existe
            try:
                user = User.objects.get(username=username)
                
                # Verificar si la cuenta está bloqueada
                try:
                    from .models import UserProfile
                    profile, created = UserProfile.objects.get_or_create(user=user)
                    if profile.is_locked():
                        raise serializers.ValidationError(
                            "Tu cuenta está temporalmente bloqueada debido a múltiples intentos fallidos. "
                            f"Intenta nuevamente después de {profile.locked_until.strftime('%H:%M')}."
                        )
                    
                    # Verificar si requiere cambio de contraseña
                    if profile.require_password_change:
                        raise serializers.ValidationError(
                            "Debes cambiar tu contraseña antes de continuar."
                        )
                except Exception as e:
                    # Si no se puede verificar el perfil, continuar
                    pass
                
                # Verificar si el usuario está activo
                if not user.is_active:
                    raise serializers.ValidationError(
                        "Tu cuenta ha sido desactivada. Contacta al administrador."
                    )
                
            except User.DoesNotExist:
                # No revelar si el usuario existe o no por seguridad
                pass
        
        return attrs


# ========================= Serializador de Respuesta de Login =========================

class LoginResponseSerializer(serializers.Serializer):
    # Token de autenticación generado tras el login exitoso
    access_token = serializers.CharField(help_text="Token de acceso para autenticación")
    
    # Token de refresco para renovar el token de acceso
    refresh_token = serializers.CharField(help_text="Token de refresco para renovar el token de acceso")
    
    # ID único del usuario autenticado
    user_id = serializers.IntegerField(help_text="ID del usuario")
    
    # Nombre de usuario autenticado
    username = serializers.CharField(help_text="Nombre de usuario")
    
    # Correo electrónico del usuario
    email = serializers.EmailField(help_text="Correo electrónico del usuario")
    
    # Indicador booleano que muestra si el usuario es superusuario
    is_superuser = serializers.BooleanField(help_text="Indica si es superusuario")
    
    # Fecha de expiración del token de acceso
    expires_in = serializers.IntegerField(help_text="Tiempo de expiración del token en segundos")
    
    # Información del perfil del usuario
    profile = serializers.SerializerMethodField(help_text="Información del perfil del usuario")
    
    # Configuraciones del usuario
    settings = serializers.SerializerMethodField(help_text="Configuraciones del usuario")

    class Meta:
        # Nombre de referencia para la documentación OpenAPI/Swagger
        ref_name = "LoginResponse"
    
    def get_profile(self, obj):
        """Obtiene información del perfil del usuario"""
        try:
            from .models import UserProfile
            profile = UserProfile.objects.get(user=obj)
            return {
                'avatar': profile.avatar.url if profile.avatar else None,
                'bio': profile.bio,
                'two_factor_enabled': profile.two_factor_enabled,
                'theme_preference': profile.theme_preference,
                'language': profile.language,
            }
        except UserProfile.DoesNotExist:
            return None
    
    def get_settings(self, obj):
        """Obtiene configuraciones del usuario"""
        try:
            from .models import UserProfile
            profile = UserProfile.objects.get(user=obj)
            return {
                'require_password_change': profile.require_password_change,
                'last_password_change': profile.password_changed_at,
                'created_at': profile.created_at,
            }
        except UserProfile.DoesNotExist:
            return None


# ========================= Serializador de Respuesta de Logout =========================

class LogoutResponseSerializer(serializers.Serializer):
    # Mensaje informativo al cerrar sesión correctamente
    detail = serializers.CharField(
        default="Logout exitoso",
        help_text="Mensaje de confirmación al cerrar sesión"
    )
    
    # Timestamp del logout
    logout_time = serializers.DateTimeField(
        default=timezone.now,
        help_text="Hora del logout"
    )

    class Meta:
        # Nombre de referencia para la documentación OpenAPI/Swagger
        ref_name = "LogoutResponse"


# ========================= Serializador de Refresh Token =========================

class RefreshTokenRequestSerializer(serializers.Serializer):
    # Token de refresco para renovar el token de acceso
    refresh_token = serializers.CharField(
        help_text="Token de refresco válido"
    )

    class Meta:
        ref_name = "RefreshTokenRequest"

    def validate_refresh_token(self, value):
        """
        Valida que el token de refresco sea válido
        """
        try:
            refresh_token = RefreshToken.objects.get(
                token=value,
                is_active=True
            )
            
            if refresh_token.is_expired():
                raise serializers.ValidationError("El token de refresco ha expirado")
            
            # Verificar que el usuario esté activo
            if not refresh_token.user.is_active:
                raise serializers.ValidationError("El usuario asociado al token no está activo")
            
            return value
            
        except RefreshToken.DoesNotExist:
            raise serializers.ValidationError("Token de refresco inválido")


class RefreshTokenResponseSerializer(serializers.Serializer):
    # Nuevo token de acceso
    access_token = serializers.CharField(help_text="Nuevo token de acceso")
    
    # Token de refresco (puede ser el mismo o uno nuevo)
    refresh_token = serializers.CharField(help_text="Token de refresco")
    
    # Nueva fecha de expiración
    expires_in = serializers.IntegerField(help_text="Tiempo de expiración en segundos")
    
    # Tipo de token
    token_type = serializers.CharField(default="Bearer", help_text="Tipo de token")

    class Meta:
        ref_name = "RefreshTokenResponse"


# ========================= Serializador de Cambio de Contraseña =========================

class ChangePasswordSerializer(serializers.Serializer):
    # Contraseña actual
    current_password = serializers.CharField(
        help_text="Contraseña actual del usuario",
        write_only=True,
        style={'input_type': 'password'}
    )
    
    # Nueva contraseña (la política de fortaleza se aplica en validate() vía
    # validate_password, usando AUTH_PASSWORD_VALIDATORS de settings)
    new_password = serializers.CharField(
        help_text="Nueva contraseña",
        write_only=True,
        style={'input_type': 'password'}
    )
    
    # Confirmación de la nueva contraseña
    confirm_password = serializers.CharField(
        help_text="Confirmación de la nueva contraseña",
        write_only=True,
        style={'input_type': 'password'}
    )

    class Meta:
        ref_name = "ChangePasswordRequest"

    def validate(self, attrs):
        """
        Valida que las contraseñas coincidan y que la actual sea correcta
        """
        new_password = attrs.get('new_password')
        confirm_password = attrs.get('confirm_password')
        current_password = attrs.get('current_password')
        
        if new_password != confirm_password:
            raise serializers.ValidationError("Las contraseñas no coinciden")
        
        # Verificar que la contraseña actual sea correcta
        user = self.context['request'].user
        if not user.check_password(current_password):
            raise serializers.ValidationError("La contraseña actual es incorrecta")
        
        # Verificar que la nueva contraseña sea diferente a la actual
        if user.check_password(new_password):
            raise serializers.ValidationError("La nueva contraseña debe ser diferente a la actual")

        # Aplicar la política de fortaleza (AUTH_PASSWORD_VALIDATORS: longitud 12,
        # CustomPasswordValidator, etc.). Antes el cambio de contraseña NO validaba
        # fortaleza (validators=[]), permitiendo contraseñas triviales.
        try:
            validate_password(new_password, user=user)
        except DjangoValidationError as e:
            raise serializers.ValidationError({'new_password': list(e.messages)})

        return attrs


# ========================= Serializador de Perfil de Usuario =========================

class UserProfileSerializer(serializers.ModelSerializer):
    # Información básica del usuario
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    
    # Campos adicionales del perfil
    phone_number = serializers.CharField(required=False, allow_blank=True)
    notification_preferences = serializers.JSONField(required=False, default=dict)
    
    class Meta:
        model = UserProfile
        fields = [
            'username', 'email', 'first_name', 'last_name',
            'avatar', 'bio', 'date_of_birth', 'phone_number',
            'two_factor_enabled', 'theme_preference', 'language', 
            'notification_preferences'
        ]
        read_only_fields = ['username', 'email', 'first_name', 'last_name']
    
    def update(self, instance, validated_data):
        """
        Actualiza el perfil y también los campos del usuario si es necesario
        """
        # Actualizar campos del perfil
        for attr, value in validated_data.items():
            if hasattr(instance, attr):
                setattr(instance, attr, value)
        
        # Actualizar campos del usuario si están presentes
        user_data = {}
        if 'first_name' in validated_data:
            user_data['first_name'] = validated_data['first_name']
        if 'last_name' in validated_data:
            user_data['last_name'] = validated_data['last_name']
        if 'email' in validated_data:
            user_data['email'] = validated_data['email']
        
        if user_data:
            for attr, value in user_data.items():
                setattr(instance.user, attr, value)
            instance.user.save()
        
        instance.save()
        return instance


# ========================= Serializador de Registro de Usuario =========================

class UserRegistrationSerializer(serializers.ModelSerializer):
    # Contraseña y confirmación (fortaleza validada en validate() vía validate_password)
    password = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'}
    )
    confirm_password = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'}
    )
    
    # Perfil del usuario
    profile = UserProfileSerializer(required=False)

    class Meta:
        model = User
        fields = [
            'username', 'email', 'first_name', 'last_name',
            'password', 'confirm_password', 'profile'
        ]
        extra_kwargs = {
            'password': {'write_only': True},
            'email': {'required': True}
        }

    def validate(self, attrs):
        """
        Validación personalizada para el registro
        """
        password = attrs.get('password')
        confirm_password = attrs.get('confirm_password')
        
        if password != confirm_password:
            raise serializers.ValidationError("Las contraseñas no coinciden")
        
        # Verificar que el email sea único
        email = attrs.get('email')
        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError("Este correo electrónico ya está registrado")

        # Aplicar la política de fortaleza completa (AUTH_PASSWORD_VALIDATORS:
        # longitud 12, CommonPasswordValidator, CustomPasswordValidator, etc.),
        # coherente con el resto del sistema. Antes se usaba una validación propia
        # más débil (mínimo 8, sin lista de comunes).
        temp_user = User(
            username=attrs.get('username', ''),
            email=email or '',
            first_name=attrs.get('first_name', ''),
            last_name=attrs.get('last_name', ''),
        )
        try:
            validate_password(password, user=temp_user)
        except DjangoValidationError as e:
            raise serializers.ValidationError({'password': list(e.messages)})

        return attrs

    def create(self, validated_data):
        """
        Crea el usuario y su perfil
        """
        profile_data = validated_data.pop('profile', {})
        confirm_password = validated_data.pop('confirm_password', None)
        
        # Crear el usuario
        user = User.objects.create_user(**validated_data)
        
        # Crear el perfil
        UserProfile.objects.create(user=user, **profile_data)
        
        return user


# ========================= Serializador de Información de Sesión =========================

class SessionInfoSerializer(serializers.Serializer):
    # Información del token actual
    token_info = serializers.SerializerMethodField()
    
    # Dispositivos activos
    active_devices = serializers.SerializerMethodField()
    
    # Últimos logins
    recent_logins = serializers.SerializerMethodField()

    class Meta:
        ref_name = "SessionInfo"

    def get_token_info(self, obj):
        """Obtiene información del token actual"""
        request = self.context.get('request')
        if request and hasattr(request, 'auth'):
            token = request.auth
            return {
                'created': token.created,
                'expires_at': token.expires_at,
                'last_used': token.last_used,
                'device_name': token.name,
                'ip_address': token.ip_address,
            }
        return None

    def get_active_devices(self, obj):
        """Obtiene dispositivos activos del usuario"""
        user = self.context.get('request').user
        active_tokens = AuthToken.objects.filter(
            user=user,
            is_active=True,
            expires_at__gt=timezone.now()
        )
        
        return [{
            'name': token.name or 'Dispositivo',
            'created': token.created,
            'last_used': token.last_used,
            'ip_address': token.ip_address,
            'device_type': token.device_type,
        } for token in active_tokens]

    def get_recent_logins(self, obj):
        """Obtiene los últimos intentos de login"""
        user = self.context.get('request').user
        recent_attempts = LoginAttempt.objects.filter(
            user=user
        ).order_by('-timestamp')[:10]
        
        return [{
            'timestamp': attempt.timestamp,
            'status': attempt.status,
            'ip_address': attempt.ip_address,
            'user_agent': attempt.user_agent,
        } for attempt in recent_attempts]


# ========================= Serializador de Imagen de Perfil =========================

class ProfileImageSerializer(serializers.Serializer):
    """
    Serializador para la gestión de imágenes de perfil
    """
    profile_image = serializers.ImageField(
        help_text="Imagen de perfil del usuario (JPG, PNG, WebP hasta 5MB)",
        max_length=255
    )
    
    class Meta:
        ref_name = "ProfileImage"
    
    def validate_profile_image(self, value):
        """
        Validación personalizada para la imagen de perfil
        """
        # Verificar tamaño máximo (5MB)
        if value.size > 5 * 1024 * 1024:  # 5MB en bytes
            raise serializers.ValidationError(
                "La imagen no puede ser mayor a 5MB"
            )
        
        # Verificar formato de archivo
        allowed_formats = ['image/jpeg', 'image/png', 'image/webp']
        if value.content_type not in allowed_formats:
            raise serializers.ValidationError(
                "Solo se permiten imágenes en formato JPG, PNG o WebP"
            )
        
        # Las dimensiones se validarán en la vista después de guardar
        # para evitar problemas con archivos temporales
        
        return value


class ProfileImageResponseSerializer(serializers.Serializer):
    """
    Serializador de respuesta para la imagen de perfil
    """
    profile_image_url = serializers.URLField(
        help_text="URL de la imagen de perfil"
    )
    profile_image_name = serializers.CharField(
        help_text="Nombre del archivo de la imagen"
    )
    uploaded_at = serializers.DateTimeField(
        help_text="Fecha y hora de subida de la imagen"
    )
    file_size = serializers.IntegerField(
        help_text="Tamaño del archivo en bytes"
    )
    dimensions = serializers.DictField(
        help_text="Dimensiones de la imagen (ancho x alto)"
    )