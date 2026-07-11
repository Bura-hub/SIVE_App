# Quick Wins de Rendimiento MTE/SIVE — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reducir la lentitud percibida de la app atacando los 3 focos (carga inicial, latencia de API, interacción React) con 9 cambios de bajo esfuerzo y alto impacto.

**Architecture:** Cambios independientes agrupados por artefacto de despliegue: **Grupo A (frontend)** = un rebuild de la imagen `frontend`; **Grupo B (backend)** = un rebuild de `backend`/`celery_*`. Sin migraciones de BD.

**Tech Stack:** React 19 + Vite, Chart.js/react-chartjs-2, nginx (SPA), Django 5.2 + DRF, gunicorn, django-redis, Docker Compose.

## Global Constraints

- **Commits:** NUNCA incluir `Co-Authored-By` ni ninguna firma de Claude.
- **Idioma:** mensajes de cara al usuario y comentarios de negocio en Español; identificadores en Inglés.
- **Ejecución Django:** todo `manage.py`/tests corre DENTRO del contenedor: `docker compose -f docker-compose.prod.yml exec backend python manage.py <cmd>`.
- **Despliegue:** `build` puede correr desde `/proyecto`; **`up`/recreación de contenedores debe correr desde la ruta real** `/home/insuasti/iteracion2/SIVE_App/SIVE_App` (bind mounts relativos). Este documento marca los pasos de `up` como acción del usuario.
- **Sin migraciones** en esta ola.
- **Spec de referencia:** `docs/superpowers/specs/2026-07-11-rendimiento-quick-wins-design.md`.

---

## Estructura de archivos afectados

**Grupo A — Frontend**
- Crear: `frontend/src/components/bg.webp` (reemplaza `bg.png`)
- Modificar: `frontend/src/components/LoginPage.js` (import + fondo, QW1)
- Modificar: `frontend/nginx.conf` (gzip svg, QW2)
- Modificar: `frontend/src/components/sive-logo.svg` (SVGO, QW2)
- Modificar: `frontend/src/components/KPI/ChartCard.jsx` (Intl hoist + tooltip, QW4)
- Modificar: `frontend/src/components/InverterDetails.js`, `ElectricalDetails.js`, `WeatherStationDetails.js`, `ExternalEnergyData.js` (useMemo, QW3)
- Modificar: `frontend/index.html` (preconnect, QW5)

**Grupo B — Backend**
- Modificar: `core/settings.py` (CONN_MAX_AGE QW6 + GZipMiddleware QW8)
- Modificar: `indicators/views.py` (caché segura de flota, QW7)
- Crear: `tests/test_dashboard_cache.py` (contrato de caché/seguridad, QW7)
- Modificar: `Dockerfile.backend` + `docker-compose.prod.yml` (gunicorn gthread, QW9)

---

## GRUPO A — FRONTEND

### Task 1: QW1 — `bg.png` (690 KB) → `bg.webp` (~100 KB)

**Files:**
- Create: `frontend/src/components/bg.webp`
- Modify: `frontend/src/components/LoginPage.js:3` (import), `:407-409` (fondo)

**Interfaces:**
- Produces: activo `bg.webp` importado como `background` en `LoginPage`.

- [ ] **Step 1: Convertir el PNG a WebP redimensionado (contenedor efímero con Pillow)**

Desde `/proyecto`:
```bash
docker run --rm -v "$PWD/frontend/src/components:/imgs" python:3.12-slim \
  sh -c "pip install -q pillow && python -c \"from PIL import Image; im=Image.open('/imgs/bg.png').convert('RGB'); w,h=im.size; nw=1400; im=im.resize((nw,int(nw*h/w))); im.save('/imgs/bg.webp','WEBP',quality=80,method=6)\""
```

- [ ] **Step 2: Verificar el tamaño resultante**

Run: `ls -l frontend/src/components/bg.webp`
Expected: archivo presente, **< 160 KB** (vs 690 KB del PNG). Si supera 200 KB, bajar `quality` a 72 y repetir.

- [ ] **Step 3: Cambiar el import en `LoginPage.js:3`**

De:
```js
import background from './bg.png';
```
A:
```js
import background from './bg.webp';
```

