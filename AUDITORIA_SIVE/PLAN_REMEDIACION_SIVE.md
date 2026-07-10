# Plan de Remediación por Olas — SIVE

_Derivado de `REPORTE_AUDITORIA_SIVE.md` (156 hallazgos, 12 dimensiones). Priorización por **riesgo activo × severidad × esfuerzo × dependencias**, deduplicando hallazgos que son la misma causa raíz vista desde varias dimensiones._

> **Cómo leer esto:** cada ola es una tanda entregable y verificable. Las referencias `[dim:línea]` apuntan al hallazgo en el reporte. Un mismo arreglo puede cerrar varios hallazgos a la vez (marcado como **cierra N**). El esfuerzo es del arreglo agrupado, no de cada hallazgo suelto.

## Resumen de olas

| Ola | Tema | Ventana | Esfuerzo | Cierra (aprox.) | Por qué ahora |
|---|---|---|---|---|---|
| **0** | Contención: seguridad activa + pérdida de datos | 1–3 días | Bajo/Medio | 🔴2 🟠6 🟡2 | Detiene fuga de datos, exposición y riesgo de pérdida total de la BD |
| **1** | Integridad y corrección de datos | Semana 1 | Medio | 🔴1 🟠3 🟡4 | Los KPIs que ve el usuario hoy son incorrectos |
| **2** | Resiliencia, CVEs y observabilidad | Semana 2 | Bajo/Medio | 🔴2 🟠5 🟡3 🔵4 | Parchea CVEs y hace que los fallos dejen de ser invisibles |
| **3** | Rendimiento, API y código muerto | Semanas 3–4 | Medio | 🟠3 🟡8 🔵5 | Latencia, crecimiento no acotado y limpieza que desbloquea lo demás |
| **4** | Frontend, accesibilidad y tests | Mes 2 | Medio/Alto | 🟠9 🟡~25 🔵~10 | Calidad de uso y red de seguridad para no regresar |
| **5** | Deuda estratégica | Backlog | Alto | 🟠1 🟡~6 ⚪ | Migraciones grandes; planificar, no improvisar |

---

## Ola 0 — Contención inmediata (1–3 días)

**Objetivo:** parar el daño que ya está ocurriendo. Nada aquí requiere rediseño; casi todo es esfuerzo bajo. **Hacer primero.**

1. **Backups reales de la BD** · medio · `[despliegue:56]` + rollback roto `[despliegue:72]`
   La BD de 4.3 GB no tiene ni un dump válido (los `pre_deploy_backup_*.sql` están en 0 bytes; el último con contenido es de sep-2025). Un fallo de disco = pérdida total. **Acción:** cron/sidecar con `pg_dump -Fc`, verificación de tamaño >0, retención (7 diarios + 4 semanales), copia off-host, y dejar de silenciar `2>/dev/null` en el deploy. Validar el rollback una vez de verdad.

2. **Bypass de autenticación por `cache_page`** · medio · **cierra 3** `[api-drf:560]` `[bd-rendimiento:659]` `[seguridad:308]`
   La clave de caché no incluye `Authorization`; tras calentarla un usuario logueado, un cliente **sin token** recibe el 200 cacheado (verificado en `dashboard/summary` y `weather-indicators`). Es fuga de datos, no solo rendimiento. **Acción:** no servir caché antes de `IsAuthenticated`; cachear dentro de `get()` tras validar, o mover el caché a la capa de servicio.

3. **IDOR de reportes y `/media/` abierto** · bajo/medio · **cierra 3** `[seguridad:284]` `[arquitectura:166]` `[seguridad:288]`
   Cualquier usuario autenticado descarga reportes de otros; `/media/` sirve reportes y avatares sin auth. **Acción:** validar propiedad (`request.user`) en descarga/estado; servir `/media/` protegido (vista con permiso o `X-Accel-Redirect`).

4. **SECRET_KEY de desarrollo en producción + `.env` legible** · bajo · **cierra 2** `[despliegue:64]` `[seguridad:292]`
   Clave `django-insecure-` firmando sesiones admin/CSRF, en `.env` con permisos 664 y credenciales legacy. **Acción:** `get_random_secret_key()`, `chmod 600 .env`, purgar variables no usadas (`password_postgres`, `wsl_*`, `password_SIVE`).

5. **Backend/frontend expuestos en 0.0.0.0 HTTP plano** · bajo · `[despliegue:60]`
   Tokens viajarían en claro puenteando el TLS de Apache. **Acción:** bindear a `127.0.0.1:...` y ajustar los health checks del deploy script.

6. **Disco del host al 87%** · bajo · `[despliegue:68]`
   Postgres corrompe el cluster si el disco se llena; sin backups (punto 1) el riesgo se multiplica. **Acción:** limpieza coordinada de imágenes/containers muertos de otros stacks + alerta simple >85%.

