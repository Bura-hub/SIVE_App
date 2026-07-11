# 🌟 MTE SIVE - Sistema de Visualización Energético

[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://www.docker.com/)
[![Django](https://img.shields.io/badge/Django-5.2.4-green.svg)](https://www.djangoproject.com/)
[![React](https://img.shields.io/badge/React-19.1.0-blue.svg)](https://reactjs.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17-blue.svg)](https://www.postgresql.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 📋 Descripción General

**MTE SIVE** es una aplicación web integral para la visualización de datos históricos e indicadores clave relacionados con el consumo y generación de energía eléctrica, así como variables climáticas relevantes. Construida con una arquitectura desacoplada utilizando **Django (Python)** para el backend y **React (JavaScript)** para el frontend.

### 🎯 Objetivo Principal
Transformar datos complejos en información accionable, proporcionando a analistas y ejecutivos una visión clara y dinámica del comportamiento de los sistemas energéticos y climáticos.

**Estado del Proyecto:** en producción bajo `https://mte.udenar.edu.co/sive/`, en fase de
remediación y refinamiento continuo (ver *Estado de Desarrollo* más abajo).

## 🚀 Características Principales

### 🔐 Autenticación y Seguridad
- **Sistema de Autenticación Robusto**: Login seguro con gestión de usuarios y roles
- **Gestión de Perfiles Avanzada**: Configuración de información personal, avatares y preferencias
- **Gestión de Sesiones**: Control de dispositivos conectados con capacidad de cerrar sesiones
- **Seguridad Mejorada**: Rate limiting, bloqueo temporal por intentos fallidos
- **Tokens de Acceso**: Sistema de autenticación basado en tokens con expiración automática

### 📊 Dashboard y Visualizaciones
- **Dashboard Interactivo**: Panel de control principal con resumen de indicadores clave (KPIs)
- **Visualizaciones Dinámicas**: Gráficos interactivos (líneas y barras) impulsados por Chart.js
- **KPIs en Tiempo Real**: Métricas actualizadas automáticamente para consumo, generación y balance energético
- **Persistencia de Estado**: Recuerda el estado de la barra lateral y pestañas activas

### 🔌 Módulos Especializados
- **Detalles Eléctricos**: Información detallada sobre el consumo eléctrico con filtros avanzados
- **Detalles de Inversores**: Métricas y tendencias de la generación de energía solar
- **Detalles del Clima**: Datos meteorológicos relevantes para el análisis energético
- **Datos Externos de Energía**: Análisis de precios, ahorros y mercado energético
- **Exportación de Reportes**: Generación y descarga de reportes en PDF, Excel y CSV

### ⚡ Integración SCADA y Procesamiento
- **Integración con API SCADA**: Conexión segura a través de proxy Django para datos en tiempo real
- **Cálculo Automático de KPIs**: Tareas asíncronas con Celery que calculan indicadores mensuales
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
curl -sk  https://mte.udenar.edu.co/sive/api/      # -> 401 (requiere auth)
curl -skI https://mte.udenar.edu.co/sive/          # -> 200 (index del frontend)
```

> Nota: los estáticos de admin/DRF se sirven con WhiteNoise; Apache quita el prefijo `/sive` y
> WhiteNoise sirve en `/django-static/`. La ruta crítica (frontend + API JSON) no depende de
> estáticos de Django.

## 📊 Indicadores Clave de Rendimiento (KPIs)

### 🔋 Consumo y Generación
- **Consumo Total**: Consumo acumulado de energía eléctrica (kWh)
- **Generación Total**: Generación acumulada de energía (kWh) por inversores
- **Equilibrio Energético**: Diferencia neta entre generación y consumo
- **Potencia Instantánea Promedio**: Promedio de potencia activa (Watts)

### 🌡️ Variables Climáticas
- **Temperatura Promedio Diaria**: Temperatura promedio (°C)
- **Humedad Relativa**: Humedad relativa promedio (%RH)
- **Velocidad del Viento**: Velocidad promedio del viento (km/h)
- **Irradiancia Solar**: Radiación solar promedio (W/m²)

### 📊 Métricas Operativas
- **Inversores Activos**: Conteo en tiempo real de inversores operativos
- **Eficiencia del Sistema**: Relación entre generación y capacidad instalada
- **Factor de Capacidad**: Utilización efectiva de la capacidad de generación
- **Autoconsumo**: Porcentaje de energía generada consumida localmente

## 🔄 Tareas Programadas (Celery Beat)

El sistema ejecuta automáticamente:
- **Metadatos SCADA**: Sincronización diaria a las 2:00 AM
- **KPIs Mensuales**: Cálculo diario a las 3:30 AM
- **Datos Diarios**: Procesamiento a las 3:45 AM
- **Mediciones Históricas**: Obtención cada hora

## 📚 Documentación

### Guías Principales
- **[Despliegue en Producción](DEPLOYMENT_PRODUCTION.md)**: Guía completa de despliegue
- **[Scripts de Gestión](scripts/README.md)**: Documentación de scripts de automatización
- **[Frontend](frontend/README.md)**: Documentación del frontend React
- **[Indicadores](indicators/indicators.md)**: Metodología de cálculo de KPIs

### Módulos Especializados
- **[Datos Externos de Energía](external_energy/README.md)**: Integración con APIs externas (XM)
- **[Inicio Rápido - Datos Externos](external_energy/quick_start.md)**: Configuración rápida

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
- Autenticación por token con expiración/refresh, rate limiting y bloqueo temporal
- Dashboard con KPIs (mensuales + inversores activos en tiempo real)
- Pantallas de detalle Eléctricos / Inversores / Estaciones (refactorizadas sobre el hook
  compartido `useDeviceDetail`) con filtros, cálculo y paginación
- Integración con API SCADA (proxy) y con el mercado XM (`external_energy`, `pydataxm`)
- Cálculo de indicadores en Celery + capa `services/` (funciones puras, vistas finas)
- Reportes en PDF/Excel/CSV
- Despliegue en producción en Docker bajo Apache, subruta `/sive/`

### 🔧 Remediación reciente (Olas 0–5)
- Migración del frontend de CRA a **Vite** (build/tests con Vitest)
- Extracción de la lógica de indicadores a `indicators/services/` y adelgazamiento de vistas
- Saneamiento anti roll-over de acumuladores y de rangos diarios (zona horaria Colombia)
- **Auditoría y saneamiento de las tarjetas KPI** de las 4 pantallas (info-al-click profesional,
  corrección de campos/agregaciones, rosa de vientos polar real)

### 🎯 Próximos pasos
- Mejora de **formato de reportes** (encabezados/paginación, resumen ejecutivo, logos)
- Organización de la documentación OpenAPI (tags/descripciones por endpoint)
- **Métricas normalizadas por capacidad** (kWh/kWp, Performance Ratio de flota, disponibilidad):
  requieren registrar la potencia nominal y disponer de irradiancia POA

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
- **Estado**: en producción bajo `/sive/`, en remediación y refinamiento continuo

## 📄 Licencia

Este proyecto está bajo la licencia MIT. Ver el archivo `LICENSE` para más detalles.

## 🙏 Agradecimientos

- **Equipo de Desarrollo**: Por la implementación técnica robusta
- **Usuarios**: Por el feedback y pruebas continuas
- **Comunidad Open Source**: Por las librerías y herramientas utilizadas
- **Instituciones Colaboradoras**: Por el apoyo y recursos proporcionados

---

**Última Actualización**: Julio 2026 (migración a Vite, capa `services/`, refactor de pantallas de detalle con `useDeviceDetail`, saneamiento de KPIs y despliegue bajo `/sive/`).