- [ ] **Step 4: Añadir color de fondo de respaldo en el contenedor (`LoginPage.js:407-409`)**

De:
```jsx
        <div 
            className="min-h-screen flex items-center justify-center bg-cover bg-center bg-no-repeat p-4 font-inter relative overflow-hidden"
            style={{ backgroundImage: `url(${background})` }}
        >
```
A:
```jsx
        <div 
            className="min-h-screen flex items-center justify-center bg-cover bg-center bg-no-repeat p-4 font-inter relative overflow-hidden"
            style={{ backgroundColor: '#0f172a', backgroundImage: `url(${background})` }}
        >
```

- [ ] **Step 5: Borrar el PNG viejo y compilar**

Run:
```bash
rm frontend/src/components/bg.png
cd frontend && npm run build
```
Expected: build sin errores; ningún `Cannot find module './bg.png'`.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/bg.webp frontend/src/components/LoginPage.js
git rm --cached frontend/src/components/bg.png 2>/dev/null; git add -A frontend/src/components/
git commit -m "perf(frontend): fondo del login PNG 690KB -> WebP ~100KB"
```

---

### Task 2: QW2 — nginx comprime SVG + optimizar `sive-logo.svg`

**Files:**
- Modify: `frontend/nginx.conf:18`
- Modify: `frontend/src/components/sive-logo.svg`

- [ ] **Step 1: Añadir `image/svg+xml` a `gzip_types` (`nginx.conf:18`)**

De:
```nginx
    gzip_types text/plain text/css text/xml text/javascript application/javascript application/xml+rss application/json;
```
A:
```nginx
    gzip_types text/plain text/css text/xml text/javascript application/javascript application/xml+rss application/json image/svg+xml application/manifest+json;
