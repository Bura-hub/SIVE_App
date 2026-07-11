"""
Configuración de Django para el proyecto core.

Generado por 'django-admin startproject' usando Django 5.2.4.

Para más información sobre este archivo:
https://docs.djangoproject.com/en/5.2/topics/settings/
"""

import os
from pathlib import Path
from dotenv import load_dotenv  # Permite cargar variables de entorno desde un archivo .env
from datetime import timedelta  # Para definir intervalos de tiempo en Celery
from celery.schedules import crontab

# Carga las variables de entorno del archivo .env
load_dotenv()

# Extrae credenciales SCADA desde variables de entorno
SCADA_USERNAME = os.getenv("SCADA_USERNAME")
SCADA_PASSWORD = os.getenv("SCADA_PASSWORD")

# Validación temprana para asegurar que las credenciales estén presentes
if not SCADA_USERNAME or not SCADA_PASSWORD:
    raise EnvironmentError("SCADA_USERNAME or SCADA_PASSWORD environment variables are not set.")

# ========================= Rutas del Proyecto =========================

# Ruta base del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent

# ========================= Configuración General =========================

# Clave secreta del proyecto desde variables de entorno
SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    raise EnvironmentError("SECRET_KEY environment variable is not set.")

# Modo debug desde variables de entorno
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'

def env_list(name, default=''):
    """Lee una variable de entorno separada por comas → lista sin espacios ni vacíos.
    Evita bugs sutiles: 'https://a, https://b' NO debe dejar ' https://b' (con espacio),
    que nunca haría match contra un Origin entrante."""
    return [item.strip() for item in os.getenv(name, default).split(',') if item.strip()]


# Lista de hosts permitidos desde variables de entorno
ALLOWED_HOSTS = env_list('ALLOWED_HOSTS', 'localhost,127.0.0.1')

# --- Despliegue bajo un subpath detrás de un reverse proxy (p. ej. /sive) ---
# FORCE_SCRIPT_NAME hace que Django genere sus URLs (admin, DRF, login, redirecciones)
# con este prefijo. Vacío por defecto → despliegue en la raíz "/" y dev local sin cambios.
FORCE_SCRIPT_NAME = os.getenv('FORCE_SCRIPT_NAME') or None
# Confiar en el Host reenviado por el proxy (Apache) cuando termina TLS por nosotros.
USE_X_FORWARDED_HOST = os.getenv('USE_X_FORWARDED_HOST', 'False').lower() == 'true'

# --- Alerting (core/alerting.py) --- Canales opcionales; si ambos vacíos, solo se loguea.
ALERT_WEBHOOK_URL = os.getenv('ALERT_WEBHOOK_URL', '')   # Slack/Discord/Teams/genérico
ALERT_EMAIL_TO = os.getenv('ALERT_EMAIL_TO', '')          # requiere EMAIL_HOST/EMAIL_* configurados

# ========================= Aplicaciones Registradas =========================

INSTALLED_APPS = [
    'django.contrib.admin',                 # Admin de Django
    'django.contrib.auth',                  # Autenticación
    'django.contrib.contenttypes',          # Tipos de contenido (modelo base)
    'django.contrib.sessions',              # Soporte para sesiones
    'django.contrib.messages',              # Sistema de mensajes
    'django.contrib.staticfiles',           # Archivos estáticos

    # Aplicaciones de terceros
    'rest_framework',                       # Django REST Framework
    'corsheaders',                          # CORS (Cross-Origin Resource Sharing)
    'rest_framework.authtoken',             # Token Auth para DRF
    'django_celery_beat',                   # Planificación de tareas periódicas con Celery
    'django_filters',                       # Filtros para DRF
    'drf_spectacular',                      # Generación de documentación OpenAPI

    # Aplicaciones personalizadas
    'authentication',
    'indicators',
    'scada_proxy',
    'external_energy',
]

# ========================= Middleware =========================

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # WhiteNoise sirve los estáticos (admin/DRF/Swagger) directamente desde gunicorn,
    # sin depender de un servidor de archivos aparte. Debe ir justo tras SecurityMiddleware.
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',  # CORS antes del CommonMiddleware
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# ========================= CORS =========================

# CORS dinámico desde variables de entorno
CORS_ALLOWED_ORIGINS = env_list('CORS_ALLOWED_ORIGINS')

# Restringe CORS a orígenes definidos explícitamente
CORS_ALLOW_ALL_ORIGINS = False

# ========================= CSRF =========================

# Orígenes de confianza para CSRF (Django >= 4 los exige para POST cross-origin,
# p. ej. el login del /admin desde una IP/puerto distintos). Se leen del entorno
# (definidos en .env / docker-compose) igual que CORS.
CSRF_TRUSTED_ORIGINS = env_list('CSRF_TRUSTED_ORIGINS')

