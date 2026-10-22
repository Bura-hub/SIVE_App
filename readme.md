# 🌟 MTE SIVE - Sistema de Visualización Energético

[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://www.docker.com/)
[![Django](https://img.shields.io/badge/Django-5.2.16-green.svg)](https://www.djangoproject.com/)
[![React](https://img.shields.io/badge/React-19.1.0-blue.svg)](https://reactjs.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17-blue.svg)](https://www.postgresql.org/)

## 📋 Descripción General

**MTE SIVE** es una aplicación web integral para la visualización de datos históricos e indicadores clave relacionados con el consumo y generación de energía eléctrica, así como variables climáticas relevantes. Construida con una arquitectura desacoplada utilizando **Django (Python)** para el backend y **React (JavaScript)** para el frontend.

### 🎯 Objetivo Principal
Transformar datos complejos en información accionable, proporcionando a analistas y ejecutivos una visión clara y dinámica del comportamiento de los sistemas energéticos y climáticos.

**Estado del Proyecto:** en producción bajo `https://mte.udenar.edu.co/sive/` (desde el 10 de octubre de 2026,
con la corrección de ingesta e indicadores, la pantalla Indicadores Solares y el modo invitado; ver *Estado de
Desarrollo* más abajo).

## 🚀 Características Principales

### 🔐 Acceso, Autenticación y Seguridad
- **Modo invitado**: sin iniciar sesión se consultan en solo lectura el Dashboard, Medidores, Inversores, Estaciones,
  Indicadores Solares y Datos Externos (`IsAuthenticatedOrPublicRead`, con cupo por IP: `SIVE_GUEST_READ_RATE`,
  120/min, y `SIVE_GUEST_XM_RATE`, 30/min). Sincronizar, recalcular, exportar y administrar piden sesión.
- **Sistema de Autenticación Robusto**: Login seguro con gestión de usuarios y roles
- **Gestión de Perfiles Avanzada**: Configuración de información personal, avatares y preferencias
- **Gestión de Sesiones**: Control de dispositivos conectados con capacidad de cerrar sesiones
- **Seguridad Mejorada**: Rate limiting, bloqueo temporal por intentos fallidos
- **Tokens de Acceso**: Sistema de autenticación basado en tokens con expiración automática

### 📊 Dashboard y Visualizaciones
- **Dashboard Interactivo**: resumen del mes en curso (demanda de los circuitos medidos, generación de las plantas,
  balance, potencia media de la flota y clima), comparado con el mes anterior en el mismo tiempo transcurrido
- **Visualizaciones Dinámicas**: Gráficos interactivos (líneas y barras) impulsados por Chart.js
- **KPIs actualizados cada hora**: se recalculan tras cada ingesta y tras la reconciliación nocturna; no son datos en vivo
- **Selector de rango en español** y aviso de **disponibilidad de datos** por dispositivo
- **Versión móvil**: menú lateral como cajón con botón de tres líneas, filtros y gráficas a todo el ancho
- **Persistencia de Estado**: Recuerda el estado de la barra lateral y pestañas activas

### 🔌 Módulos Especializados
- **Medidores**: energía importada, demanda pico, factor de carga y factor de potencia, por medidor o para todos
- **Inversores**: generación, potencia máxima, FP y frecuencia mientras genera, desbalances y Performance Ratio;
  «No disponible» con su motivo en lugar de 0
- **Estaciones**: irradiancia y HSP, temperatura, viento (con rosa de los vientos), precipitación y potencia FV teórica
- **Indicadores Solares**: desempeño de la planta de cada institución (energía, kWh/kWp, factor de capacidad, frente al
  diseño, PR, cobertura, autoconsumo, ahorro, CO₂ y disponibilidad), con la convención de energía de la tesis y del
  mercado P2P (`indicators/services/institution_energy.py`, `solar_kpis.py`)
- **Datos Externos (XM)**: precios, generación y demanda nacional, factor de emisión y comercio internacional
- **Exportación de Reportes** (administradores): Generación y descarga de reportes en PDF, Excel y CSV

### ⚡ Integración SCADA y Procesamiento
- **Integración con API SCADA**: ingesta horaria de las mediciones del conector a tablas tipadas por categoría
- **Reconciliación con el conector (D1)**: compara por dispositivo y día el conteo local con el del conector y
  vuelve a descargar los días distintos; recupera las colas que las RPi envían con retraso
- **Cálculo Automático de KPIs**: Tareas asíncronas con Celery que calculan indicadores diarios y mensuales
- **Sincronización de Metadatos**: Actualización automática de dispositivos, categorías e instituciones
- **Procesamiento de Datos Históricos**: Almacenamiento y análisis de mediciones históricas

## 🏗️ Arquitectura del Proyecto

### Backend (Django 5.2)
- **Django 5.2 + Django REST Framework**: APIs RESTful (auth por token `Token <key>`)
- **PostgreSQL 17**: Base de datos principal
- **Redis**: Broker para Celery y caché
- **Celery + Celery Beat**: Procesamiento asíncrono y tareas periódicas (scheduler en BD)
- **Capa `services/`**: la lógica de cálculo de indicadores vive en funciones puras
  (`indicators/services/`), separada de tasks/vistas (vistas "finas")
- **drf-spectacular**: OpenAPI en `/schema/`, Swagger en `/docs/`, Redoc en `/redocs/`
  (accesibles solo a admin vía sesión de `/admin/`)

### Frontend (React 19 + Vite)
- **React 19**: Biblioteca de interfaz de usuario (JSX servido desde archivos `.js`)
- **Vite 5**: Bundler y dev server (`npm start`); **Vitest** para tests (`npm test`)
- **Chart.js** (`react-chartjs-2`, `chartjs-plugin-zoom`): gráficos, incluida la rosa de vientos polar
- **Tailwind CSS**: framework de CSS utilitario
- Navegación por **estado** (sin router de URL); la URL base de la API se inyecta en
  build-time vía `VITE_API_URL`

### Infraestructura
- **Docker**: containerización completa (`docker-compose.prod.yml`)
- **PostgreSQL** (persistencia) y **Redis** (cache/broker)
- **Producción tras Apache**: publicado como subruta **`/sive/`** del dominio
  `mte.udenar.edu.co`, reutilizando su certificado Let's Encrypt (ver sección de despliegue)

## 🛠️ Requisitos del Sistema

### Software Requerido
- **Docker**: Versión 20.10 o superior
- **Docker Compose**: Versión 2.0 o superior
- **Git**: Para control de versiones

### Hardware Recomendado
- **RAM**: 4GB mínimo, 8GB recomendado
- **Almacenamiento**: 20GB mínimo para desarrollo, 50GB+ para producción
- **CPU**: Procesador de 2+ núcleos para desarrollo, 4+ núcleos para producción

## ⚙️ Instalación y Configuración

### 1. Clonar el Repositorio
```bash
git clone <URL_DEL_REPOSITORIO>
cd <carpeta-del-repo>
```

### 2. Configurar Variables de Entorno
```bash
# Copiar archivo de ejemplo
cp env.example .env

# Editar variables de entorno (ver env.example para la lista completa)
nano .env
```

### 3. Desplegar con Docker

#### Para Desarrollo (Windows):
```powershell
.\scripts\deploy_to_new_machine.ps1
```

#### Para Producción (Windows):
```powershell
.\scripts\deploy_production.ps1 deploy
```

#### Para Producción (Linux/Mac):
```bash
chmod +x scripts/deploy_production.sh
./scripts/deploy_production.sh deploy
```

### 4. Configurar Aplicación
```bash
# Crear superusuario
docker exec -it mte_backend_prod python manage.py createsuperuser

# Verificar servicios
docker-compose -f docker-compose.prod.yml ps
```

## 🌐 URLs de Acceso

### Desarrollo:
- **Frontend**: http://localhost:${FRONTEND_PORT:-3503}
- **Backend**: http://localhost:${BACKEND_PORT:-3504}
- **Admin**: http://localhost:${BACKEND_PORT:-3504}/admin

### Producción (bajo Apache, subruta `/sive/`):
- **Aplicación**: https://mte.udenar.edu.co/sive/
- **Admin**: https://mte.udenar.edu.co/sive/admin/
- **API**: https://mte.udenar.edu.co/sive/api/
- **Docs API** (solo admin, tras iniciar sesión en `/sive/admin/`): Swagger `/sive/docs/`,
  Redoc `/sive/redocs/`, esquema OpenAPI `/sive/schema/`

> Los contenedores escuchan solo en `127.0.0.1:3503` (frontend) y `127.0.0.1:3504`
> (backend); **no** se exponen a Internet — solo Apache los alcanza. Ver
> [Despliegue en producción bajo `/sive/`](#-despliegue-en-producción-bajo-sive).

## 🌐 Despliegue en producción bajo `/sive/`

SIVE se publica como **subruta `/sive/`** de `mte.udenar.edu.co`, reutilizando el Apache y
el certificado Let's Encrypt existentes, sin abrir puertos nuevos.

```
Navegador ──HTTPS──> Apache (:443, cert de mte.udenar.edu.co)
   /sive/api,/auth,/admin,... ├─(quita /sive)──> 127.0.0.1:3504  backend  (gunicorn)
   /sive/django-static        ├────────────────> 127.0.0.1:3504  (WhiteNoise)
   /sive/ (resto)             └────────────────> 127.0.0.1:3503  frontend (nginx)
```

- El **frontend** navega por estado (sin router de URL) y carga assets de forma relativa bajo `/sive/`.
- El **backend** corre con `FORCE_SCRIPT_NAME=/sive`, así admin, DRF, Swagger y redirecciones generan URLs con `/sive`.
- API y frontend comparten **el mismo origen** → sin CORS ni contenido mixto.

**Variables clave del `.env`:**
```env
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1,mte.udenar.edu.co
CORS_ALLOWED_ORIGINS=https://mte.udenar.edu.co
CSRF_TRUSTED_ORIGINS=https://mte.udenar.edu.co
VITE_API_URL=https://mte.udenar.edu.co/sive     # se incrusta en el bundle en build-time
FORCE_SCRIPT_NAME=/sive
STATIC_URL=/sive/django-static/
USE_X_FORWARDED_HOST=True
BEHIND_TLS_PROXY=True
SECURE_HSTS_SECONDS=0        # dominio compartido; HSTS lo gestiona Apache
```

**Reconstruir tras cambiar `VITE_API_URL`** (se hornea en build-time):
```bash
docker compose -f docker-compose.prod.yml build backend frontend
docker compose -f docker-compose.prod.yml up -d
```

**Apache** (lo aplica el administrador; requiere `proxy`, `proxy_http`, `headers`): insertar el
bloque de [`deploy/apache-sive.conf`](deploy/apache-sive.conf) dentro del `<VirtualHost *:443>`
existente, luego `sudo apache2ctl configtest && sudo systemctl reload apache2`.

**Verificación:**
```bash
curl -sk  https://mte.udenar.edu.co/sive/health/   # -> 200
curl -sk  https://mte.udenar.edu.co/sive/api/      # -> 401 (la raíz de la API pide sesión)
curl -sk  https://mte.udenar.edu.co/sive/api/dashboard/summary/   # -> 200 (lectura pública, modo invitado)
curl -skI https://mte.udenar.edu.co/sive/          # -> 200 (index del frontend)
```

> Nota: los estáticos de admin/DRF se sirven con WhiteNoise; Apache quita el prefijo `/sive` y
> WhiteNoise sirve en `/django-static/`. La ruta crítica (frontend + API JSON) no depende de
> estáticos de Django.

## 📊 Indicadores Clave de Rendimiento (KPIs)

La metodología completa está en [`indicators/indicators.md`](indicators/indicators.md) y en la corrección de octubre de
2026 ([`docs/superpowers/specs/2026-10-10-correccion-ingesta-e-indicadores-design.md`](docs/superpowers/specs/2026-10-10-correccion-ingesta-e-indicadores-design.md),
con sus hallazgos C1–C22). Cada tarjeta explica su cálculo en la propia aplicación (`frontend/src/utils/kpiInfo.js`).

### 🔋 Dashboard (mes en curso)
- **Demanda de los circuitos medidos**: Medidor 1 de cada institución, horas con ≥ 15 de 30 lecturas (kWh)
- **Generación de las plantas FV**: inversores de las cinco plantas de 17,55 kWp, sin equipos de prueba ni retirados (kWh)
- **Balance generación − demanda** y **Potencia media de la flota** (generación × 1000 / horas transcurridas)
- **Clima**: temperatura, humedad, viento e irradiancia de las estaciones
- **Inversores con datos**: inversores de planta con lecturas en SIVE en las últimas 24 h (no es un dato en vivo)

### 🔌 Medidores
- **Energía importada**: integración de la potencia activa (C17)
- **Demanda pico**: mayor media de bloques de reloj de 15 min (C18); **Factor de carga** = media / pico
- **Factor de potencia**: promedio de |FP| (C19); con «Todos», sumas de medias y de picos (C20)

### ☀️ Inversores e Indicadores Solares
- **Generación**, **potencia máxima**, **FP** y **frecuencia** mientras genera, **desbalances** de tensión y corriente
- **Performance Ratio** con la estación de la institución, validada contra la de referencia (C22)
- **Rendimiento específico** (kWh/kWp), **factor de capacidad**, **frente al diseño**, **cobertura solar**,
  **autoconsumo**, **ahorro estimado** (con el CU del comercializador, C13) y **CO₂ evitado**
- La **eficiencia DC/AC** no se calcula: el inversor solo reporta una de sus entradas MPPT

## 🔄 Tareas Programadas (Celery Beat)

Definidas en `CELERY_BEAT_SCHEDULE` (`core/settings.py`) y cargadas en la BD por el `DatabaseScheduler`. Horas de Bogotá:

| Tarea | Horario | Qué hace |
|---|---|---|
| `sync-scada-metadata-hourly` | cada hora, :00 | Sincroniza dispositivos, categorías e instituciones |
| `check-devices-status-hourly` | cada hora, :01 | Estado de los dispositivos |
| `repair-device-relationships-hourly` | cada hora, :02 | Repara relaciones dispositivo–institución |
| `ingest-and-calculate-hourly` | cada hora, :10 | Ingesta de las últimas 3 h y recálculo de indicadores |
| `reconcile-measurements-midnight` | 00:40 | Reconciliación y recálculo forzado del día de ayer (C15) |
| `reconcile-measurements-daily` | 01:30 | Reconciliación de hoy y los 35 días anteriores |
| `warm-solar-cache-daily` | 02:40 | Precalienta la caché por mes de Indicadores Solares |
| `sync-external-energy-daily` | 03:00 | Sincroniza los datos de XM |
| `calculate-energy-savings-daily` | 03:30 | Calcula los ahorros con los precios del día |
| `reconcile-measurements-6h` | 06:40, 12:40, 18:40 | Reconciliación de hoy y los 2 días anteriores |
| `refetch-verify-yesterday-daily` | deshabilitada | Sustituida por la reconciliación diaria |

## 📚 Documentación

### Guías Principales
- **[Despliegue en Producción](DEPLOYMENT_PRODUCTION.md)**: Guía completa de despliegue
- **[Scripts de Gestión](scripts/README.md)**: Documentación de scripts de automatización
- **[Frontend](frontend/README.md)**: Documentación del frontend React
- **[Indicadores](indicators/indicators.md)**: Metodología de cálculo de KPIs

### Módulos Especializados
- **[Datos Externos de Energía](external_energy/README.md)**: Integración con APIs externas (XM)
- **[Inicio Rápido - Datos Externos](external_energy/quick_start.md)**: Configuración rápida

### Diseño e informes
- **[Corrección de ingesta e indicadores (oct-2026)](docs/superpowers/specs/2026-10-10-correccion-ingesta-e-indicadores-design.md)**: hallazgos C1–C22, decisiones y registro de cambios
- **[Informe HUDN para la visita de ICONTEC](docs/informes/2026-10-hudn-icontec/README.md)**: cifras de la planta del HUDN desde el 2025-04-04

### Referencia técnica
- **[Análisis Backend/Frontend](BACKEND_FRONTEND_ANALYSIS.md)**: troubleshooting y fallas comunes de despliegue
- **Convenciones completas**: `.cursor/rules/*.mdc` y `CLAUDE.md`

## 🛠️ Comandos de Gestión Útiles

### Desarrollo y Pruebas
```bash
# Ver logs
docker-compose -f docker-compose.prod.yml logs -f

# Ver estado de servicios
docker-compose -f docker-compose.prod.yml ps

# Reiniciar servicios
docker-compose -f docker-compose.prod.yml restart

# Crear backup
./scripts/deploy_production.sh backup  # Linux/Mac
```

### Mantenimiento
```bash
# Verificar salud
./scripts/deploy_production.sh health  # Linux/Mac

# Rollback
./scripts/deploy_production.sh rollback  # Linux/Mac

# Limpiar recursos
docker system prune -f
```

## 🚨 Solución de Problemas

### Error: Puerto en uso
```bash
# Verificar puertos
netstat -an | findstr :80    # Windows
netstat -tulpn | grep :80    # Linux/Mac
```

### Error: Docker no responde
```bash
# Windows
Restart-Service -Name "com.docker.service"

# Linux/Mac
sudo systemctl restart docker
```

### Error: Base de datos no conecta
```bash
# Verificar logs
docker logs mte_postgres_prod

# Reiniciar base de datos
docker-compose -f docker-compose.prod.yml restart db
```

## 📈 Estado de Desarrollo

### ✅ Funcionalidades operativas
- Autenticación por token con expiración/refresh, rate limiting y bloqueo temporal; modo invitado de solo lectura
- Dashboard, Medidores, Inversores, Estaciones e Indicadores Solares, con selector de rango, disponibilidad de datos
  y versión móvil
- Ingesta horaria del conector SCADA en tablas tipadas (esquema v2) y reconciliación diaria con el conector
- Integración con el mercado XM (`external_energy`, `pydataxm`)
- Cálculo de indicadores en Celery + capa `services/` (funciones puras, vistas finas), con caché por mes
- Reportes en PDF/Excel/CSV
- Despliegue en producción en Docker bajo Apache, subruta `/sive/`

### 🔧 Historia reciente
- **Julio de 2026 (Olas 0–5)**: migración del frontend de CRA a **Vite**; lógica de indicadores en `indicators/services/`;
  esquema v2 de mediciones; auditoría de las tarjetas KPI; selector de rango en español, disponibilidad de datos y
  versión móvil (18-jul)
- **Octubre de 2026 (corrección C1–C22, rama `correccion-indicadores-2026-10`, desplegada el 10-oct)**: reconciliación de
  mediciones (D1) y backfill desde mayo de 2026; energía por institución con la convención de la tesis y del mercado P2P;
  medidores integrados de la potencia (C17–C20); inversor con FP y frecuencia mientras genera y PR validado (C1–C5, C22);
  reposición de lecturas perdidas sueltas (C21); ahorro con la tarifa al usuario (C13); pantalla Indicadores Solares;
  modo invitado
- **21 de octubre de 2026**: PR de Inversores con las reglas de Indicadores Solares, alertas, cupos y XM configurables
  desde `.env`, el CI con todas las suites (236 pruebas), ayuda integrada al día y correcciones del frontend
  (`f42ca0a`, `5048d56`, `34b5e14`); la energía de Inversores también igual a la de Indicadores Solares, con el
  histórico recalculado desde el 2024-12-01 (`ec12df7`); después, la energía de Inversores (día, mes, gráfica y detalle horario) sale de
  la misma energía horaria con la reposición de lecturas sueltas (C21) que Indicadores Solares

### 🎯 Pendiente
- Destino de las alertas: el compose ya pasa `ALERT_WEBHOOK_URL`, `ALERT_EMAIL_TO` y `EMAIL_*`, pero por decisión del
  autor el `.env` de producción no define ningún canal hasta que haya uno institucional; las alertas quedan en el log
- Irradiancia POA para un PR en el plano de los módulos (hoy es con irradiancia horizontal)

## 🤝 Contribución

Las contribuciones son bienvenidas:

1. **Fork** del repositorio
2. **Crear** una rama para tu funcionalidad
3. **Commit** tus cambios
4. **Push** a la rama
5. **Crear** un Pull Request

### Guías de Contribución
- Sigue las convenciones de código del proyecto
- Incluye pruebas para nuevas funcionalidades
- Actualiza la documentación según sea necesario

## 📞 Soporte y Contacto

### Canales de Soporte
- **Issues del Proyecto**: Reportar bugs y solicitar funcionalidades
- **Documentación**: Guías de usuario y técnica
- **Sistema de Ayuda**: Integrado en la aplicación

### Información del Proyecto
- **Código BPIN**: 2021000100499
- **Tipo**: Sistema de Visualización Energético
- **Ubicación**: Departamento de Nariño, Colombia
- **Estado**: en producción bajo `/sive/`

## 📄 Licencia

La licencia de SIVE está pendiente de definición por la Universidad de Nariño, titular del software en el marco
del proyecto MTE. Mientras no haya un archivo `LICENSE` en el repositorio, no se otorga ninguna licencia de uso,
modificación ni redistribución.

## 🙏 Agradecimientos

- **Equipo de Desarrollo**: Por la implementación técnica robusta
- **Usuarios**: Por el feedback y pruebas continuas
- **Comunidad Open Source**: Por las librerías y herramientas utilizadas
- **Instituciones Colaboradoras**: Por el apoyo y recursos proporcionados

---

**Última Actualización**: Octubre 2026 (corrección de ingesta e indicadores C1–C22, reconciliación con el conector, Indicadores Solares y modo invitado).
