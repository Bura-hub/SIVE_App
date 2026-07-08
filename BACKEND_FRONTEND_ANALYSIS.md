# Análisis Backend–Frontend SIVET_App

Documento para entender cómo está construido el backend, cómo se integra con el frontend y cómo analizar problemas de funcionamiento.

---

## 1. Arquitectura del backend

### 1.1 Stack

- **Django 5.2** + **Django REST Framework** (API JSON).
- **PostgreSQL** (configuración en `core/settings.py`: `name_db`, `user_postgres`, `password_user_postgres`, `POSTGRES_HOST`, `port_postgres`).
- **Redis**: broker y backend de Celery.
- **Celery** + **django-celery-beat**: tareas asíncronas y periódicas (sync SCADA, KPIs, datos diarios).
- **Gunicorn** en producción (puerto 8000 dentro del contenedor).
- **Autenticación**: tokens propios (`authentication.AuthToken`) con expiración; refresh tokens. Header: `Authorization: Token <key>`.
- **CORS**: orígenes definidos por `CORS_ALLOWED_ORIGINS` (lista separada por comas). Si el frontend no está en esa lista, el navegador bloquea las peticiones.

### 1.2 Aplicaciones Django y rutas

| Prefijo URL        | App / Inclusión              | Descripción |
|--------------------|------------------------------|-------------|
| `/health/`         | core.health_views            | Health check (sin auth). |
| `/schema/`, `/docs/`, `/redocs/` | drf-spectacular      | OpenAPI / Swagger / Redoc. |
| `/admin/`          | Django admin                 | Admin (sesión). |
| `/auth/*`          | authentication.urls           | Login, logout, refresh, perfil, cambio contraseña, sesiones, imagen de perfil. |
| `/api/*`           | indicators.urls               | Dashboard (summary, chart-data), electric-meters, inverters, weather-stations, reports. |
| `/api/external-energy/*` | external_energy.urls   | Precios, ahorro, generación, demanda, emisiones, sync, market-overview. |
| `/scada/*`         | scada_proxy.urls_scada        | Proxy SCADA remoto. |
| `/local/*`         | scada_proxy.urls_local        | SCADA local, sync dispositivos. |
| `/tasks/*`         | scada_proxy.urls_tasks        | Tareas (fetch histórico, etc.). |
| `/media/<path>`    | MediaFileView                 | Archivos subidos (perfil, etc.). |

### 1.3 Configuración crítica (variables de entorno)

- **Base de datos**: `name_db`, `user_postgres`, `password_user_postgres`, `POSTGRES_HOST` (en Docker: `db`), `port_postgres`. Si faltan, Django lanza `EnvironmentError` al cargar settings.
- **SCADA**: `SCADA_USERNAME`, `SCADA_PASSWORD` (obligatorios en settings). `SCADA_BASE_URL` para el cliente.
- **Redis**: `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`, `REDIS_PASSWORD`. Sin Redis, Celery no arranca.
- **CORS**: `CORS_ALLOWED_ORIGINS` debe incluir la URL exacta del frontend (origen del navegador), por ejemplo `http://localhost:3503` o `http://IP:3503`. Sin esto, las peticiones desde el frontend fallan por CORS.
- **ALLOWED_HOSTS**: debe incluir el host con el que se llama al backend (IP o dominio).

### 1.4 Contrato de login (backend → frontend)

La vista de login devuelve JSON con (entre otros):

- `access_token`: string (clave del token).
- `username`: string.
- `is_superuser`: boolean.
- `expires_in`, `token_type`, etc.

El frontend guarda `access_token` como `authToken` en `localStorage` y lo envía en `Authorization: Token <authToken>` en todas las peticiones autenticadas.

---

## 2. Arquitectura del frontend

### 2.1 Stack

- **React 19** (Create React App / react-scripts).
- **Build**: estático (npm run build → carpeta `build/`).
- **Producción**: imagen Docker con **nginx** que sirve los estáticos; puerto 3000 en el contenedor (mapeado a `FRONTEND_PORT`, p. ej. 3503).
- **Estado de sesión**: `localStorage` (`authToken`, `username`, `isSuperuser`, `currentPage`, `isSidebarMinimized`).
- **Routing**: interno por estado en `App.js` (`currentPage`: login, dashboard, electricalDetails, inverterDetails, weatherDetails, externalEnergy, exportReports).

### 2.2 Configuración de la API (origen de muchos fallos)

- **URL base del backend**: `process.env.REACT_APP_API_URL`.
  - En Create React App las variables de entorno se **inyectan en tiempo de build**, no en tiempo de ejecución.
  - Si el frontend se construye con Docker sin pasar esta variable, `REACT_APP_API_URL` queda `undefined`. Entonces `buildApiUrl` hace `new URL(undefined + endpoint)` y puede lanzar error o generar URLs incorrectas.