```

- [ ] **Step 2: Inspeccionar si el SVG lleva raster embebido**

Run: `grep -c "data:image" frontend/src/components/sive-logo.svg`
Expected: `0` → es SVG vectorial, optimizable con SVGO (continúa en Step 3). Si es `>= 1` → lleva un raster base64 (por eso pesa 168 KB); en ese caso **omite SVGO** y anota en el commit que el logo debería rasterizarse a WebP en una tarea de seguimiento (fuera de alcance de este quick win). Salta al Step 5.

- [ ] **Step 3: Optimizar con SVGO**

Run: `npx --yes svgo frontend/src/components/sive-logo.svg -o frontend/src/components/sive-logo.svg`
Expected: SVGO reporta un porcentaje de reducción.

- [ ] **Step 4: Verificar tamaño y que sigue siendo un SVG válido**

Run: `ls -l frontend/src/components/sive-logo.svg && head -c 60 frontend/src/components/sive-logo.svg`
Expected: menor tamaño que 168 KB; empieza por `<svg` o `<?xml`.

- [ ] **Step 5: Compilar**

Run: `cd frontend && npm run build`
Expected: build sin errores.

- [ ] **Step 6: Commit**

```bash
git add frontend/nginx.conf frontend/src/components/sive-logo.svg
git commit -m "perf(frontend): comprimir SVG en nginx y optimizar sive-logo"
```

---

### Task 3: QW4 — `ChartCard`: hoistear `Intl.NumberFormat` + `tooltip.mode: 'nearest'`

**Files:**
- Modify: `frontend/src/components/KPI/ChartCard.jsx` (imports/top-level ~línea 1-30; `:243`, `:260-263`, `:331-333`)

**Interfaces:**
- Produces: constantes de módulo `NF2` (2 decimales) y `NF1` (1 decimal) reutilizadas en los callbacks.

- [ ] **Step 1: Declarar los formateadores a nivel de módulo**

Justo después de los `import` (antes de `function ChartCard(...)` / `const ChartCard = ...`), añadir:
```js
// Formateadores es-ES reutilizados: crear un Intl.NumberFormat por punto/tick era
// un coste notable en cada frame de hover. Se instancian una sola vez a nivel de módulo.
const NF2 = new Intl.NumberFormat('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const NF1 = new Intl.NumberFormat('es-ES', { maximumFractionDigits: 1 });
```

- [ ] **Step 2: Cambiar `tooltip.mode` a `'nearest'` (`ChartCard.jsx:243`)**

De:
```js
        mode: 'index',
```
A:
```js
        mode: 'nearest',
```

- [ ] **Step 3: Reusar `NF2` en el callback del tooltip (`:259-263`)**

De:
```js
            if (context.parsed.y !== null) {
              label += new Intl.NumberFormat('es-ES', { 
                maximumFractionDigits: 2,
                minimumFractionDigits: 2
              }).format(context.parsed.y);
            }
```
A:
```js
            if (context.parsed.y !== null) {
              label += NF2.format(context.parsed.y);
            }
```

- [ ] **Step 4: Reusar `NF1` en el callback de ticks del eje Y (`:330-334`)**

De:
```js
          callback: function(value) {
            return new Intl.NumberFormat('es-ES', {
              maximumFractionDigits: 1
            }).format(value);
          }
```
A:
```js
          callback: function(value) {
            return NF1.format(value);
          }
```

- [ ] **Step 5: Compilar**

Run: `cd frontend && npm run build`
Expected: build sin errores.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/KPI/ChartCard.jsx
git commit -m "perf(charts): reutilizar Intl.NumberFormat y tooltip nearest en ChartCard"
```

---

### Task 4: QW3 — Memoizar el `data` de las gráficas en las 4 pantallas de detalle

**Files:**
- Modify: `frontend/src/components/InverterDetails.js`, `ElectricalDetails.js`, `WeatherStationDetails.js`, `ExternalEnergyData.js`

**Interfaces:**
- Consumes: `useMemo` de React (añadir a los imports si falta).
- Produces: por pantalla, una fila memoizada `<x>Rows` y un objeto `data` memoizado por cada `<ChartCard>`.

**Patrón a aplicar (idéntico en las 4 pantallas).** Hoy cada gráfica hace `data={{ labels: X.results.slice().reverse().map(...), datasets: [...slice().reverse().map...] }}` inline → objeto nuevo por render → `chart.update()` animado en TODAS las gráficas al paginar/abrir modal. Se corrige en dos pasos: (a) calcular las filas invertidas UNA vez con `useMemo`; (b) lift de cada objeto `data` a un `useMemo` sobre esas filas.

- [ ] **Step 1: Asegurar `useMemo` importado en las 4 pantallas**

En cada archivo, si el import de React no lo trae, cambiar (ejemplo):
```js
import React, { useState, useEffect } from 'react';
```
por:
```js
import React, { useState, useEffect, useMemo } from 'react';
```

- [ ] **Step 2: `InverterDetails.js` — fila memoizada + `data` memoizados**

Antes del `return (` del componente, añadir la fila base:
```js
  // Filas en orden cronológico ascendente, calculadas una sola vez por cambio de datos.
  const invRows = useMemo(
    () => (inverterData?.results ? inverterData.results.slice().reverse() : []),
    [inverterData]
  );
```
Para CADA `<ChartCard ... data={{...}} />` de este archivo (charts en el rango ~874-1078), extraer su objeto `data` a un `useMemo` situado junto a `invRows` y referenciarlo en el JSX. Ejemplo con la gráfica "Análisis de Generación Fotovoltaica" (`:874-915`):

Declarar arriba:
```js
  const generationChartData = useMemo(() => ({
    labels: invRows.map(item => new Date(item.date + 'T00:00:00').toLocaleDateString('es-ES')),
    datasets: [
      {
        label: 'Energía Total Generada (kWh)',
        data: invRows.map(item => item.total_generated_energy_kwh || 0),
        borderColor: '#10B981',
        backgroundColor: 'rgba(16, 185, 129, 0.1)',
        fill: true,
        tension: 0.4,
        pointRadius: 4,
        pointBackgroundColor: '#10B981',
        pointBorderColor: '#ffffff',
        pointBorderWidth: 2,
      },
      {
        label: 'Potencia Máxima (kW)',
        data: invRows.map(item => (item.max_power_w || 0) / 1000),
        borderColor: '#8B5CF6',
        backgroundColor: 'rgba(139, 92, 246, 0.1)',
        fill: false,
        tension: 0.4,
        pointRadius: 4,
        borderDash: [8, 4],
        pointBackgroundColor: '#8B5CF6',
        pointBorderColor: '#ffffff',
        pointBorderWidth: 2,
      }
    ]
  }), [invRows]);
```
Y en el JSX sustituir `data={{ ... }}` por `data={generationChartData}`. Repetir para cada gráfica del archivo (una const `<nombre>ChartData` por gráfica, dependencia `[invRows]`; si el `data` usa además un filtro/estado, añadirlo a las dependencias). No tocar la prop `options`.

- [ ] **Step 3: `ElectricalDetails.js` — mismo patrón**

Añadir junto al `return`:
```js
  const meterRows = useMemo(
    () => (meterData?.results ? meterData.results.slice().reverse() : []),
    [meterData]
  );
```
Extraer a `useMemo([meterRows, ...])` el `data` de cada `<ChartCard>` (gráficas en ~709, ~802, ~867) y referenciarlo en el JSX, igual que en el Step 2. Usar el nombre real de la variable de estado de esta pantalla si no es `meterData` (verificar en el archivo).

- [ ] **Step 4: `WeatherStationDetails.js` — mismo patrón**

```js
  const weatherRows = useMemo(
    () => (weatherData?.results ? weatherData.results.slice().reverse() : []),
    [weatherData]
  );
```
Extraer el `data` de cada gráfica (~885-1156) a `useMemo([weatherRows, ...])`. Usar el nombre real de la variable de estado si difiere.

- [ ] **Step 5: `ExternalEnergyData.js` — mismo patrón**

Identificar la variable de resultados de esta pantalla y crear su fila memoizada análoga; extraer el `data` de cada gráfica (~475, 586, 649, 717) a `useMemo`. Si esta pantalla NO invierte los datos (`.slice().reverse()`), memoizar el `data` directamente sobre la fuente sin invertir.

- [ ] **Step 6: Compilar y correr los tests de frontend**

Run:
```bash
cd frontend && npm run build && npm test -- --run
```
Expected: build sin errores; los tests existentes pasan (o el runner reporta "no tests" sin fallos).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/InverterDetails.js frontend/src/components/ElectricalDetails.js frontend/src/components/WeatherStationDetails.js frontend/src/components/ExternalEnergyData.js
git commit -m "perf(frontend): memoizar data de graficas en pantallas de detalle"
```

---

### Task 5: QW5 — Preconnect a Google Fonts

**Files:**
- Modify: `frontend/index.html:6`

- [ ] **Step 1: Añadir preconnect antes del `<link>` de la fuente (`index.html:6`)**

De:
```html
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
```
A:
```html
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
```

- [ ] **Step 2: Compilar**

Run: `cd frontend && npm run build`
Expected: build sin errores; el `index.html` del build incluye los `preconnect`.

- [ ] **Step 3: Commit**

```bash
git add frontend/index.html
git commit -m "perf(frontend): preconnect a Google Fonts para la fuente Inter"
```

---

### Task 6: Build y despliegue del frontend (cierre del Grupo A)

**Files:** ninguno (acción de build/deploy).

- [ ] **Step 1: Build de la imagen frontend** (puede correr desde `/proyecto`)

Run: `docker compose -f docker-compose.prod.yml build frontend`
Expected: build OK.

- [ ] **Step 2: (ACCIÓN DEL USUARIO) Levantar desde la ruta real**

Indicar al usuario que ejecute, desde `/home/insuasti/iteracion2/SIVE_App/SIVE_App`:
```bash
docker compose -f docker-compose.prod.yml up -d frontend
```
y recargue el navegador con `Ctrl+Shift+R`.

- [ ] **Step 3: Verificación en el navegador**

- Login se ve idéntico (fondo WebP + color de respaldo `#0f172a`).
- DevTools > Network (caché deshabilitada): el fondo pesa ~100 KB (no 690 KB); `sive-logo.svg` llega con `content-encoding: gzip`.
- Paginar la tabla en Inversores/Medidores/Estaciones NO re-anima las gráficas (DevTools > Performance sin picos de `chart.update` al paginar). Hover fluido; tooltip legible.

---

## GRUPO B — BACKEND

### Task 7: QW6 — `CONN_MAX_AGE` (conexiones Postgres persistentes)

**Files:**
- Modify: `core/settings.py:142-154`

- [ ] **Step 1: Añadir `CONN_MAX_AGE` y `CONN_HEALTH_CHECKS` al `DATABASES['default']`**

De:
```python
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
```
A:
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('name_db'),
        'USER': os.getenv('user_postgres'),
        'PASSWORD': os.getenv('password_user_postgres'),
        'HOST': os.getenv('POSTGRES_HOST', 'db'),
        'PORT': os.getenv('port_postgres', '5432'),
        # Reutiliza la conexión TCP hasta 60s en vez de abrir/cerrar una por request.
        'CONN_MAX_AGE': 60,
        'CONN_HEALTH_CHECKS': True,
        'OPTIONS': {
            'options': '-c client_encoding=UTF8'
        }
    }
}
```

- [ ] **Step 2: Verificar que Django carga la config (check)**

Run: `docker compose -f docker-compose.prod.yml exec backend python manage.py check`
Expected: `System check identified no issues`.

- [ ] **Step 3: Commit**

```bash
git add core/settings.py
git commit -m "perf(backend): CONN_MAX_AGE 60s para conexiones Postgres persistentes"
```

---

### Task 8: QW8 — `GZipMiddleware` (comprimir JSON de la API)

**Files:**
- Modify: `core/settings.py:90-102`

- [ ] **Step 1: Añadir `GZipMiddleware` al inicio de `MIDDLEWARE`**

`GZipMiddleware` debe ir lo antes posible; se coloca justo tras `SecurityMiddleware` y antes de `WhiteNoiseMiddleware`. De:
```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # WhiteNoise sirve los estáticos (admin/DRF/Swagger) directamente desde gunicorn,
    # sin depender de un servidor de archivos aparte. Debe ir justo tras SecurityMiddleware.
    'whitenoise.middleware.WhiteNoiseMiddleware',
