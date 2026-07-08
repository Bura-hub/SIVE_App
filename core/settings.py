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

# Lista de hosts permitidos desde variables de entorno
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

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
CORS_ALLOWED_ORIGINS = os.getenv('CORS_ALLOWED_ORIGINS', '').split(',') if os.getenv('CORS_ALLOWED_ORIGINS') else []

# Restringe CORS a orígenes definidos explícitamente
CORS_ALLOW_ALL_ORIGINS = False

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

STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'static')

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
}

# ========================= Caché en Memoria =========================

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
        'TIMEOUT': 300,        # Elementos expiran en 5 minutos
        'OPTIONS': {
            'MAX_ENTRIES': 1000  # Máximo de objetos en caché
        }
    }
}

# ========================= Celery =========================

# Broker y backend de resultados desde variables de entorno
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = os.getenv('REDIS_PORT', '6379')
REDIS_DB = os.getenv('REDIS_DB', '0')
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', '')

# Construir URLs de Redis con autenticación si hay contraseña
if REDIS_PASSWORD:
    CELERY_BROKER_URL = f'redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}'
    CELERY_RESULT_BACKEND = f'redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}'
else:
    CELERY_BROKER_URL = f'redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}'
    CELERY_RESULT_BACKEND = f'redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}'

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
CELERY_BEAT_SCHEDULE = {
    'fetch-device-metadata-daily': {
        'task': 'scada_proxy.tasks.sync_scada_metadata',
        'schedule': crontab(minute=0),  # Cada hora en :00
    },
    'fetch-historical-measurements-hourly': {
        'task': 'scada_proxy.tasks.fetch_historical_measurements_for_all_devices',
        'schedule': crontab(minute=10),  # Cada hora en :10 (después de sync)
        'args': (int(timedelta(hours=2).total_seconds()),),
    },
    'calculate-monthly-consumption-kpi-daily': {
        'task': 'indicators.tasks.calculate_monthly_consumption_kpi',
        'schedule': crontab(minute=25),  # Cada hora en :25
        'args': (),
        'kwargs': {},
        'options': {'queue': 'default'},
    },
    'calculate-daily-chart-data': {
        'task': 'indicators.tasks.calculate_and_save_daily_data',
        'schedule': crontab(minute=35),  # Cada hora en :35
        'args': (),
        'kwargs': {},
        'options': {'queue': 'default'},
    },
    'check-devices-status-hourly': {
        'task': 'scada_proxy.tasks.check_devices_status',
        'schedule': crontab(minute=1),
    },
    'repair-device-relationships-after-check': {
        'task': 'scada_proxy.tasks.repair_device_relationships',
        'schedule': crontab(minute=2),
    },
}

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
            'class': 'logging.FileHandler',
            'filename': 'celery.log',
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