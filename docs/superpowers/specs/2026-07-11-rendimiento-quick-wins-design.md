# Spec: Rendimiento MTE/SIVE — Quick Wins (Ola de rendimiento)

**Fecha:** 2026-07-11
**Alcance elegido:** los 9 quick wins de la auditoría completa de rendimiento (frontend carga + runtime, backend/BD, infra). Los cambios "mayores" quedan documentados como backlog para iteraciones posteriores.
**Origen:** auditoría multiagente (4 dimensiones + síntesis). Todos los hallazgos verificados en archivo:línea antes de redactar.

## Diagnóstico (resumen)

La lentitud percibida tiene tres focos en gran parte independientes:

1. **Carga inicial (login):** assets pesados sin optimizar en la ruta crítica de todo usuario no autenticado (`bg.png` 690 KB, `sive-logo.svg` 168 KB que nginx ni comprime, fuente Inter bloqueante externa).
2. **Latencia de API (dashboard):** I/O externa síncrona a SCADA dentro del request, amplificada por gunicorn sync con 3 workers, sin conexiones Postgres persistentes, sin compresión de JSON, y una caché que se desperdicia por variar por token.
3. **Interacción/navegación (React):** el objeto `data` de cada gráfica se construye inline sin `useMemo`, disparando `chart.update()` animado en todas las gráficas ante cualquier cambio de estado (paginar, abrir modal). Formateadores `Intl` recreados por punto/tick.

Los quick wins atacan los tres focos sin refactors grandes.

---

## Cambios (9 quick wins)

Cada uno es independiente y verificable por separado. Agrupados por artefacto de despliegue.

### Grupo A — Frontend (un solo rebuild de imagen `frontend`)

#### QW1 — Optimizar `bg.png` del login (690 KB → ~80-120 KB)
- **Problema:** `frontend/src/components/bg.png` es un PNG 1392×752 de 690 KB (gzip no lo comprime, es foto). Se importa en `LoginPage.js:3` y se aplica como `backgroundImage` en `:409`. Es el activo más pesado del proyecto, en la ruta crítica del primer render.
- **Cambio:** recomprimir/redimensionar a **WebP** (~1400px de ancho, calidad ~80). Sustituir el import y el `url(...)` por el nuevo `bg.webp`. Mantener un fallback de color de fondo sólido en el contenedor por si el WebP no carga.
- **Archivos:** `frontend/src/components/bg.png` → `bg.webp`; `LoginPage.js:3,409`.
- **Riesgo:** bajo. WebP soportado por todos los navegadores objetivo. Verificación visual del login.

#### QW2 — Comprimir SVG en nginx + optimizar `sive-logo.svg`
- **Problema:** `sive-logo.svg` pesa 168 KB y `frontend/nginx.conf:18` (`gzip_types`) **no incluye `image/svg+xml`**, así que se sirve sin comprimir. Se carga en `LoginPage.js:2` y `Sidebar.js:2` (ruta inicial).
- **Cambio:** (a) añadir `image/svg+xml` (y `application/manifest+json`) a `gzip_types` en `nginx.conf:18`; (b) pasar **SVGO** al `sive-logo.svg` para recortar paths/metadata. Si el SVG lleva un raster embebido en base64 (lo que explicaría 168 KB), evaluar rasterizarlo a WebP pequeño — decidir tras inspeccionar el archivo.
- **Archivos:** `frontend/nginx.conf:18`; `frontend/src/components/sive-logo.svg`.
- **Riesgo:** bajo. Verificar que el logo se ve idéntico tras SVGO.

#### QW3 — `useMemo` del objeto `data` en las 4 pantallas de detalle
- **Problema:** `grep useMemo` = 0 en `InverterDetails.js`, `ElectricalDetails.js`, `WeatherStationDetails.js`, `ExternalEnergyData.js`. Cada `data={{...}}` se construye inline con `.slice().reverse().map(...)` repetido por serie → nueva identidad en cada render → `chart.update()` animado en todas las gráficas al paginar la tabla o abrir un modal. (Dashboard ya sube el `data` a `useState`, no aplica.)
- **Cambio:** por pantalla, calcular una vez `const rows = useMemo(() => results.slice().reverse(), [results])` y derivar cada objeto `data` de gráfica con su propio `useMemo` dependiente de `rows`/filtros. Referenciar la const memoizada en el JSX.
- **Archivos:** `InverterDetails.js` (charts ~878-1078), `ElectricalDetails.js` (~713,806,871), `WeatherStationDetails.js` (~889-1156), `ExternalEnergyData.js` (~475,586,649,717).
- **Riesgo:** medio-bajo. Asegurar que las dependencias del `useMemo` incluyen TODO lo que el `data` usa (results, filtros, unidades) para no congelar datos viejos.