```
A:
```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # Comprime las respuestas de la API (JSON). La API usa auth por token en header
    # (no cookies de sesión para datos), por lo que el riesgo BREACH es bajo.
    'django.middleware.gzip.GZipMiddleware',
    # WhiteNoise sirve los estáticos (admin/DRF/Swagger) directamente desde gunicorn,
    # sin depender de un servidor de archivos aparte. Debe ir justo tras SecurityMiddleware.
    'whitenoise.middleware.WhiteNoiseMiddleware',
```

- [ ] **Step 2: Verificar el check**

Run: `docker compose -f docker-compose.prod.yml exec backend python manage.py check`
Expected: sin issues.

- [ ] **Step 3: Commit**

```bash
git add core/settings.py
git commit -m "perf(backend): GZipMiddleware para comprimir respuestas JSON de la API"
```

---

### Task 9: QW7 — Caché de flota segura para el dashboard summary

**Files:**
- Modify: `indicators/views.py:53-56` (decoradores + clase) y `:90-101` (inicio de `get`), `:301` (set antes del return)
- Create: `tests/test_dashboard_cache.py`

**Interfaces:**
- Consumes: `from django.core.cache import cache` (añadir al import si falta).
- Produces: `ConsumptionSummaryView` con caché global manual (clave `dashboard:summary:v1`, TTL 300s) que se consulta DESPUÉS de la autenticación de DRF.

**Motivo (seguridad):** `@cache_page` a nivel `dispatch` cortocircuita ANTES de que DRF autentique; con clave común serviría datos de flota a anónimos. La caché manual dentro de `get()` se ejecuta tras `permission_classes=[IsAuthenticated]`, así que un anónimo recibe 401 y nunca ve datos. Además la clave es global (no por token), así que todos los usuarios autenticados comparten el hit y las llamadas SCADA solo ocurren en el miss.

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/test_dashboard_cache.py`:
```python
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APITestCase

DASHBOARD_URL = '/api/dashboard/summary/'


class DashboardSummaryCacheTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(
            username='tester', password='pw12345'
        )

    def tearDown(self):
        cache.clear()

    def test_anonymous_gets_401_and_never_cached_data(self):
        """Un request sin token NO recibe datos de flota cacheados: 401."""
        cache.set('dashboard:summary:v1', {'totalConsumption': {'value': 'SECRETO'}}, 300)
        response = self.client.get(DASHBOARD_URL)
        self.assertEqual(response.status_code, 401)

    def test_authenticated_hit_short_circuits_before_scada(self):
        """En cache-hit se devuelven los datos SIN llamar a SCADA."""
        payload = {'totalConsumption': {'value': '123'}, 'hasData': True}
        cache.set('dashboard:summary:v1', payload, 300)
        self.client.force_authenticate(user=self.user)
        with patch('indicators.views.scada_client') as mock_scada:
            response = self.client.get(DASHBOARD_URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['totalConsumption']['value'], '123')
        mock_scada.get_token.assert_not_called()
```