- **Solución**: en el Dockerfile del frontend, pasar `ARG REACT_APP_API_URL` y `ENV REACT_APP_API_URL=...` **antes** de `npm run build`, o usar un script de build que lea el valor (p. ej. desde `.env` o desde variables de compose en el host) y exporte `REACT_APP_API_URL` antes del build.
- **Dos módulos de config**:
  - **config.js**: usa `REACT_APP_API_URL`; usado por LoginPage, ProfileSettings, ProfileImageUpload, Sidebar (auth, perfil, logout).
  - **utils/apiConfig.js**: mismo `REACT_APP_API_URL`, más `ENDPOINTS` y `buildApiUrl(endpoint, params)`, `getDefaultFetchOptions(authToken)`, `fetchWithAuth`, `handleApiResponse`. Usado por Dashboard, ElectricalDetails, InverterDetails, WeatherStationDetails, ExternalEnergyData, ExportReports, filtros.
- **Dashboard.js** define localmente `API_BASE_URL = process.env.REACT_APP_API_BASE_URL || ''` y su propio objeto `ENDPOINTS` (parcial); en las llamadas reales usa `apiUtils` (apiConfig), por lo que la URL base efectiva es la de `apiConfig.js` (`REACT_APP_API_URL`). La variable `REACT_APP_API_BASE_URL` en env.example no existe; el nombre correcto es `REACT_APP_API_URL`.

### 2.3 Endpoints conocidos (apiConfig.js) vs backend

- Dashboard: `/api/dashboard/summary/`, `/api/dashboard/chart-data/` → indicators.
- Eléctricos: `/api/electric-meters/`, `/api/electric-meters/list/`, `/api/institutions/`, `/api/electric-meters/calculate-new/`, `/api/electric-meter-indicators/`, etc.
- Inversores: `/api/inverter-indicators/`, `/api/inverter-chart-data/`, `/api/inverters/calculate/`, `/api/inverters/list/`.
- Weather: `/api/weather-station-indicators/`, `/api/weather-station-chart-data/`, `/api/weather-stations/calculate/`, `/api/weather-stations/list/`.
- Reportes: `/api/reports/generate/`, `/api/reports/status/`, `/api/reports/download/`, `/api/reports/history/`.
- **ExportReports.js** usa `ENDPOINTS.reports.delete`; en `apiConfig.js` **no existe** `reports.delete`. Eso produce `buildApiUrl(undefined, ...)` y fallo. En el backend no hay ruta de “delete report” en `indicators/urls.py`; si se añade, hay que definir `reports.delete` en apiConfig.

### 2.4 Autenticación en el frontend

- **Login**: POST a `/auth/login/` con `config.buildApiUrl(getEndpoint('LOGIN'))` (body: `username`, `password`). Respuesta: `access_token`, `username`, `is_superuser` → se guardan y se pasan a `onLoginSuccess`.
- **Peticiones autenticadas**: header `Authorization: Token <authToken>` vía `getDefaultFetchOptions(authToken)`.
- **401**: `handleApiResponse` / `fetchWithAuth` limpian `localStorage` y redirigen a `/` (login). Algunos componentes no usan `fetchWithAuth` y solo hacen `fetch`; en esos casos un 401 no limpia sesión automáticamente (p. ej. LoginPage no necesita token; otros sí).

---

## 3. Docker y despliegue

- **Compose**: `docker-compose.prod.yml`. Servicios: `db`, `redis`, `backend`, `celery_worker`, `celery_beat`, `frontend`.
- **Backend** depende de `db` y `redis` (healthcheck). Comando: migrate + collectstatic + gunicorn.
- **Frontend** depende de `backend` (healthcheck). Se construye desde `frontend/Dockerfile`; **no** se inyectan `REACT_APP_*` en el build por defecto.
- **Red**: todos en `mte_network_prod`. El navegador habla con el backend en `BACKEND_PORT` (ej. 3504) y con el frontend en `FRONTEND_PORT` (ej. 3503); por tanto `REACT_APP_API_URL` debe ser la URL con la que el **navegador** alcanza al backend (p. ej. `http://<IP>:3504`), no la URL interna entre contenedores.

---

## 4. Cómo analizar problemas de funcionamiento

### 4.1 Checklist rápido

1. **¿El backend arranca?**  
   - `docker compose -f docker-compose.prod.yml logs backend`  
   - Verificar que no haya `EnvironmentError` (DB, SECRET_KEY, SCADA, etc.) y que Gunicorn escuche en 8000.

2. **¿El frontend carga?**  
   - Abrir la URL del frontend (ej. `http://IP:3503`).  
   - Si la pantalla queda en blanco o hay errores en consola, revisar si hay `Failed to construct 'URL'` o referencias a `undefined` en URLs (falta `REACT_APP_API_URL` en build).