7. **Contraseña de Redis débil** · bajo · **cierra 2** `[despliegue:80]` `[seguridad:300]`
   `defaultpassword` visible en `docker inspect`. **Acción:** cambiarla en `.env` y rotar.

**Criterio de salida:** dump válido verificado; `curl` sin token a endpoints cacheados → 401; descarga de reporte ajeno → 403; puertos solo en loopback; SECRET_KEY nueva; disco <85%.

---

## Ola 1 — Integridad y corrección de datos (semana 1)

**Objetivo:** los KPIs y gráficos que el usuario ve **hoy** son incorrectos. Esto los arregla. Es el núcleo de la dimensión calidad-datos.

1. **🔴 Roll-over de contadores no filtrado** · medio · `[calidad-datos:696]` — **el peor hallazgo de la auditoría**
   Energía por medidor con valores imposibles (499.950.000 kWh/día en device 29; factor de carga hasta 77M %). Se propaga al mensual. **Acción:** en el cálculo por contador, descartar deltas negativos o > umbral físico (potencia_nominal×24h), tratar `delta<0` como reset; recalcular `ElectricMeterIndicators` diario+mensual tras el filtro.

2. **Eficiencia DC-AC imposible (>100% en 91% de inversores)** · medio · `[calidad-datos:708]`
   El crudo trae `dcPower < acPower` en el 92% de filas (dc ≈ 0.55×ac; `dcVoltage` negativo en 47%). **Acción:** confirmar semántica de `dcPower`/`dcVoltage` con el equipo del **scada-connector** (dato de entrada, no del repo); mientras tanto clampear eficiencia a [0,100] y marcar inversores afectados como "dato dudoso".

3. **DailyChartData con hueco de 4 meses** · bajo · `[calidad-datos:700]`
   Sin filas mar–jun 2026 pese a haber crudo → gráficos del dashboard con agujero. **Acción:** reejecutar `calculate_and_save_daily_data` para 2026-02-26..2026-07-01 + verificación de continuidad de días.

4. **Tablas de consumo por medidor vacías → reportes vacíos** · medio · **cierra 2** `[calidad-datos:704]` `[arquitectura:162]`
   `ElectricMeterEnergyConsumption/Consumption/ChartData` en 0 filas; los reportes "Resumen de Consumo" y "Balance Energético" leen esas tablas y salen siempre sin datos. **Acción:** decidir poblarlas (activar la periódica) o retirarlas y reapuntar los reportes a las tablas v2 vivas.

5. **Salud de dispositivos no modelada** · bajo · **cierra 3** `[calidad-datos:716]` `[calidad-datos:712]` `[observabilidad:231]`
   35/35 `is_active=True` incluidos ~14 muertos hace meses y 2 "prueba" que nunca reportaron. **Acción:** tarea periódica que fije `last_seen`/`is_active=False` cuando `max(date) > 48h`, excluir inactivos de los KPIs de flota, desactivar los "prueba". (Esto también sienta la base de la alerta de frescura de la Ola 2.)

6. **Outliers no físicos en estaciones** · medio · `[calidad-datos:720]`
   Viento 472 km/h, irradiancia negativa y >1968 W/m². **Acción:** validar rangos físicos en ingesta/agregación (irradiancia 0–1500, viento 0–150) antes de promediar.

**Criterio de salida:** 0 filas con `imported_energy_kwh` imposible; `dc_ac_efficiency_pct ≤ 100`; DailyChartData sin huecos; reportes con datos; KPIs de flota solo sobre equipos vivos.

---

## Ola 2 — Resiliencia, CVEs y observabilidad (semana 2)

**Objetivo:** parchear vulnerabilidades conocidas y lograr que **un humano se entere cuando algo falla**.

1. **Pasada de CVEs de dependencias** · bajo · **cierra 3** `[dependencias:113]` `[dependencias:117]` `[dependencias:133]`
   Django 5.2.4 (~20 CVEs, varios SQL injection) → **5.2.16**; Pillow 11.3 (6 CVEs, procesa avatares subidos) → **12.3.0**; requests 2.32.4 → 2.34.2. Todo drop-in en la misma serie. Correr la suite en el contenedor y reconstruir.

2. **Alerting mínimo (hoy: cero alertas)** · bajo · **cierra 2** `[observabilidad:227]` `[observabilidad:231]`
   Ningún mecanismo avisa de errores ni caídas. **Acción:** notificación (email/webhook) ante fallo de tarea Celery y ante frescura de datos vencida (reusa el `last_seen` de la Ola 1).