- [ ] **Step 2: Correr el test — debe fallar**

Run: `docker compose -f docker-compose.prod.yml exec backend python manage.py test tests.test_dashboard_cache -v 2`
Expected: FALLA. `test_authenticated_hit_short_circuits_before_scada` falla porque hoy `get()` llama a `get_scada_token()` antes de mirar la caché (`mock_scada.get_token` SÍ se llama). `test_anonymous...` podría pasar ya (permiso), pero el conjunto no pasa entero.

- [ ] **Step 3: Añadir el import de `cache` en `indicators/views.py`**

Junto a los otros imports de Django (cerca de `from django.views.decorators.cache import cache_page`), añadir:
```python
from django.core.cache import cache
```

- [ ] **Step 4: Quitar los decoradores `cache_page`/`vary_on_headers` de `ConsumptionSummaryView` y añadir constantes de caché (`:53-56`)**

De:
```python
@method_decorator(cache_page(60 * 5), name='dispatch')
@method_decorator(vary_on_headers('Authorization'), name='dispatch')
class ConsumptionSummaryView(APIView):
    permission_classes = [IsAuthenticated]
```
A:
```python
class ConsumptionSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    # Caché GLOBAL (no por token): la respuesta es data de flota idéntica para todos los
    # usuarios autenticados. Se consulta dentro de get(), DESPUÉS de que DRF autentique,
    # para no exponer datos a anónimos (a diferencia de cache_page a nivel dispatch).
    CACHE_KEY = 'dashboard:summary:v1'
    CACHE_TTL = 60 * 5
```

