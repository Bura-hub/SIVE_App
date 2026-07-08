from django.db import models
from django.db.models import F
from django.utils import timezone
from django.core.validators import RegexValidator
from django.contrib.auth.models import User
import hashlib
import secrets
from datetime import timedelta


class UserProfile(models.Model):
    """
    Perfil extendido del usuario con funcionalidades de seguridad mejoradas
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    
    # Campos adicionales de seguridad
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    last_login_ip = models.GenericIPAddressField(null=True, blank=True, verbose_name="Última IP de acceso")
    last_activity = models.DateTimeField(auto_now=True, verbose_name="Última actividad")
    
    # Campos de seguridad
    failed_login_attempts = models.PositiveIntegerField(default=0, verbose_name="Intentos fallidos de login")
    locked_until = models.DateTimeField(null=True, blank=True, verbose_name="Bloqueado hasta")
    password_changed_at = models.DateTimeField(auto_now_add=True, verbose_name="Contraseña cambiada el")
    require_password_change = models.BooleanField(default=False, verbose_name="Requiere cambio de contraseña")
    
    # Validaciones personalizadas
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="El número de teléfono debe estar en formato: '+999999999'. Hasta 15 dígitos permitidos."
    )
    phone_number = models.CharField(validators=[phone_regex], max_length=17, blank=True, verbose_name="Número de teléfono")
    
    # Configuraciones de seguridad
    two_factor_enabled = models.BooleanField(default=False, verbose_name="2FA habilitado")
    notification_preferences = models.JSONField(default=dict, verbose_name="Preferencias de notificación")
    
    # Configuraciones de la aplicación
    theme_preference = models.CharField(max_length=20, default='light', verbose_name="Tema preferido")
    language = models.CharField(max_length=10, default='es', verbose_name="Idioma preferido")
    
    # Avatar y información personal
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True, verbose_name="Avatar")
    bio = models.TextField(max_length=500, blank=True, verbose_name="Biografía")
    date_of_birth = models.DateField(null=True, blank=True, verbose_name="Fecha de nacimiento")
    
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Última actualización")
    
    class Meta:
        verbose_name = 'Perfil de Usuario'
        verbose_name_plural = 'Perfiles de Usuario'
    
    def __str__(self):
        return f"Perfil de {self.user.username}"
    
    def is_locked(self):
        """Verifica si el usuario está bloqueado temporalmente"""
        if self.locked_until and timezone.now() < self.locked_until:
            return True
        return False
    
    def lock_account(self, duration_minutes=30):
        """Bloquea la cuenta temporalmente"""
        self.locked_until = timezone.now() + timedelta(minutes=duration_minutes)
        self.save(update_fields=['locked_until'])
    
    def unlock_account(self):
        """Desbloquea la cuenta"""
        self.locked_until = None
        self.failed_login_attempts = 0
        self.save(update_fields=['locked_until', 'failed_login_attempts'])
    
    def increment_failed_attempts(self):
        """Incrementa (atómicamente) el contador de intentos fallidos y bloquea al superar el umbral.

        Usa F() + UPDATE para evitar la condición de carrera del read-modify-write
        bajo intentos concurrentes.
        """
        type(self).objects.filter(pk=self.pk).update(
            failed_login_attempts=F('failed_login_attempts') + 1
        )
        self.refresh_from_db(fields=['failed_login_attempts'])
        if self.failed_login_attempts >= 5:  # Bloquear después de 5 intentos
            self.lock_account()
    
    def reset_failed_attempts(self):
        """Resetea el contador de intentos fallidos"""
        self.failed_login_attempts = 0
        self.save(update_fields=['failed_login_attempts'])
    



class AuthToken(models.Model):
    """
    Modelo de token de autenticación mejorado con expiración y metadatos
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='auth_tokens')
    key = models.CharField(max_length=64, unique=True, verbose_name="Clave del token")
    name = models.CharField(max_length=100, blank=True, verbose_name="Nombre del dispositivo")
    created = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    expires_at = models.DateTimeField(verbose_name="Fecha de expiración")
    last_used = models.DateTimeField(auto_now=True, verbose_name="Último uso")
    is_active = models.BooleanField(default=True, verbose_name="Token activo")
    
    # Metadatos del dispositivo
    user_agent = models.TextField(blank=True, verbose_name="User Agent")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="Dirección IP")
    device_type = models.CharField(max_length=50, blank=True, verbose_name="Tipo de dispositivo")

    # Token de refresco emparejado con esta sesión/dispositivo. Permite que el
    # logout invalide SOLO el refresh token de esta sesión (antes se usaba una
    # heurística por fecha que afectaba a otros dispositivos).
    refresh_token = models.ForeignKey(
        'RefreshToken', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='access_tokens', verbose_name="Token de refresco emparejado"
    )

    class Meta:
        verbose_name = 'Token de Autenticación'
        verbose_name_plural = 'Tokens de Autenticación'
        ordering = ['-created']
    
    def __str__(self):
        return f"Token para {self.user.username} - {self.name or 'Dispositivo'}"
    
    def is_expired(self):
        """Verifica si el token ha expirado"""
        return timezone.now() > self.expires_at
    
    def refresh_expiry(self, days=30):
        """Refresca la fecha de expiración del token"""
        self.expires_at = timezone.now() + timedelta(days=days)
        self.save(update_fields=['expires_at'])
    
    @classmethod
    def generate_key(cls):
        """Genera una nueva clave de token"""
        return secrets.token_hex(32)
    
    @classmethod
    def create_token(cls, user, name="", user_agent="", ip_address=None, days_valid=30, refresh_token=None):
        """Crea un nuevo token para un usuario, opcionalmente emparejado a un refresh token"""
        token = cls(
            user=user,
            key=cls.generate_key(),
            name=name,
            expires_at=timezone.now() + timedelta(days=days_valid),
            user_agent=user_agent,
            ip_address=ip_address,
            refresh_token=refresh_token
        )
        token.save()
        return token