3. **Tareas Celery que tragan excepciones y terminan en SUCCESS** · bajo/medio · **cierra 4** `[observabilidad:243]` `[arquitectura:170]` `[celery:613]` `[celery:609]`
   Errores devueltos como string e ignorados por substring-match; retries declarados pero inertes; chord post-ingesta sin `link_error`. **Acción:** propagar excepciones reales, `link_error` en el chord, activar `autoretry_for`/`retry_backoff` de forma consistente.

4. **Health check ampliado** · medio · `[observabilidad:235]`
   No cubre connector SCADA, Celery beat ni frescura del pipeline. **Acción:** extender `/health/` con esos tres checks.

5. **Logs persistentes y rotados** · bajo · **cierra 4** `[observabilidad:239]` `[despliegue:88]` `[celery:637]` `[observabilidad:263]`
   `celery.log` en ruta efímera sin rotación, `./logs` montado sin uso, Gunicorn sin access log. **Acción:** `RotatingFileHandler` (o solo consola + driver Docker), montar el volumen, activar access log.

6. **`GET /local/measurements/` sin paginación** · medio · `[arquitectura:158]`
   Puede materializar 9,2M filas en memoria (DoS de memoria). **Acción:** paginación + rango por defecto obligatorio.

7. **Endurecimiento de exposición** · bajo · **cierra 4** `[seguridad:304]` `[seguridad:296]` `[seguridad:316]` `[despliegue:100]`
   Headers de seguridad (CSP/Referrer-Policy) definidos pero no aplicados; `X-Forwarded-For` no confiable colapsa el rate-limit a la IP del proxy; admin y OpenAPI públicos. **Acción:** aplicar headers, configurar `USE_X_FORWARDED_HOST`/proxy de confianza, restringir admin/docs.

**Criterio de salida:** `pip freeze` en versiones parcheadas y suite verde; un fallo forzado de tarea genera alerta; `/health/` refleja connector/beat/frescura; logs sobreviven al redeploy.

---

## Ola 3 — Rendimiento, API y código muerto (semanas 3–4)

**Objetivo:** latencia, crecimiento no acotado y limpieza que reduce superficie para todo lo demás.

1. **external-energy: fetch síncrono a XM → Celery** · medio · **cierra 2** `[bd-rendimiento:663]` `[api-drf:580]`
   `generation` cold=1.57s (único >1s), sin persistir. **Acción:** tarea periódica que persista en modelo (patrón `energy_prices`) y la vista lee de BD; de paso arregla `renewable_percentage` siempre 0.

2. **Índices y N+1** · bajo · **cierra 4** `[bd-rendimiento:667]` `[bd-rendimiento:683]` `[bd-rendimiento:671]` `[arquitectura:218]`
   ~57MB de índices `device_id` redundantes + duplicados en indicators; N+1 en `ElectricMeterEnergyViewSet`/`InverterChartDataView`. **Acción:** `db_index=False` en las FK cubiertas por el compuesto (+ migración DROP INDEX), quitar `models.Index` duplicados, añadir `select_related`.

3. **Rango/paginación uniformes en weather** · bajo · **cierra 2** `[bd-rendimiento:675]` `[arquitectura:218]`
   Payload de 1.08MB sin acotar. **Acción:** aplicar `resolve_indicators_date_range` (31d por defecto, 366 máx) igual que los demás.

4. **Política de retención de tablas v2** · medio · `[bd-rendimiento:679]`
   metermeasurement en 3.6GB, +12k filas/día sin cota. **Acción:** retención/archivado de crudo >N meses (ya calculado en indicadores) como tarea Celery. _(El particionado declarativo queda para la Ola 5.)_

5. **Contratos y validación de API** · bajo/medio · **cierra 4** `[api-drf:564]` `[api-drf:588]` `[api-drf:572]` `[api-drf:576]`
   `chart-data` 500→400 ante fecha inválida; `time_range` inválido devuelve 200 vacío; contratos inconsistentes entre los 3 endpoints; external_energy sin `@extend_schema`. **Acción:** validación explícita → 400, homogeneizar respuestas, documentar en OpenAPI.

6. **Barrido de código muerto** · medio · **cierra 3** `[arquitectura:174]` `[api-drf:584]` `[arquitectura:186]`
   3 modelos con 0 filas, 2 tareas, ~470 líneas de helpers, 7 rutas 404 en `apiConfig.js`, métricas siempre-cero (PR/irradiancia/temp) y `PnomPV` hardcodeado en InverterIndicators. **Acción:** eliminar tras confirmar 0 consumidores; documentar lo retirado.

**Criterio de salida:** ningún endpoint >1s en warm; índices redundantes eliminados; retención activa; fechas inválidas → 400; `apiConfig.js` sin rutas muertas.

