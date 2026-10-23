from django.utils.deprecation import MiddlewareMixin
from django.http import HttpResponse
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
import logging
from .client_ip import get_client_ip

logger = logging.getLogger('security')


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Middleware para agregar headers de seguridad HTTP
    """
    
    def process_response(self, request, response):
        """
        Agrega headers de seguridad a la respuesta
        """
        # Headers de seguridad básicos
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Content Security Policy
        csp_policy = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self' ws: wss:; "
            "frame-ancestors 'none';"
        )
        response['Content-Security-Policy'] = csp_policy
        
        # Headers adicionales de seguridad
        response['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        
        return response


class UserActivityMiddleware(MiddlewareMixin):
    """
    Middleware para rastrear la actividad del usuario
    """
    
    def process_request(self, request):
        """
        Registra la actividad del usuario en cada request
        """
        if hasattr(request, 'user') and request.user.is_authenticated:
            try:
                # Obtener o crear el perfil del usuario
                from .models import UserProfile
                profile, created = UserProfile.objects.get_or_create(user=request.user)
                
                # Actualizar timestamp de última actividad
                profile.last_activity = timezone.now()
                profile.save(update_fields=['last_activity'])
                
                # Registrar actividad en caché para análisis en tiempo real
                cache_key = f"user_activity_{request.user.id}"
                cache.set(cache_key, timezone.now(), 300)  # 5 minutos
            except Exception as e:
                logger.warning(f"Error actualizando actividad del usuario {request.user.id}: {str(e)}")
        
        return None


class IPSecurityMiddleware(MiddlewareMixin):
    """
    Middleware para medidas de seguridad basadas en IP
    """
    
    def process_request(self, request):
        """
        Implementa medidas de seguridad basadas en IP
        """
        client_ip = self._get_client_ip(request)
        
        # Verificar si la IP está en lista negra
        if self._is_ip_blacklisted(client_ip):
            logger.warning(f"Request bloqueado desde IP en lista negra: {client_ip}")
            return HttpResponse(
                'Acceso denegado desde esta IP',
                status=403,
                content_type='text/plain'
            )
        
        # Verificar rate limiting por IP
        if not self._check_ip_rate_limit(client_ip):
            logger.warning(f"Rate limit excedido para IP: {client_ip}")
            return HttpResponse(
                'Demasiadas solicitudes desde esta IP',
                status=429,
                content_type='text/plain'
            )
        
        return None
    
    def _get_client_ip(self, request):
        """IP del cliente con la regla del proxy de confianza (authentication/client_ip.py).
        El primer salto de X-Forwarded-For lo escribe el cliente y permitía falsear la IP."""
        return get_client_ip(request)
    
    def _is_ip_blacklisted(self, ip):
        """
        Verifica si una IP está en la lista negra
        """
        # Implementar lógica de lista negra (por ahora, solo ejemplo)
        blacklisted_ips = getattr(settings, 'BLACKLISTED_IPS', [])
        return ip in blacklisted_ips
    
    def _check_ip_rate_limit(self, ip):
        """
        Verifica el rate limiting por IP
        """
        cache_key = f"ip_rate_limit_{ip}"
        request_count = cache.get(cache_key, 0)
        
        # Permitir máximo 1000 requests por hora por IP
        if request_count >= 1000:
            return False
        
        # Incrementar contador
        cache.set(cache_key, request_count + 1, 3600)  # 1 hora
        return True


class RequestLoggingMiddleware(MiddlewareMixin):
    """
    Middleware para logging detallado de requests
    """
    
    def process_request(self, request):
        """
        Registra información del request
        """
        # Solo loggear requests autenticados para evitar spam
        if hasattr(request, 'user') and request.user.is_authenticated:
            logger.info(
                f"Request: {request.method} {request.path} "
                f"User: {request.user.username} "
                f"IP: {self._get_client_ip(request)} "
                f"User-Agent: {request.META.get('HTTP_USER_AGENT', 'N/A')}"
            )
        
        return None
    
    def process_response(self, request, response):
        """
        Registra información de la respuesta
        """
        if hasattr(request, 'user') and request.user.is_authenticated:
            logger.info(
                f"Response: {request.method} {request.path} "
                f"Status: {response.status_code} "
                f"User: {request.user.username}"
            )
        
        return response
    
    def _get_client_ip(self, request):
        """IP del cliente con la regla del proxy de confianza (authentication/client_ip.py).
        El primer salto de X-Forwarded-For lo escribe el cliente y permitía falsear la IP."""
        return get_client_ip(request)


class SessionSecurityMiddleware(MiddlewareMixin):
    """
    Middleware para mejorar la seguridad de las sesiones
    """
    
    def process_request(self, request):
        """
        Implementa medidas de seguridad para sesiones
        """
        if hasattr(request, 'user') and request.user.is_authenticated:
            # Verificar si la sesión es sospechosa
            if self._is_suspicious_session(request):
                logger.warning(
                    f"Sesión sospechosa detectada para usuario: {request.user.username}"
                )
                # Forzar logout o requerir re-autenticación
                # request.user.logout()  # Implementar según tu lógica
        
        return None
    
    def _is_suspicious_session(self, request):
        """
        Detecta sesiones sospechosas
        """
        try:
            # Obtener el perfil del usuario
            from .models import UserProfile
            profile, created = UserProfile.objects.get_or_create(user=request.user)
            
            # Verificar cambios de IP
            current_ip = self._get_client_ip(request)
            last_ip = profile.last_login_ip
            
            if last_ip and current_ip != last_ip:
                # Cambio de IP detectado
                return True
        except Exception as e:
            logger.warning(f"Error verificando sesión sospechosa para usuario {request.user.id}: {str(e)}")
        
        # Verificar User-Agent sospechoso
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        suspicious_agents = ['bot', 'crawler', 'scraper', 'spider']
        
        if any(agent in user_agent.lower() for agent in suspicious_agents):
            return True
        
        return False
    
    def _get_client_ip(self, request):
        """IP del cliente con la regla del proxy de confianza (authentication/client_ip.py).
        El primer salto de X-Forwarded-For lo escribe el cliente y permitía falsear la IP."""
        return get_client_ip(request)
