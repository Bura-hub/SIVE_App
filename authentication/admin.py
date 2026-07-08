from django.contrib import admin
# No necesitamos BaseUserAdmin ya que no registramos el modelo User
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import UserProfile, AuthToken, RefreshToken, LoginAttempt
from django.utils import timezone
from datetime import timedelta


# El modelo User ya está registrado por Django, no necesitamos registrarlo aquí
@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """
    Admin para el perfil de usuario
    """
    list_display = [
        'user', 'two_factor_enabled', 'theme_preference', 'language',
        'created_at', 'updated_at'
    ]
    list_filter = [
        'two_factor_enabled', 'theme_preference', 'language', 'created_at'
    ]
    search_fields = ['user__username', 'user__email', 'bio']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Usuario', {'fields': ('user',)}),
        ('Información Personal', {
            'fields': ('avatar', 'bio', 'date_of_birth')
        }),
        ('Seguridad', {
            'fields': ('two_factor_enabled',)
        }),
        ('Preferencias', {
            'fields': ('theme_preference', 'language', 'notification_preferences')
        }),
        ('Fechas', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['enable_2fa', 'disable_2fa']

    def enable_2fa(self, request, queryset):
        """Habilita 2FA para perfiles seleccionados"""
        for profile in queryset:
            profile.two_factor_enabled = True
            profile.save(update_fields=['two_factor_enabled'])
        
        self.message_user(
            request,
            f'2FA habilitado para {queryset.count()} perfiles.'
        )
    enable_2fa.short_description = "Habilitar 2FA"
    
    def disable_2fa(self, request, queryset):
        """Deshabilita 2FA para perfiles seleccionados"""
        for profile in queryset:
            profile.two_factor_enabled = False
            profile.save(update_fields=['two_factor_enabled'])
        
        self.message_user(
            request,
            f'2FA deshabilitado para {queryset.count()} perfiles.'
        )
    disable_2fa.short_description = "Deshabilitar 2FA"


@admin.register(AuthToken)
class AuthTokenAdmin(admin.ModelAdmin):
    """
    Admin para tokens de autenticación
    """
    list_display = [
        'user', 'name', 'is_active', 'created', 'expires_at', 
        'last_used', 'ip_address', 'device_type'
    ]
    list_filter = [
        'is_active', 'created', 'expires_at', 'device_type'
    ]
    search_fields = ['user__username', 'name', 'key']
    readonly_fields = ['key', 'created', 'last_used']
    ordering = ['-created']
    
    fieldsets = (
        ('Información del Token', {
            'fields': ('user', 'key', 'name', 'is_active')
        }),
        ('Metadatos', {
            'fields': ('user_agent', 'ip_address', 'device_type')
        }),
        ('Fechas', {
            'fields': ('created', 'expires_at', 'last_used'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Filtra tokens expirados por defecto"""
        qs = super().get_queryset(request)
        return qs.filter(expires_at__gt=timezone.now())
    
    actions = ['invalidate_tokens', 'extend_expiry']
    
    def invalidate_tokens(self, request, queryset):
        """Invalida tokens seleccionados"""
        for token in queryset:
            token.is_active = False
            token.save(update_fields=['is_active'])
        
        self.message_user(
            request,
            f'{queryset.count()} tokens han sido invalidados.'
        )
    invalidate_tokens.short_description = "Invalidar tokens seleccionados"
    
    def extend_expiry(self, request, queryset):
        """Extiende la expiración de tokens seleccionados"""
        for token in queryset:
            token.refresh_expiry(days=30)
        
        self.message_user(
            request,
            f'La expiración de {queryset.count()} tokens ha sido extendida.'
        )
    extend_expiry.short_description = "Extender expiración"


@admin.register(RefreshToken)
class RefreshTokenAdmin(admin.ModelAdmin):
    """
    Admin para tokens de refresco
    """
    list_display = [
        'user', 'is_active', 'created', 'expires_at'
    ]
    list_filter = [
        'is_active', 'created', 'expires_at'
    ]
    search_fields = ['user__username', 'token']
    readonly_fields = ['token', 'created']
    ordering = ['-created']
    
    fieldsets = (
        ('Información del Token', {
            'fields': ('user', 'token', 'is_active')
        }),
        ('Fechas', {
            'fields': ('created', 'expires_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['invalidate_tokens']
    
    def invalidate_tokens(self, request, queryset):
        """Invalida tokens de refresco seleccionados"""
        for token in queryset:
            token.is_active = False
            token.save(update_fields=['is_active'])
        
        self.message_user(
            request,
            f'{queryset.count()} tokens de refresco han sido invalidados.'
        )
    invalidate_tokens.short_description = "Invalidar tokens seleccionados"


@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    """
    Admin para intentos de login (auditoría de seguridad)
    """
    list_display = [
        'username', 'ip_address', 'status', 'timestamp', 'user', 'failure_reason'
    ]
    list_filter = [
        'status', 'timestamp', 'ip_address'
    ]
    search_fields = ['username', 'ip_address', 'user_agent']
    readonly_fields = ['timestamp']
    ordering = ['-timestamp']
    
    fieldsets = (
        ('Información del Intento', {
            'fields': ('user', 'username', 'status')
        }),
        ('Detalles Técnicos', {
            'fields': ('ip_address', 'user_agent', 'failure_reason')
        }),
        ('Timestamp', {
            'fields': ('timestamp',),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        """No permitir crear intentos de login manualmente"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """No permitir modificar intentos de login"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Permitir eliminar para limpieza de logs"""
        return True
    
    actions = ['cleanup_old_attempts']
    
    def cleanup_old_attempts(self, request, queryset):
        """Limpia intentos de login antiguos"""
        cutoff_date = timezone.now() - timedelta(days=90)
        old_attempts = LoginAttempt.objects.filter(timestamp__lt=cutoff_date)
        count = old_attempts.count()
        old_attempts.delete()
        
        self.message_user(
            request,
            f'{count} intentos de login antiguos han sido eliminados.'
        )
    cleanup_old_attempts.short_description = "Limpiar intentos antiguos (90+ días)"


# Configuración del sitio de admin
admin.site.site_header = "MTE - SIVE - Administración"
admin.site.site_title = "MTE - SIVE Admin"
admin.site.index_title = "Panel de Administración"