---

## Ola 4 — Frontend, accesibilidad y tests (mes 2)

**Objetivo:** calidad de uso y una red de seguridad para no reintroducir regresiones. Muchos ítems de esfuerzo bajo agrupados por área.

**Frontend / higiene de producción** (bajo, cierra ~6):
- Paneles de depuración visibles y **token impreso en consola** `[frontend:390]` `[accesibilidad:483]` `[frontend:406]` — quitar ya (roza seguridad).
- Manejo de 401: redirige a `/` fuera de `/sive` y expulsa al portal WordPress `[frontend:382]` `[accesibilidad:487]`; pantallas de detalle con `fetch` crudo sin 401 `[frontend:386]` — unificar en `fetchWithAuth`.
- Refresh de token definido pero nunca usado (sesiones expiran de golpe) `[frontend:442]` `[arquitectura:198]`.
- Marca obsoleta "Sistema MTE" `[accesibilidad:519]`, enlaces muertos y reset por `alert()` `[accesibilidad:523]`, `console.log` ×110 `[frontend:406]`, 57 warnings ESLint `[frontend:402]`.

**Accesibilidad** (medio, cierra ~8): teclado inoperable `[accesibilidad:491]`, `lang="en"` en app español `[accesibilidad:495]` `[frontend:434]`, modales sin semántica de diálogo/Escape `[accesibilidad:499]`, contraste WCAG `[accesibilidad:503]`, `aria-live` en estados `[accesibilidad:531]`, labels sin `htmlFor` `[accesibilidad:547]`, estados de reportes/dispositivos en inglés `[accesibilidad:515]`, estados vacíos deshonestos (0 vs N/D) `[accesibilidad:511]` `[frontend:458]`.

**Tests / CI** (medio, cierra ~9): scripts `test_*.py` de diagnóstico que serían peligrosos bajo pytest `[tests:337]` (arreglar antes de meter CI); tests de pipeline chord `[tests:329]`, ingesta v2 `[tests:333]`, endpoints `[tests:341]`, reportes `[tests:345]`, cálculos KPI/inversores/estaciones `[tests:349]`; instalar pytest-cov `[tests:361]`; **CI que corra la suite** `[tests:357]`; smoke test único de frontend `[tests:365]`.

**Criterio de salida:** sin debug ni tokens en consola; app operable por teclado; `lang="es"`; CI verde en cada push; cobertura medible con línea base.

---

## Ola 5 — Deuda estratégica (backlog, planificar aparte)

**Objetivo:** cambios grandes que necesitan su propio diseño. No improvisar dentro de una ola corta.

- **Migración CRA → Vite** · alto · `[dependencias:121]` — react-scripts 5.0.1 abandonado, 55 vulns npm sin fix real dentro de CRA, no soporta React 19 oficialmente. Es el único arreglo de fondo del audit de npm. (De paso: Node 18→22 `[dependencias:129]`, split requirements `[dependencias:125]`.)
- **Refactor de god-modules** · alto · `[arquitectura:178]` `[arquitectura:182]` `[frontend:410]` — `indicators/tasks.py` (3.430 líneas) y `views.py` (2.858) sin capa de servicios; duplicación entre categorías de dispositivo; componentes React con lógica cuadruplicada. Extraer capa de servicios/hooks compartidos.
- **Routing SPA + drawer móvil** · alto · `[accesibilidad:535]` `[accesibilidad:507]` — URLs por pantalla, botón "atrás" funcional, uso en móvil.
- **Particionado declarativo de tablas v2** — extensión natural de la retención (Ola 3) para `DROP` barato de particiones antiguas.
- **Versionado de API** · `[api-drf:596]` y backfill de precios XM 2024-12..2025-11 `[calidad-datos:724]`.

---

## Notas de secuenciación

- **Ola 0 antes que nada**: la fuga por `cache_page`, el IDOR y la ausencia de backups son daño en curso.
- **Ola 1 depende de Ola 0 solo operativamente** (tener backup antes de recalcular masivamente). El recálculo del roll-over reescribe indicadores: hacerlo con un dump reciente a mano.
- **La salud de dispositivos (Ola 1.5) alimenta el alerting de frescura (Ola 2.2)** — hacerlas en ese orden.
- **La limpieza de código muerto (Ola 3.6) antes del refactor (Ola 5)**: no refactorizar lo que se va a borrar.
- **Los scripts `test_*.py` peligrosos (Ola 4) antes de montar CI**: un `pytest` ciego los ejecutaría como si fueran tests.
- **Dependencia externa**: la eficiencia DC-AC (Ola 1.2) requiere confirmar con el equipo del scada-connector; el resto es todo dentro de este repo.