- [ ] **Step 5: Consultar la caché al inicio de `get()` (antes de tocar SCADA, `:90-96`)**

De:
```python
    def get(self, request, *args, **kwargs):
        """
        GET /api/dashboard/summary/
        
        Obtiene el resumen de consumo, generación y balance energético mensual.
        """
        token = self.get_scada_token()
        if isinstance(token, Response):
            return token
```
A:
```python
    def get(self, request, *args, **kwargs):
        """
        GET /api/dashboard/summary/
        
        Obtiene el resumen de consumo, generación y balance energético mensual.
        """
        cached = cache.get(self.CACHE_KEY)
        if cached is not None:
            return Response(cached)

        token = self.get_scada_token()
        if isinstance(token, Response):
            return token
```

- [ ] **Step 6: Guardar en caché antes del return exitoso (`:300-301`)**

De:
```python
            }
            return Response(kpi_data)
```
A:
```python
            }
            cache.set(self.CACHE_KEY, kpi_data, self.CACHE_TTL)
            return Response(kpi_data)
```

- [ ] **Step 7: Correr el test — debe pasar**

Run: `docker compose -f docker-compose.prod.yml exec backend python manage.py test tests.test_dashboard_cache -v 2`
Expected: PASS (2 tests).

- [ ] **Step 8: Correr la suite completa (no regresión)**

Run: `docker compose -f docker-compose.prod.yml exec backend python manage.py test`
Expected: todos verdes (los 87 previos + 2 nuevos).

- [ ] **Step 9: Commit**

```bash
git add indicators/views.py tests/test_dashboard_cache.py
git commit -m "perf(backend): cache global segura del dashboard summary (post-auth, sin round-trip SCADA en hit)"
```

