# SIVE, Sistema de Visualización Energético

SIVE es la aplicación web del proyecto MTE «Desarrollo de un modelo transaccional de energía no convencional de
múltiples agentes para el departamento de Nariño» para consultar los datos históricos y los indicadores de consumo,
generación y clima de las cinco plantas fotovoltaicas del proyecto, en Udenar, Unimar, UCC, HUDN y Unicesmag. Toma
las mediciones del conector SCADA del proyecto y los datos públicos del mercado eléctrico colombiano de XM.

Corre en producción en https://mte.udenar.edu.co/sive/. Sin iniciar sesión se pueden consultar en solo lectura las
pantallas de datos, es decir, Dashboard, Medidores, Inversores, Estaciones, Indicadores Solares y Datos Externos.
Sincronizar, recalcular, exportar reportes y administrar piden sesión.

El uso de cada pantalla está en el Manual de Usuario y el diseño interno, en el Documento de Desarrollo, los dos
entregados con este código.

## Arquitectura

Seis servicios en Docker Compose (`docker-compose.prod.yml`, proyecto `mtesive_app`):

| Servicio | Contenedor | Qué hace |
|---|---|---|
| `db` | `mte_postgres_prod` | PostgreSQL 17 con dispositivos, mediciones, indicadores y cuentas |
| `redis` | `mte_redis_prod` | Broker de Celery y caché |
| `backend` | `mte_backend_prod` | Django 5.2 y Django REST Framework con gunicorn, en `127.0.0.1:3504` |
| `celery_worker` | `mte_celery_worker_prod` | Ingesta, reconciliación con el conector y cálculo de indicadores |
| `celery_beat` | `mte_celery_beat_prod` | Programación de las tareas periódicas, guardada en la base |
| `frontend` | `mte_frontend_prod` | React 19 compilado con Vite y servido por nginx, en `127.0.0.1:3503` |

Los puertos solo escuchan en el *loopback*. Apache, en el servidor, termina el TLS y publica la aplicación bajo
`/sive/` del dominio `mte.udenar.edu.co`, con el bloque de [`deploy/apache-sive.conf`](deploy/apache-sive.conf).

Cada hora se descargan las mediciones de las últimas 3 horas y se recalculan los indicadores. Una reconciliación
nocturna y otra cada 6 horas comparan los conteos de SIVE con los del conector y vuelven a descargar los días que no
coinciden. Las tareas y sus horarios están en `CELERY_BEAT_SCHEDULE` de `core/settings.py`. Los indicadores no son
datos en vivo.

## Requisitos

- Docker Engine con Docker Compose v2 (la orden `docker compose`).
- Git.
- Unos 4,5 GB de memoria para los límites de los seis contenedores y espacio para los respaldos de la base, de
  cientos de MB cada uno.
- Para el desarrollo sin Docker, Python 3.11 y Node.js 20 o posterior.
- Acceso de red al conector SCADA (`SCADA_BASE_URL`) y a la API pública de XM.

## Instalación

```bash
git clone <URL_DEL_REPOSITORIO> SIVE_App
cd SIVE_App
cp env.example .env          # y completar los valores (ver «Variables de entorno»)
docker volume create mtesive_app_redis_data_prod    # el compose lo define como externo
docker compose -p mtesive_app -f docker-compose.prod.yml up -d --build
docker compose -p mtesive_app -f docker-compose.prod.yml exec backend python manage.py createsuperuser
```

Al arrancar, el backend aplica las migraciones, carga las instituciones, categorías y dispositivos del conector si la
base está vacía, reúne los estáticos y arranca gunicorn. Para una prueba local basta con `DOMAIN_NAME=localhost` y
`VITE_API_URL=http://localhost:3504`. La aplicación queda en http://localhost:3503 y la API en
http://localhost:3504. El histórico de mediciones se trae con `scripts/backfill_mediciones.sh DESDE HASTA` (ver
[`scripts/README.md`](scripts/README.md)).

Para trabajar en la interfaz sin reconstruir la imagen, con el backend ya arriba:

```bash
cd frontend
npm ci
VITE_API_URL=http://localhost:3504 npm start    # servidor de Vite en http://localhost:3000
```

El despliegue bajo `/sive/` detrás de Apache, las actualizaciones, la vuelta atrás y los respaldos están en
[`DEPLOYMENT_PRODUCTION.md`](DEPLOYMENT_PRODUCTION.md).

## Variables de entorno

La plantilla es `env.example`. El compose pasa a cada contenedor solo las variables que nombra, así que una variable
que no figure en `docker-compose.prod.yml` no llega a Django.