# ========================= Enrutamiento =========================

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],  # Puedes añadir rutas de templates personalizadas aquí
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

# ========================= Base de Datos =========================

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('name_db'),
        'USER': os.getenv('user_postgres'),
        'PASSWORD': os.getenv('password_user_postgres'),
        'HOST': os.getenv('POSTGRES_HOST', 'db'),
        'PORT': os.getenv('port_postgres', '5432'),
        'OPTIONS': {
            'options': '-c client_encoding=UTF8'
        }
    }
}

# Validar configuración de base de datos
if not all([os.getenv('name_db'), os.getenv('user_postgres'), os.getenv('password_user_postgres')]):
    raise EnvironmentError("Database configuration environment variables are not set.")

# ========================= Configuración de Usuario Personalizado =========================

# Mantener el modelo de usuario estándar de Django
# AUTH_USER_MODEL = 'authentication.User'

# ========================= Validación de Contraseñas =========================

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 12}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
    {'NAME': 'authentication.validators.CustomPasswordValidator'},
    {'NAME': 'authentication.validators.UserAttributeSimilarityValidator'},
]

# ========================= Internacionalización =========================

LANGUAGE_CODE = 'es-co'
TIME_ZONE = 'America/Bogota'
USE_I18N = True
USE_TZ = True

# ========================= Archivos Estáticos =========================

# Bajo un subpath (p. ej. /sive) debe apuntarse a una ruta propia como
# /sive/django-static/ para NO colisionar con los estáticos del frontend React
# (/sive/static/). Por defecto conserva 'static/' (raíz / dev local).
STATIC_URL = os.getenv('STATIC_URL', 'static/')
STATIC_ROOT = os.path.join(BASE_DIR, 'static')

# WhiteNoise: compresión de estáticos (sin manifest, para no romper collectstatic si
# alguna referencia de admin/DRF faltara). Sirve STATIC_URL desde gunicorn.
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage'},
}

# ========================= Configuración por defecto de PK =========================

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ========================= Django REST Framework =========================

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'authentication.authentication.CustomTokenAuthentication',  # Autenticación personalizada
        'rest_framework.authentication.SessionAuthentication',      # Para acceso al admin
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',               # Requiere login por defecto
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',  # Esquema OpenAPI
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/day',
        'user': '1000/day'
    },
    # Paginación global: acota el payload de los ViewSets/generics que devuelven listas.
    # Los endpoints cuyo shape plano/custom consume el frontend se eximen con
    # pagination_class = None en la vista (ver ElectricMeterIndicatorsViewSet).
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 100,
}

# ========================= Redis =========================

# Conexión a Redis compartida por la caché de Django y por Celery.
# Variables desde el entorno (definidas en .env / docker-compose).
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = os.getenv('REDIS_PORT', '6379')
REDIS_DB = os.getenv('REDIS_DB', '0')                # Base usada por Celery (broker/resultados)
REDIS_CACHE_DB = os.getenv('REDIS_CACHE_DB', '1')    # Base separada para la caché de Django
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', '')

# URL base de Redis con autenticación si hay contraseña
if REDIS_PASSWORD:
    REDIS_BASE_URL = f'redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}'
else:
    REDIS_BASE_URL = f'redis://{REDIS_HOST}:{REDIS_PORT}'

# ========================= Caché (Redis compartido) =========================

# Caché compartida entre procesos vía django-redis. Con LocMemCache cada worker
# de gunicorn tenía su propia caché en memoria, lo que rompía el throttling de
# DRF y cualquier lock compartido entre procesos. Se usa una base de Redis
# distinta a la de Celery (REDIS_CACHE_DB, por defecto la 1) para no mezclar
# claves de caché con mensajes del broker.
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': f'{REDIS_BASE_URL}/{REDIS_CACHE_DB}',
        'TIMEOUT': 300,        # Elementos expiran en 5 minutos
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# ========================= Celery =========================

# Broker y backend de resultados sobre la misma instancia de Redis (base REDIS_DB)
CELERY_BROKER_URL = f'{REDIS_BASE_URL}/{REDIS_DB}'
CELERY_RESULT_BACKEND = f'{REDIS_BASE_URL}/{REDIS_DB}'

CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'America/Bogota'
CELERY_TASK_TRACK_STARTED = True
CELERY_RESULT_EXTENDED = True

# Usar el programador basado en base de datos
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

# ========================= Tareas Periódicas =========================