#### QW4 — `ChartCard`: hoistear `Intl.NumberFormat` + `tooltip.mode: 'nearest'`
- **Problema:** `ChartCard.jsx:260` crea `new Intl.NumberFormat('es-ES', ...)` por cada punto del tooltip y `:331` por cada tick del eje Y. Con `tooltip.mode:'index'` (`:243`) se formatean TODOS los datasets del índice en cada frame de hover. `interaction.mode` ya es `'nearest'` (`:356`), así que `index` es incoherente y más caro.
- **Cambio:** definir a nivel de módulo `const NF2 = new Intl.NumberFormat('es-ES', {minimumFractionDigits:2, maximumFractionDigits:2})` y `NF1` (según lo que usen los callbacks), y reutilizarlos en `:260` y `:331`. Cambiar `tooltip.mode:'index'` → `'nearest'` en `:243`.
- **Archivos:** `frontend/src/components/KPI/ChartCard.jsx:243,260,331` (+ patrón duplicado en `InverterDetails.js:43,72` si aplica).
- **Riesgo:** bajo. Cambio visual menor: el tooltip mostrará la serie más cercana en vez de todas las del índice. Verificar que sigue siendo legible en gráficas multi-serie.

#### QW5 — Fuente Inter: preconnect (o auto-hospedaje)
- **Problema:** `frontend/index.html:6` carga Inter con `<link rel="stylesheet">` a `fonts.googleapis.com` — render-blocking y dependiente de red externa (frágil bajo CSP/subpath/sin salida a internet).
- **Cambio (mínimo, recomendado ahora):** añadir `<link rel="preconnect" href="https://fonts.googleapis.com">` y `<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>` antes del stylesheet. **Opción robusta (backlog):** auto-hospedar Inter (woff2 con `@font-face` + `font-display: swap`) para eliminar la dependencia externa.
- **Archivos:** `frontend/index.html:6`.
- **Riesgo:** bajo. El preconnect es puramente aditivo.

### Grupo B — Backend (rebuild de imagen `backend` + `celery_worker`/`beat`)

#### QW6 — `CONN_MAX_AGE` en Postgres (conexiones persistentes)
- **Problema:** `core/settings.py:142` `DATABASES` no define `CONN_MAX_AGE` → default 0 → Django abre y cierra una conexión TCP nueva a Postgres en cada request (handshake + auth por petición).
- **Cambio:** añadir `'CONN_MAX_AGE': 60` y `'CONN_HEALTH_CHECKS': True` al dict `DATABASES['default']`.
- **Archivos:** `core/settings.py:142-154`.
- **Riesgo:** bajo. Con Postgres y pocas conexiones, 60s es conservador. `CONN_HEALTH_CHECKS` (Django 4.1+, tenemos 5.2) evita servir conexiones muertas.

#### QW7 — Caché de flota compartida sin exponer data sin auth
- **Problema:** 8 vistas usan `@cache_page(60*5)` + `@vary_on_headers('Authorization')` (`indicators/views.py:53-54,310,551,595,725,804,1177,1295`). La respuesta es data de flota idéntica para todos, pero la clave varía por token → cada rotación/refresh de token es un cache-miss que re-dispara las llamadas SCADA síncronas.
- **⚠️ Matiz de seguridad (detectado al verificar):** NO basta con quitar `vary_on_headers`. `cache_page` a nivel `dispatch` cortocircuita **antes** de que DRF autentique; con clave común, un request sin token (o con token inválido) recibiría data de flota cacheada → **fuga de datos sin autenticación**. Hoy el `vary` por token lo mitiga por accidente (necesitas el token exacto).
- **Cambio (seguro):** reemplazar el par `cache_page`+`vary_on_headers` por **caché manual dentro de la vista, después de autenticar**, con clave **global** (no por token). Patrón: DRF autentica (permiso `IsAuthenticated` intacto) → `cache.get(key_global)` → si miss, computar y `cache.set(key_global, data, 300)`. Así el hit es compartido entre todos los usuarios autenticados y ningún anónimo ve data cacheada.
- **Alcance en esta ola:** aplicar el patrón seguro al **dashboard summary** (`ConsumptionSummaryView`, la de mayor impacto) y a las demás vistas de flota que sean data global no específica del usuario. Las vistas cuyo payload dependa de parámetros de usuario mantienen su clave variada por esos parámetros. Enumerar caso por caso en el plan de implementación (revisar cada una de las 8).
- **Archivos:** `indicators/views.py` (las 8 vistas listadas; empezar por `ConsumptionSummaryView`).
- **Riesgo:** medio. Requiere revisar cada vista para confirmar que su respuesta es realmente global. Verificación: un usuario anónimo (sin token) debe recibir 401, nunca data cacheada.

