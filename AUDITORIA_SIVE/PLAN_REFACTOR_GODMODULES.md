# Plan de refactor de god-modules (Ola 5)

> Estado a jul-2026. Objetivo: reducir los módulos gigantes a una arquitectura por capas,
> **sin cambiar comportamiento**, apoyándose en la red de 46 tests del CI como garantía de
> no-regresión. NO es una reescritura: es extracción incremental y verificable.

## 1. Estado actual (medido)

| Módulo | Líneas | Problema |
|---|---|---|
| `indicators/tasks.py` | 3.054 (39 funciones top-level) | Cálculo + orquestación Celery + acceso a datos mezclados |
| `indicators/views.py` | 2.404 | Vistas gruesas con lógica de negocio y de presentación |
| `frontend/.../InverterDetails.js` | 1.851 | 3 pantallas de detalle casi idénticas… |
| `frontend/.../WeatherStationDetails.js` | 1.800 | …con fetch/estado/gráficas duplicados |
| `frontend/.../ElectricalDetails.js` | 1.385 | |

**Duplicación núcleo (backend):** 6 funciones con la misma forma —
`_calculate_{daily,monthly}_{electrical,inverter,weather}_data` (3 categorías × 2 granularidades).
Cada trío comparte: ventana de fechas, lectura v2, saneamiento, agregación y `update_or_create`.

## 2. Objetivo (arquitectura destino)

```
indicators/
  services/                # lógica de negocio pura (sin Celery, sin HTTP)
    __init__.py
    date_ranges.py         # resolve_indicators_date_range, colombia_day_range (ya existen)
    sanitize.py            # _accumulate_register_energy, clamps de rango (ya existen)
    meter_calc.py          # cálculo de medidores (daily+monthly) sobre un queryset
    inverter_calc.py       # cálculo de inversores
    weather_calc.py        # cálculo de estaciones
    kpi.py                 # KPI mensual
  tasks.py                 # SOLO orquestación Celery: cada task llama a services/ y persiste
  views.py                 # SOLO HTTP: parse/validación -> services/ -> serializer
```

**Regla de oro:** `services/` no importa Celery ni DRF. `tasks.py` y `views.py` se vuelven
finos (envuelven a `services/`). Así el mismo cálculo es testeable sin BD de Celery/HTTP.

## 3. Decomposición concreta

### Backend — `indicators/tasks.py` → `services/`
1. **Extraer helpers ya puros** (bajo riesgo, ya cubiertos por tests): mover
   `_accumulate_register_energy`, `colombia_day_range`, `resolve_indicators_date_range`,
   `consumption_energy_kwh` a `services/sanitize.py` y `services/date_ranges.py`. Dejar
   re-exports en `tasks.py`/`views.py` para no romper imports (`from .services.sanitize import *`).
2. **Unificar el trío por categoría con una plantilla**: definir un `DeviceCalculator`
   (Strategy) con la parte común (ventana, lectura v2, agregación, persistencia) y 3
   subclases/descriptores que declaran solo lo específico (campos v2, saneamientos, campos
   de salida). Colapsa 6 funciones (~900 líneas) en ~1 base + 3 configs.
3. **`tasks.py` queda como envoltorios**: `calculate_electric_meter_indicators` pasa a
   `MeterCalculator(device, range).run()`; la task solo maneja `@shared_task`, `single_instance`,
   logging y errores (ya con `link_error`/alerting de la Ola 2).

### Backend — `indicators/views.py`
4. **Vistas finas**: cada `APIView.get` hace solo: validar params (helpers de `services/`),
   llamar al service, serializar. La lógica de `ChartDataView.format_energy_value` y cálculos
   de unidades → `services/formatting.py`.
5. **Serializers explícitos** para las respuestas que hoy se arman a mano con dicts.

### Frontend — 3 pantallas de detalle → hooks + componentes compartidos
6. **`useDeviceDetail(category, deviceId, range)`**: hook que encapsula el fetch con
   `fetchWithAuth`, estados de carga/error y normalización — hoy triplicado.
7. **`<DetailScreen>`** genérico + config por categoría (métricas, series, etiquetas). Las 3
   pantallas (~5.000 líneas) se reducen a 3 configs + 1 componente. Reusar `ChartCard`.

## 4. Secuencia (orden seguro)

> Cada paso: extraer → correr los 46 tests del CI → commit. Nunca dos capas a la vez.

1. **Preparación**: subir cobertura de los 6 `_calculate_*` a nivel de integración (ya hay
   medidor/inversor/estación; añadir monthly y net/gross de cada uno) — **red antes de tocar**.
2. Extraer helpers puros a `services/` (paso 3.1) — casi cero riesgo.
3. Introducir `DeviceCalculator` base y migrar **una** categoría (medidor), verde, commit.
4. Migrar inversor y estación a la base (3.2). Borrar las funciones viejas.
5. Adelgazar `tasks.py` (3.3) y luego `views.py` (3.4–3.5).
6. Frontend: `useDeviceDetail` + `<DetailScreen>`, migrar una pantalla, luego las otras dos.

## 5. Riesgos y mitigación

- **Regresión de cálculo** → la red de 46 tests (roll-over, DC-AC, rangos meteo, net/gross,
  KPI) es el gate. Ampliarla en el paso 4.1 antes de mover nada.
- **Imports rotos** → re-exports temporales desde `tasks.py`/`views.py` durante la transición.
- **Cambios de comportamiento sutiles** (TZ, redondeo) → los tests fijan los valores esperados.
- **Alcance** → hacerlo por PRs pequeños (uno por paso), no un big-bang.

## 6. Esfuerzo estimado (orientativo)

| Bloque | Esfuerzo |
|---|---|
| Ampliar tests (4.1) | S |
| `services/` + helpers (3.1) | S |
| `DeviceCalculator` + 3 categorías (3.2–3.3) | L |
| Vistas finas + serializers (3.4–3.5) | M |
| Frontend hooks + `<DetailScreen>` (3.6–3.7) | L |

**No hacer** en esta ola: cambiar la metodología de cálculo (eso es Ola 1, ya cerrada),
tocar el esquema de datos, ni mezclar con el particionado de tablas (ítem aparte de Ola 5).

## 7. Criterio de salida

- `indicators/tasks.py` y `views.py` < ~800 líneas cada uno.
- Las 6 funciones de cálculo colapsadas en 1 base + 3 configs.
- Las 3 pantallas de detalle sobre 1 componente + 3 configs.
- CI verde en cada paso; sin cambios en los valores que devuelven los endpoints.