# Una sola fuente de verdad: todas las tareas periódicas aquí, con horarios escalonados
# para evitar carreras (sync → fetch → cálculos).
# Los cálculos (KPI mensual y chart diario) ya NO se programan por separado:
# los encadena run_post_ingest_pipeline como callback del chord de ingesta
# (barrera real: corren solo cuando el fetch de TODOS los dispositivos acabó).
# Al cambiar nombres aquí, borrar las PeriodicTask viejas en el switchover
# (el DatabaseScheduler añade/actualiza, pero no elimina entradas obsoletas).
CELERY_BEAT_SCHEDULE = {
    'sync-scada-metadata-hourly': {
        'task': 'scada_proxy.tasks.sync_scada_metadata',
        'schedule': crontab(minute=0),  # Cada hora en :00
    },
    'ingest-and-calculate-hourly': {
        'task': 'scada_proxy.tasks.fetch_historical_measurements_for_all_devices',
        'schedule': crontab(minute=10),  # Cada hora en :10 (después de sync)
        # Ventana de 3h con cadencia 1h: tolera caídas del connector de hasta
        # ~2h sin pérdida (upserts idempotentes); >2h lo cubre el refetch de ayer.
        'args': (int(timedelta(hours=3).total_seconds()),),
    },
    'check-devices-status-hourly': {
        'task': 'scada_proxy.tasks.check_devices_status',
        'schedule': crontab(minute=1),
    },
    'repair-device-relationships-hourly': {
        'task': 'scada_proxy.tasks.repair_device_relationships',
        'schedule': crontab(minute=2),
    },
    'refetch-verify-yesterday-daily': {
        'task': 'scada_proxy.tasks.refetch_and_verify_yesterday',
        'schedule': crontab(hour=1, minute=30),  # Diario 01:30 Bogotá
    },
    'sync-external-energy-daily': {
        'task': 'external_energy.tasks.sync_external_energy_data',
        'schedule': crontab(hour=3, minute=0),  # Diario a las 03:00 (hora Bogotá)
    },
    'calculate-energy-savings-daily': {
        'task': 'external_energy.tasks.calculate_energy_savings',
        # 03:30: después de sync-external-energy-daily (03:00) para que los precios
        # de XM del día ya estén persistidos al calcular los ahorros.
        'schedule': crontab(hour=3, minute=30),
    },
}

# Límites y entrega de tareas: ninguna tarea normal debería exceder 9 min
# (las de reportes definen sus propios límites en el decorador). acks_late +
# reject_on_worker_lost es seguro porque todas las escrituras son upserts
# idempotentes; garantiza re-entrega si un worker muere a mitad de tarea.
CELERY_TASK_SOFT_TIME_LIMIT = 540
CELERY_TASK_TIME_LIMIT = 660
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True

# ========================= Configuración External Energy (XM) =========================

# Timeout duro (segundos) para las llamadas a la API de XM (pydataxm) hechas desde
# vistas y tareas. Evita bloquear el ciclo request/response de Django ante una red lenta.
XM_API_TIMEOUT = int(os.getenv('XM_API_TIMEOUT', '30'))

# Verificación SSL para pydataxm (informativo). Ver la nota de seguridad en
# external_energy/services.py: NO se desactiva la verificación SSL global del proceso.
PYDATAXM_VERIFY_SSL = os.getenv('PYDATAXM_VERIFY_SSL', 'true').lower() not in ('0', 'false', 'no')

# Parámetros del cálculo de factor de capacidad y ROI en los ahorros de energía.
# Antes estaban hardcodeados en la vista (100 kW y 50.000.000 COP).
SOLAR_INSTALLED_CAPACITY_KW = float(os.getenv('SOLAR_INSTALLED_CAPACITY_KW', '100'))
SOLAR_INSTALLATION_COST_COP = float(os.getenv('SOLAR_INSTALLATION_COST_COP', '50000000'))

# ========================= Documentación de la API (drf-spectacular) =========================

SPECTACULAR_SETTINGS = {
    'TITLE': 'MTE - SIVE API',
    'DESCRIPTION': (
        'API completa para el sistema MTE - SIVE con autenticación avanzada, '
        'monitoreo de sistemas eléctricos, estaciones meteorológicas e inversores. '
        'Incluye funcionalidades de seguridad mejoradas, tokens de refresco, '
        'y auditoría completa de acceso.'
    ),
    'VERSION': '2.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    # Documentación (schema + Swagger + Redoc): SOLO admin. Se accede logueándose primero
    # por /admin/ (SessionAuthentication está en DEFAULT_AUTHENTICATION_CLASSES, así que la
    # cookie de sesión del admin autentica estas vistas). NO sirve el token de la app: el
    # navegador no lo envía en cargas de página, solo manda cookies.
    'SERVE_PERMISSIONS': ['rest_framework.permissions.IsAdminUser'],
    'SECURITY': [
        {"TokenAuth": []},
        {"SessionAuth": []}
    ],
    'COMPONENTS': {
        'securitySchemes': {
            'TokenAuth': {
                'type': 'apiKey',
                'in': 'header',
                'name': 'Authorization',
                'description': "Formato: **Token <access_token>**"
            },
            'SessionAuth': {
                'type': 'apiKey',
                'in': 'cookie',
                'name': 'sessionid',
                'description': "Autenticación por sesión (automática si estás logueado en /admin)"
            }
        }
    },
    'TAGS': [
        {'name': 'Autenticación', 'description': 'Endpoints para autenticación y gestión de usuarios'},
        {'name': 'Indicadores', 'description': 'KPIs y métricas del sistema'},
        {'name': 'SCADA', 'description': 'Integración con sistemas SCADA'},
        {'name': 'Reportes', 'description': 'Generación y gestión de reportes'},
    ],
}