#### QW8 — Comprimir las respuestas de la API (JSON)
- **Problema:** el JSON de la API sale sin comprimir. `core/settings.py:90` `MIDDLEWARE` no incluye `GZipMiddleware`; el nginx del frontend solo comprime los assets del SPA, NO la API (que va por Apache→gunicorn). Apache proxya sin `mod_deflate`.
- **Cambio (decisión):** dos opciones —
  - **Opción A (recomendada por despliegue simple):** añadir `django.middleware.gzip.GZipMiddleware` al inicio de `MIDDLEWARE`. Solo rebuild de backend, sin tocar el Apache del host. La API usa auth por token en header (no cookies de sesión para data), así que el riesgo BREACH es bajo.
  - **Opción B (no gasta CPU de gunicorn):** `AddOutputFilterByType DEFLATE application/json` en los vhosts de Apache (`deploy/apache-sive.conf`, `deploy/mte-sive-ssl-vhost.conf`). Requiere editar el Apache del host y recargarlo (sudo).
  - **Elegido:** **Opción A** por simplicidad de despliegue (encaja con el flujo Docker existente). B queda anotada por si el CPU de gunicorn se vuelve el cuello (poco probable: hoy 0.03% CPU).
- **Archivos:** `core/settings.py:90-102`.
- **Riesgo:** bajo.

### Grupo C — Infra (rebuild de imagen `backend`; cambio en CMD/compose)

#### QW9 — Gunicorn a `gthread` con hilos + más workers
- **Problema:** gunicorn corre `--workers 3` clase **sync** (`Dockerfile.backend:118` y el override en `docker-compose.prod.yml:143`). Sync = un request bloqueante por worker; con I/O externa lenta (SCADA/XM) 3 requests lentos saturan los 3 workers y todo lo demás espera. El host tiene 32 vCPU y 25 GiB libres, infrautilizados; el contenedor está limitado a 1 GiB de memoria.
- **Cambio:** cambiar a `--worker-class gthread --threads 4 --workers 5` (valores iniciales conservadores dado el límite de 1 GiB; ajustables). Aplicar en **ambos** sitios pero recordar que el `command` de `docker-compose.prod.yml:143` es el que efectivamente manda en prod.
- **Archivos:** `Dockerfile.backend:118`, `docker-compose.prod.yml:143`.
- **Riesgo:** medio. Vigilar consumo de memoria del contenedor tras el cambio (`docker stats`); si se acerca al límite de 1 GiB, bajar workers/threads.

---

## Orden y estrategia de despliegue

Tres artefactos independientes; se pueden desplegar por grupos o todo junto:

1. **Frontend** (QW1-5): `npm run build` → `docker compose build frontend` → `up -d frontend`. Requiere `Ctrl+Shift+R` para saltar caché del navegador.
2. **Backend** (QW6-9): `docker compose build backend` → `up -d backend celery_worker celery_beat`.
3. Recordatorio operativo: `build` puede correr desde `/proyecto`, pero **`up`/recreación debe correr desde la ruta real** `/home/insuasti/iteracion2/SIVE_App/SIVE_App` por los bind mounts relativos (`./logs`, `./celerybeat-schedule`, `./init-db.sql`).

No hay migraciones en esta ola (el índice de BD es un "cambio mayor", fuera de alcance).

## Verificación (end-to-end)

- **Carga inicial:** DevTools > Network con caché deshabilitada en el login: el peso transferido total debe caer notablemente (bg de ~690 KB a ~100 KB; svg comprimido). Login visualmente idéntico.
- **API:** `curl -H "Authorization: Token <t>" -H "Accept-Encoding: gzip" <API>/…` debe devolver `Content-Encoding: gzip`. Un request **sin** token a las vistas de flota debe devolver **401**, nunca data (validación de seguridad de QW7). Latencia del dashboard summary estable en cache-hit compartido.
- **Interacción:** paginar la tabla en una pantalla de detalle NO debe re-animar las gráficas (DevTools > Performance: sin `chart.update` en el paginado). Hover fluido, tooltip legible.
- **Infra:** `docker stats mte_backend_prod` tras carga: memoria bajo 1 GiB; varios requests concurrentes no se serializan.
- **Tests backend:** `docker compose exec backend python manage.py test` (los 87 existentes siguen verdes; añadir test de QW7 que verifique 401 sin token en una vista de flota).

## Fuera de alcance (backlog — "cambios mayores")

Documentados para iteraciones futuras, en orden de impacto:
1. Sacar las llamadas SCADA del request path del dashboard (tarea Celery periódica que escribe "inversores activos"/estado en caché; la vista solo lee). **Causa dominante de latencia de API.**
2. Descomponer los god-components de detalle (1200-1546 líneas) en subcomponentes `React.memo`.
3. Índice compuesto `(date, device)` en las 3 tablas de mediciones (~1.4M filas) — acelera tareas Celery de KPI (requiere migración en ventana).
4. Aligerar el chunk Chart.js (tree-shaking del `register` + `chartjs-plugin-zoom` diferido) + `manualChunks`/Brotli en el build de Vite.
5. HTTP/2 + `enablereuse`/`keepalive` en el proxy Apache.
6. Paginar/aligerar los listados de indicadores y `chart-data` (arrays JSON horarios); combinar Min/Max en un `aggregate`; `assertNumQueries` anti-N+1.
