# Datos externos de energía (XM)

La aplicación `external_energy` trae datos del mercado eléctrico colombiano desde **XM**, el operador del sistema, con
la librería `pydataxm`, y calcula el **ahorro** de las plantas del proyecto. Alimenta la pantalla «Datos Externos».

No hay otras integraciones ni hace falta una clave de API, porque la API pública de XM no la pide.

## Qué se consulta en XM

`services.py` (`XMRealAPIService` y su envoltorio `XMEnergyService`) pide estas métricas a nivel `Sistema`:

| Métrica de XM | Qué es | Unidad | Uso |
|---|---|---|---|
| `PrecBolsNaci` | Precio de bolsa nacional, horario | COP/kWh | Se promedia por día y se guarda en `EnergyPrice` |
| `Gene` | Generación real del sistema, horaria | kWh por hora | `/generation/` y la oferta diaria de `EnergyMarketData` |
| `DemaCome` | Demanda comercial, horaria | kWh por hora | `/demand/` y la demanda diaria de `EnergyMarketData` |
| `factorEmisionCO2e` | Factor de emisión del sistema, horario | gCO₂e/kWh | `/emissions/` |
| `ExpoEner` | Exportaciones de energía, horarias | kWh | `/exports/` |
| `ImpoEner` | Importaciones de energía, horarias | kWh | `/imports/` |

`pydataxm` no tiene tiempo de espera propio, así que cada consulta corre en un hilo con un límite de
`XM_API_TIMEOUT` segundos (30 por defecto). La verificación SSL se controla con `PYDATAXM_VERIFY_SSL` (activa por
defecto) y no se desactiva para el resto del proceso.

## Endpoints

Todos cuelgan de `/api/external-energy/`. Los `GET` son públicos en solo lectura, en modo invitado, y `sync/` pide un
superusuario. El parámetro `range` acepta `week` (7 días), `month` (30), `quarter` (90) y `year` (365). Un valor
desconocido se toma como 30 días.

| Método y ruta | Qué devuelve | Fuente | Rango por defecto | Caché | Cupo anónimo |
|---|---|---|---|---|---|
| `GET prices/` | Precio medio, máximo, mínimo, variación, tendencia, historial diario y datos del mercado del periodo | Base de datos. Si está vacía para el rango, consulta XM y guarda | `month` | 1 h | `anon_xm` |
| `GET savings/` | Ahorro, demanda, generación, autoconsumo, exportación, factor de capacidad, ROI y ahorro por mes | `EnergySavings` | `month` | No | `anon_read` |
| `GET market-overview/` | Último día de `EnergyMarketData`, los 7 precios más recientes y las alertas activas | Base de datos | (fijo) | 1 h | `anon_read` |
| `GET generation/` | Serie de `Gene` con media, máximo, mínimo y total | XM en vivo | `month` | 1 h | `anon_xm` |
| `GET demand/` | Serie de `DemaCome` | XM en vivo | `month` | 1 h | `anon_xm` |
| `GET emissions/` | Serie de `factorEmisionCO2e` | XM en vivo | `month` | 1 h | `anon_xm` |
| `GET exports/` | Serie de `ExpoEner` | XM en vivo | `week` | 1 h | `anon_xm` |
| `GET imports/` | Serie de `ImpoEner` | XM en vivo | `week` | 1 h | `anon_xm` |
| `POST sync/` | Encola `sync_external_energy_data` y responde 202 con el `task_id` | Celery | | | Solo superusuario |

Si XM no responde, las series devuelven listas vacías con `source: "unavailable"` en lugar de un error. El campo
`source` de `prices/` dice si los precios son de XM (`XM`), simulados (`simulated`), mezclados (`mixed`) o si no hay
(`none`).

Los esquemas están en Swagger (`/docs/`), bajo la etiqueta «Mercado Energético (XM)». `sync/` está en «Operación».

## Tareas programadas

Definidas en `CELERY_BEAT_SCHEDULE` (`core/settings.py`), en hora de Bogotá:

- **`sync-external-energy-daily`** (03:00), tarea `sync_external_energy_data`. Guarda en `EnergyPrice` el precio de
  bolsa medio de cada uno de los últimos 30 días y en `EnergyMarketData` la demanda y la oferta medias diarias en MW
  (de `DemaCome` y `Gene`) con el precio del día en COP/MWh. La composición por tecnología no se puede obtener de
  esas métricas y queda en 0.