# ========================= Configuración de Logging =========================

# Archivo de log rotado. Se escribe en BASE_DIR (/app), que es escribible por el
# usuario del contenedor; el volumen ./logs no se usa por problemas de permisos
# (pertenece al host). El registro duradero real es `docker logs`; aquí solo se
# acota el crecimiento del archivo con rotación (antes: FileHandler sin límite).
_LOG_FILE = os.path.join(BASE_DIR, 'celery.log')

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
            'level': 'INFO',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': _LOG_FILE,
            'maxBytes': 10 * 1024 * 1024,  # 10 MB por archivo
            'backupCount': 5,              # 5 archivos de respaldo (~50 MB máx)
            'formatter': 'verbose',
            'level': 'INFO',
        },
    },
    'loggers': {
        'indicators.tasks': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'scada_proxy.tasks': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'celery': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        # Emite el resultado de CADA tarea (succeeded/failed/retry + duración).
        # Sin este logger el worker no deja rastro del desenlace de las tareas.
        'celery.app.trace': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'celery.task': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'celery.worker': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}

# ========================= Configuración de Archivos Media =========================

# URL para servir archivos media en desarrollo
MEDIA_URL = '/media/'

# Directorio donde se almacenan los archivos subidos por los usuarios
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Configuración para archivos de imagen
IMAGE_UPLOAD_MAX_SIZE = 5 * 1024 * 1024  # 5MB
IMAGE_UPLOAD_ALLOWED_FORMATS = ['image/jpeg', 'image/png', 'image/webp']
IMAGE_UPLOAD_MIN_DIMENSIONS = (100, 100)  # 100x100 píxeles mínimo
IMAGE_UPLOAD_MAX_DIMENSIONS = (2000, 2000)  # 2000x2000 píxeles máximo

# ========================= Seguridad en Producción =========================

# Endurecimiento aplicado solo con DEBUG=False para no romper el desarrollo
# local por HTTP.
#
# IMPORTANTE: HSTS y las cookies "Secure" requieren servir el sitio por HTTPS
# real (TLS terminado en un proxy/nginx o en Django). Si el despliegue aún se
# accede por HTTP plano, el login por sesión (/admin) no funcionará hasta tener
# HTTPS, y el header HSTS le indica al navegador que rechace HTTP para el
# dominio durante SECURE_HSTS_SECONDS (difícil de revertir: empezar con un
# valor bajo si hay dudas).
if not DEBUG:
    # Cookies de sesión y CSRF solo se envían por HTTPS
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    # Evita que el navegador "adivine" content-types (X-Content-Type-Options: nosniff)
    SECURE_CONTENT_TYPE_NOSNIFF = True

    # Referrer-Policy: no filtrar la URL completa a orígenes cruzados.
    SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

    # HSTS: opt-in por entorno. Por defecto DESACTIVADO (0) porque el dominio
    # mte.udenar.edu.co es COMPARTIDO con otras apps; un HSTS con includeSubDomains/
    # preload emitido por SIVE afectaría a todo el dominio. El header HSTS debe
    # gestionarlo el dueño del dominio a nivel de Apache, no una sola app.
    SECURE_HSTS_SECONDS = int(os.getenv('SECURE_HSTS_SECONDS', '0'))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = os.getenv('SECURE_HSTS_INCLUDE_SUBDOMAINS', 'False').lower() == 'true'
    SECURE_HSTS_PRELOAD = os.getenv('SECURE_HSTS_PRELOAD', 'False').lower() == 'true'

    # Detrás de un proxy/balanceador que termina TLS (Apache con el certificado
    # Let's Encrypt del dominio), activar por env para que request.is_secure()
    # reconozca HTTPS desde X-Forwarded-Proto. Requiere un proxy de CONFIANZA que
    # sobrescriba ese header (Apache lo hace); nunca activarlo con acceso directo.
    if os.getenv('BEHIND_TLS_PROXY', 'False').lower() == 'true':
        SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')