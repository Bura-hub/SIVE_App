"""
Configuración de URLs para el proyecto core.

La lista `urlpatterns` enruta las URLs hacia las vistas correspondientes.
Para más información, consulta:
https://docs.djangoproject.com/en/5.2/topics/http/urls/

Ejemplos de configuración:
- Vistas basadas en funciones:
    1. from my_app import views
    2. path('', views.home, name='home')
- Vistas basadas en clases:
    1. from other_app.views import Home
    2. path('', Home.as_view(), name='home')
- Inclusión de otros archivos de URL:
    1. from django.urls import include, path
    2. path('blog/', include('blog.urls'))
"""

# Importaciones estándar para administración y ruteo
from django.contrib import admin
from django.urls import path, include

# Importar vista de health check
from .health_views import health_check

# Configuración para archivos media en desarrollo
from django.conf import settings
from django.conf.urls.static import static

# ========================= Documentación automática con drf-spectacular =========================

# Importación de vistas para OpenAPI, Swagger y Redoc
from drf_spectacular.views import (
    SpectacularAPIView,       # Endpoint que entrega el esquema OpenAPI en formato JSON
    SpectacularSwaggerView,   # Vista de documentación Swagger UI
    SpectacularRedocView,     # Vista de documentación Redoc UI
)

# ========================= Rutas principales del proyecto =========================

urlpatterns = [
    # Health check endpoint
    path('health/', health_check, name='health_check'),
    
    # Ruta para obtener el esquema OpenAPI en formato JSON
    path('schema/', SpectacularAPIView.as_view(), name='schema'),

    # Interfaz de documentación interactiva Swagger basada en el esquema OpenAPI
    path('docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),

    # Alternativa de documentación con Redoc
    path('redocs/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # Interfaz de administración de Django
    path('admin/', admin.site.urls),

    # Rutas para autenticación de usuarios (login/logout)
    path('auth/', include('authentication.urls')),

    # Rutas del módulo de indicadores
    path('api/', include('indicators.urls')),

    # Rutas relacionadas con la conexión SCADA remota
    path('scada/', include('scada_proxy.urls_scada')),

    # Rutas para la conexión SCADA local
    path('local/', include('scada_proxy.urls_local')),

    # Rutas para la gestión de tareas relacionadas con SCADA
    path('tasks/', include('scada_proxy.urls_tasks')),
    
    # Rutas para datos externos de energía
    path('api/external-energy/', include('external_energy.urls')),
]

# Configuración para archivos media (habilitado para producción)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Vista específica para servir archivos media en producción
from django.http import FileResponse, Http404
from django.views import View
import os

class MediaFileView(View):
    def get(self, request, path):
        file_path = os.path.join(settings.MEDIA_ROOT, path)
        if os.path.exists(file_path):
            return FileResponse(open(file_path, 'rb'))
        raise Http404("File not found")

# Agregar ruta para servir archivos media
urlpatterns += [
    path('media/<path:path>', MediaFileView.as_view(), name='media_file'),
]