3. **¿Login falla?**  
   - Comprobar en DevTools (Network) la URL del POST a login: debe ser `http://...:3504/auth/login/` (o el host/puerto correctos).  
   - Si la petición no sale o va a otra URL → problema de `REACT_APP_API_URL` en build o de `config.js`.  
   - Si la petición va bien pero responde 403/502 → backend (credenciales SCADA, CORS, ALLOWED_HOSTS, o lógica de login).

4. **¿CORS?**  
   - En Network, si la petición aparece como “blocked” o “CORS error”, añadir el origen exacto del frontend (esquema + host + puerto) a `CORS_ALLOWED_ORIGINS` en el backend y reiniciar.

5. **¿401 en todas las peticiones después de login?**  
   - Token no enviado: comprobar que las peticiones lleven `Authorization: Token <valor>`.  
   - Token inválido o expirado: backend devuelve 401; el frontend debería limpiar y redirigir si usa `handleApiResponse`/`fetchWithAuth`.  
   - Verificar que el backend use `CustomTokenAuthentication` y que el token exista y esté activo en la base de datos.

6. **¿Dashboard o datos vacíos?**  
   - Puede ser SCADA (token, conectividad, `SCADA_BASE_URL`), falta de datos en BD, o que las tareas Celery (KPIs, daily data) no hayan corrido.  
   - Revisar logs del backend y de `celery_worker` / `celery_beat`.  
   - Comprobar en Network la respuesta JSON de `/api/dashboard/summary/` y `/api/dashboard/chart-data/`.

7. **¿Energía externa (XM) falla?**  
   - Servicio `XMEnergyService` (pydataxm); depende de conectividad y opcionalmente `PYDATAXM_VERIFY_SSL`.  
   - Revisar logs del backend y respuestas de los endpoints bajo `/api/external-energy/`.

8. **¿Reportes (generar/descargar) fallan?**  
   - Endpoints en indicators (generate, status, download, history).  
   - Si el frontend llama a “delete report”, falta definir `reports.delete` en apiConfig y/o implementar el endpoint en el backend.

### 4.2 Origen de datos por pantalla

- **Dashboard**: `/api/dashboard/summary/`, `/api/dashboard/chart-data/` (indicators; datos precalculados y SCADA).
- **Detalle eléctrico**: institutions, electric-meters list, indicators, calculate (indicators).
- **Inversores**: institutions, inverters list, inverter-indicators, chart-data, calculate (indicators).
- **Estaciones meteorológicas**: institutions, weather-stations list, weather-station-indicators, chart-data, calculate (indicators).
- **Energía externa**: `/api/external-energy/*` (external_energy app).
- **Reportes**: `/api/reports/*` (indicators).

### 4.3 Archivos clave para depuración

- **Backend**: `core/settings.py`, `core/urls.py`, `authentication/views.py` (login, refresh), `authentication/authentication.py` (CustomTokenAuthentication), `indicators/views.py`, `external_energy/views.py`, `scada_proxy/scada_client.py`.
- **Frontend**: `frontend/src/utils/apiConfig.js`, `frontend/src/config.js`, `frontend/src/App.js`, `frontend/src/components/LoginPage.js`, `frontend/Dockerfile`, `frontend/nginx.conf`.
- **Despliegue**: `docker-compose.prod.yml`, `env.example`, `.env` (no versionado).

---

## 5. Resumen de riesgos conocidos

| Riesgo | Dónde | Qué hacer |
|--------|--------|-----------|
| Frontend construido sin `REACT_APP_API_URL` | frontend Dockerfile / build | Pasar la variable en el build (ARG/ENV o script) y reconstruir imagen. |
| CORS bloquea peticiones | Backend `CORS_ALLOWED_ORIGINS` | Incluir el origen exacto del frontend (incl. puerto). |
| Login devuelve 502 / error SCADA | Backend necesita SCADA para algo en startup o en login | Revisar si login realmente depende de SCADA; en cualquier caso, revisar credenciales y conectividad. |
| `ENDPOINTS.reports.delete` no definido | apiConfig.js / ExportReports.js | Añadir `reports.delete` en apiConfig si el backend tiene delete; si no, implementar backend y luego frontend. |
| Variable `REACT_APP_API_BASE_URL` en Dashboard | Dashboard.js / env | No usada de forma consistente; el proyecto usa `REACT_APP_API_URL`. Eliminar duplicado o unificar. |
| Health check frontend en Docker | nginx.conf tiene `/health` | El compose espera `curl -f http://localhost:3000/health`; está configurado correctamente. |

Con esta información se puede seguir el flujo desde el navegador hasta la base de datos y Celery, y acotar si un fallo es de configuración (env, CORS, URL base), de contrato (auth, JSON), de red (Docker, SCADA, XM) o de lógica de negocio (vistas, tareas, datos).