- **`calculate-energy-savings-daily`** (03:30), tarea `calculate_energy_savings`. Calcula el ahorro diario de las
  plantas del proyecto.
  - Por institución y hora, toma la energía de `indicators/services/institution_energy.py`, es decir, demanda del
    Medidor 1, generación, autoconsumo y exportación.
  - Ahorro = energía autoconsumida × CU mensual del comercializador de la institución, en nivel de tensión 2 y sin
    contribución (`indicators/data/tarifas_cu.csv`). Un mes sin tarifa publicada usa la última anterior.
  - Guarda en `EnergySavings` la suma de las instituciones por día.
  - Recalcula siempre los últimos 40 días, para recoger las lecturas que llegan tarde, y los días que falten desde el
    2025-02-25. Con `start_date_str` y `end_date_str` recalcula un rango completo.

El ahorro no usa el precio de bolsa, que es lo que cuesta la energía en el mercado mayorista y no lo que paga una
institución.

## Cálculos de `savings/`

Sobre los días del rango en `EnergySavings`:

- **Ahorro total** y **costo evitado**: la suma del ahorro diario (son la misma cifra).
- **Porcentaje de ahorro**: energía autoconsumida / demanda.
- **Autoconsumo**: energía autoconsumida / generación.
- **Factor de capacidad**: generación / (capacidad instalada × horas del periodo), con la capacidad de
  `indicators/institution_config.py` (5 plantas de 17,55 kWp).
- **ROI**: ahorro / costo de la instalación, con `SOLAR_INSTALLATION_COST_COP` (50 000 000 COP por defecto).

## Modo invitado

Sin sesión se pueden leer todos los `GET`. El tráfico anónimo tiene cupos por IP (`core/throttling.py`):

- `anon_read`, para las lecturas públicas en general, con `SIVE_GUEST_READ_RATE`, 120/min por defecto.
- `anon_xm`, más estricto, para las vistas que pueden consultar XM en vivo, con `SIVE_GUEST_XM_RATE`, 30/min por defecto.

La IP del cliente se toma del último salto de `X-Forwarded-For` según `SIVE_NUM_PROXIES`, 1 por defecto, que es
Apache delante del backend. Los usuarios con sesión usan el cupo normal de usuario.

## Modelos

- `EnergyPrice`: precio de bolsa medio por día (COP/kWh) y su fuente.
- `EnergyMarketData`: demanda, oferta y precio del mercado por día.
- `EnergySavings`: ahorro diario de las plantas.
- `EnergyPriceForecast` y `EnergyAlert`: existen en el modelo, pero ninguna tarea los llena, solo el comando de datos
  simulados.

## Datos simulados

`python manage.py populate_external_energy_data [--days 90] [--clear]` llena las tablas con datos aleatorios para
desarrollo. Esos precios llevan `source = 'ElectricityMaps'`, aunque no vienen de ningún servicio, y `prices/` los
marca como `simulated`. No se usa en producción.

## Variables de entorno

| Variable | Por defecto | Para qué |
|---|---|---|
| `XM_API_TIMEOUT` | 30 | Segundos máximos por consulta a XM |
| `PYDATAXM_VERIFY_SSL` | `true` | Verificación SSL de las consultas a XM |
| `SOLAR_INSTALLATION_COST_COP` | 50000000 | Costo de la instalación para el ROI |
| `SIVE_GUEST_READ_RATE` | `120/min` | Cupo anónimo general |
| `SIVE_GUEST_XM_RATE` | `30/min` | Cupo anónimo de las vistas que consultan XM |
| `SIVE_NUM_PROXIES` | 1 | Proxies de confianza delante del backend |

`docker-compose.prod.yml` las pasa al backend y a los dos servicios de Celery. Están en `env.example`.

## Pruebas

```bash
docker compose -f docker-compose.prod.yml exec backend python manage.py test tests.test_external_energy_fixes tests.test_savings_cu tests.test_guest_mode
```

`tests/test_external_energy.py` es un guion de diagnóstico que se corre a mano contra una base real y no forma parte
de la suite.