> **Nota de alcance:** las otras 7 vistas con `cache_page`+`vary_on_headers` (`indicators/views.py:310,551,595,725,804,1177,1295`) quedan FUERA de esta ola. Cada una necesita verificarse individualmente (¿su payload depende de parámetros del usuario?) antes de convertirla al patrón seguro; se aborda en una tarea de seguimiento. No tocarlas aquí.

---

### Task 10: QW9 — Gunicorn a `gthread` con hilos

**Files:**
- Modify: `Dockerfile.backend:118`
- Modify: `docker-compose.prod.yml:143`

**Motivo:** el `command` de `docker-compose.prod.yml` es el que manda en prod (override del CMD). Se actualizan ambos por coherencia. Se mantienen **3 workers** para no aumentar la huella de memoria (límite del contenedor 512M) y se añaden **4 hilos** por worker: 12 requests concurrentes, ideal para la I/O bloqueante a SCADA/XM.

- [ ] **Step 1: Actualizar el CMD del Dockerfile (`Dockerfile.backend:118`)**

De:
```dockerfile
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120", "core.wsgi:application"]
```
A:
```dockerfile
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "--threads", "4", "--worker-class", "gthread", "--timeout", "120", "core.wsgi:application"]
```

- [ ] **Step 2: Actualizar el `command` del compose (`docker-compose.prod.yml:143`)**

De:
```yaml
             gunicorn --bind 0.0.0.0:8000 --workers 3 --timeout 120 --max-requests 1000 --max-requests-jitter 100 core.wsgi:application"
```
A:
```yaml
             gunicorn --bind 0.0.0.0:8000 --workers 3 --threads 4 --worker-class gthread --timeout 120 --max-requests 1000 --max-requests-jitter 100 core.wsgi:application"
```

- [ ] **Step 3: Commit**

```bash
git add Dockerfile.backend docker-compose.prod.yml
git commit -m "perf(infra): gunicorn gthread con 4 hilos por worker para I/O bloqueante"
```

---

### Task 11: Build y despliegue del backend (cierre del Grupo B)

**Files:** ninguno (build/deploy).

- [ ] **Step 1: Build de la imagen backend** (desde `/proyecto`)

Run: `docker compose -f docker-compose.prod.yml build backend`
Expected: build OK.

- [ ] **Step 2: (ACCIÓN DEL USUARIO) Recrear contenedores desde la ruta real**

Desde `/home/insuasti/iteracion2/SIVE_App/SIVE_App`:
```bash
docker compose -f docker-compose.prod.yml up -d backend celery_worker celery_beat
```

- [ ] **Step 3: Verificación end-to-end**

- **GZip:** `curl -s -o /dev/null -D - -H "Authorization: Token <token>" -H "Accept-Encoding: gzip" https://mte.udenar.edu.co/sive/api/dashboard/summary/ | grep -i content-encoding`
  Expected: `content-encoding: gzip`.
- **Seguridad de caché:** `curl -s -o /dev/null -w "%{http_code}\n" https://mte.udenar.edu.co/sive/api/dashboard/summary/`
  Expected: `401` (anónimo nunca recibe datos).
- **Hilos gunicorn:** `docker compose -f docker-compose.prod.yml logs backend | grep -i "Booting worker\|threads"` muestra el arranque; `docker stats --no-stream mte_backend_prod` → memoria estable bajo 512M.
- **Latencia:** primera carga del dashboard puebla la caché; recargas subsiguientes (dentro de 5 min) responden sin round-trip a SCADA.

---

## Self-Review (cobertura del spec)

- QW1 → Task 1 ✅ | QW2 → Task 2 ✅ | QW3 → Task 4 ✅ | QW4 → Task 3 ✅ | QW5 → Task 5 ✅
- QW6 → Task 7 ✅ | QW7 → Task 9 (con test de seguridad) ✅ | QW8 → Task 8 ✅ | QW9 → Task 10 ✅
- Builds/deploy por grupo → Task 6 (frontend) y Task 11 (backend) ✅
- Sin migraciones ✅ | Constraint de ruta real para `up` reflejado en Task 6/11 ✅ | Commits sin coautoría ✅
- Las 7 vistas de caché restantes se declaran explícitamente fuera de alcance (nota en Task 9) para no romper contratos sin verificación individual.