| Variable | Para qué |
|---|---|
| `SECRET_KEY`, `DEBUG` | Clave de Django. `DEBUG=False` siempre en producción |
| `name_db`, `user_postgres`, `password_user_postgres` | Base de datos que crea el contenedor de PostgreSQL |
| `REDIS_PASSWORD` | Contraseña de Redis |
| `SCADA_BASE_URL`, `SCADA_USERNAME`, `SCADA_PASSWORD` | Conector SCADA de donde salen las mediciones |
| `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` | Hosts y orígenes autorizados |
| `DOMAIN_NAME`, `FRONTEND_PORT`, `BACKEND_PORT` | Dominio y puertos locales (3503 y 3504 por defecto) |
| `VITE_API_URL` | URL de la API que Vite escribe en el JavaScript al construir la imagen del frontend. Cambiarla exige reconstruir esa imagen |
| `FORCE_SCRIPT_NAME`, `STATIC_URL`, `USE_X_FORWARDED_HOST`, `BEHIND_TLS_PROXY` | Publicación bajo `/sive/` detrás de Apache |
| `SIVE_GUEST_READ_RATE`, `SIVE_GUEST_XM_RATE`, `SIVE_NUM_PROXIES` | Cupos por IP de la lectura sin sesión (120/min y 30/min) y proxies de confianza (1) |
| `XM_API_TIMEOUT`, `PYDATAXM_VERIFY_SSL`, `SOLAR_INSTALLATION_COST_COP` | Consultas a XM y costo de la instalación para el ROI |
| `ALERT_WEBHOOK_URL`, `ALERT_EMAIL_TO`, `EMAIL_*`, `DEFAULT_FROM_EMAIL` | Destino de las alertas de fallos. Sin ellas, las alertas quedan en el registro |

Otras entradas de `env.example` no tienen efecto. `TIME_ZONE` está fijada en el código en `America/Bogota`,
`SECURE_HSTS_SECONDS` no la pasa el compose y Django queda en 0, que es lo correcto en un dominio compartido, y
`REACT_APP_FRONTEND_URL`, `password_postgres`, `username_SIVE`, `password_SIVE`, `wsl_account`, `wsl_password`,
`start_worker_celery` y `start_celery_beat` no las lee nadie.

## Pruebas

Backend, con las clases de prueba de Django. Cada corrida crea una base de prueba temporal y no toca los datos:

```bash
docker compose -p mtesive_app -f docker-compose.prod.yml exec backend python manage.py test
docker compose -p mtesive_app -f docker-compose.prod.yml exec backend python manage.py test tests.test_solar_indicators
```

Frontend, con Vitest:

```bash
cd frontend
npm ci
npm test
npm run build
```

`.github/workflows/ci.yml` corre las dos en cada *push* y *pull request*, y comprueba además que no falte ninguna
migración. En `tests/` hay también guiones de diagnóstico que se ejecutan a mano contra una base real y no forman
parte de la suite (lista en `tests/conftest.py`).

## Estructura del repositorio

| Ruta | Contenido |
|---|---|
| `core/` | Configuración de Django y Celery, URL, permisos, cupos, salud y alertas |
| `authentication/` | Cuentas, token con expiración, sesiones, perfil y bloqueo por intentos |
| `scada_proxy/` | Cliente del conector SCADA, ingesta, reconciliación y mediciones por categoría |
| `indicators/` | Cálculo de indicadores, Indicadores Solares, reportes y vistas de la API. Metodología en [`indicators/indicators.md`](indicators/indicators.md) |
| `external_energy/` | Datos de XM y ahorro de las plantas. Detalle en [`external_energy/README.md`](external_energy/README.md) |
| `frontend/` | Interfaz en React. Detalle en [`frontend/README.md`](frontend/README.md) |
| `tests/` | Suites del backend y guiones de diagnóstico |
| `scripts/` | Despliegue, respaldo, relleno y recálculo del histórico. Detalle en [`scripts/README.md`](scripts/README.md) |
| `deploy/` | Bloque de Apache para publicar bajo `/sive/` |
| `requirements.txt`, `requirements/` | Dependencias de Python. La imagen se construye con `requirements.txt` |
| `static/` | Estáticos reunidos de Django (administración y documentación de la API) |
| `Dockerfile.backend`, `docker-compose.prod.yml`, `init-db.sql` | Imagen del backend, servicios e inicialización de la base |

La documentación de la API, generada con drf-spectacular, está en `/docs/` (Swagger), `/redocs/` y `/schema/`, solo
para administradores con sesión iniciada en `/admin/`.

## Licencia

Copyright (c) 2025-2026 Universidad de Nariño. Todos los derechos reservados. Nadie puede usar, copiar, modificar ni
distribuir este software sin autorización previa y por escrito de la Universidad de Nariño. Las bibliotecas de
terceros conservan sus propias licencias. El texto completo está en [`LICENSE`](LICENSE).

## Autores

- Brayan Stiven López-Méndez, Departamento de Electrónica, Universidad de Nariño.
- Wilson Olmedo Achicanoy-Martínez, Ph. D., Departamento de Electrónica, Universidad de Nariño.

Desarrollado en el Grupo de Investigación en Ingeniería Eléctrica y Electrónica (GIIEE) de la Universidad de Nariño,
en el proyecto MTE, financiado por el Sistema General de Regalías (BPIN 2021000100499).

## Contacto

GIIEE, Universidad de Nariño, Pasto, Colombia. Correo wilachic@udenar.edu.co.