class RefreshToken(models.Model):
    """
    Token de refresco para renovar tokens de acceso
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='refresh_tokens')
    token = models.CharField(max_length=64, unique=True, verbose_name="Token de refresco")
    created = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    expires_at = models.DateTimeField(verbose_name="Fecha de expiración")
    is_active = models.BooleanField(default=True, verbose_name="Token activo")
    
    class Meta:
        verbose_name = 'Token de Refresco'
        verbose_name_plural = 'Tokens de Refresco'
    
    def __str__(self):
        return f"Refresh token para {self.user.username}"
    
    def is_expired(self):
        """Verifica si el token de refresco ha expirado"""
        return timezone.now() > self.expires_at
    
    @classmethod
    def generate_token(cls):
        """Genera un nuevo token de refresco"""
        return secrets.token_hex(32)
    
    @classmethod
    def create_refresh_token(cls, user, days_valid=90):
        """Crea un nuevo token de refresco"""
        refresh_token = cls(
            user=user,
            token=cls.generate_token(),
            expires_at=timezone.now() + timedelta(days=days_valid)
        )
        refresh_token.save()
        return refresh_token


class LoginAttempt(models.Model):
    """
    Registro de intentos de login para auditoría y seguridad
    """
    SUCCESS = 'success'
    FAILED = 'failed'
    LOCKED = 'locked'
    
    STATUS_CHOICES = [
        (SUCCESS, 'Exitoso'),
        (FAILED, 'Fallido'),
        (LOCKED, 'Cuenta bloqueada'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='login_attempts', null=True, blank=True)
    username = models.CharField(max_length=150, verbose_name="Nombre de usuario")
    ip_address = models.GenericIPAddressField(verbose_name="Dirección IP")
    user_agent = models.TextField(blank=True, verbose_name="User Agent")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, verbose_name="Estado")
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Timestamp")
    failure_reason = models.CharField(max_length=200, blank=True, verbose_name="Razón del fallo")
    
    class Meta:
        verbose_name = 'Intento de Login'
        verbose_name_plural = 'Intentos de Login'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['username', 'timestamp']),
            models.Index(fields=['ip_address', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.username} - {self.status} - {self.timestamp}"
