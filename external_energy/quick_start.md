# Inicio rápido: datos externos de energía (XM)

Guía corta para poner en marcha y comprobar la integración con XM. La descripción completa está en
[`README.md`](README.md).

## 1. Qué hace falta

Nada más que los servicios de SIVE. La API pública de XM no pide clave y `pydataxm` ya viene en `requirements.txt`.

Estas variables, todas opcionales, van en `.env` (ver `env.example`):

```bash
# Segundos máximos por consulta a XM
XM_API_TIMEOUT=30
# Solo si un proxy rompe el SSL
# PYDATAXM_VERIFY_SSL=false
# Cupo anónimo de las vistas que consultan XM en vivo
SIVE_GUEST_XM_RATE=30/min
```

## 2. Primera carga

Todo se ejecuta dentro de los contenedores:

```bash
# Precios de bolsa y datos del mercado de los últimos 30 días
docker compose -f docker-compose.prod.yml exec backend python manage.py shell -c \
  "from external_energy.tasks import sync_external_energy_data; print(sync_external_energy_data.delay().id)"

# Ahorro diario: los días que falten desde el 2025-02-25 y los últimos 40
docker compose -f docker-compose.prod.yml exec backend python manage.py shell -c \
  "from external_energy.tasks import calculate_energy_savings; print(calculate_energy_savings.delay().id)"
```

Después, Celery Beat repite cada día la sincronización con XM a las 03:00 y el ahorro a las 03:30 (hora de
Bogotá). Un superusuario también puede lanzar la sincronización con `POST /api/external-energy/sync/`.

## 3. Comprobar

```bash
# Series en vivo de XM (públicas, ver el campo "source")
curl -s "https://mte.udenar.edu.co/sive/api/external-energy/demand/?range=week" | head -c 400
curl -s "https://mte.udenar.edu.co/sive/api/external-energy/prices/?range=month" | head -c 400
curl -s "https://mte.udenar.edu.co/sive/api/external-energy/savings/?range=month" | head -c 400

# Registros guardados
docker compose -f docker-compose.prod.yml exec backend python manage.py shell -c \
  "from external_energy.models import EnergyPrice, EnergySavings, EnergyMarketData; \
   print(EnergyPrice.objects.count(), EnergyMarketData.objects.count(), EnergySavings.objects.count())"
```

En un despliegue en la raíz (sin el prefijo `/sive`), las rutas son `/api/external-energy/...`.

Las rutas y lo que devuelve cada una están en [`README.md`](README.md).

## 4. Problemas frecuentes

- `source: "unavailable"` en una serie. XM no respondió a tiempo o no tenía datos. Revise
  `docker compose -f docker-compose.prod.yml logs backend` y, si XM está lento, suba `XM_API_TIMEOUT`.
- Error de SSL con XM. Normalmente lo causa un proxy o cortafuegos. Como último recurso,
  `PYDATAXM_VERIFY_SSL=false`.
- `429 Too Many Requests` sin sesión. Es el cupo del modo invitado. Inicie sesión o ajuste `SIVE_GUEST_XM_RATE` y
  `SIVE_GUEST_READ_RATE`.
- Ahorro en 0 o vacío. El ahorro sale de las mediciones de las plantas y, sin lecturas de los medidores y de los
  inversores para esos días, no hay ahorro que calcular.

## 5. Datos simulados (solo desarrollo)

```bash
docker compose -f docker-compose.prod.yml exec backend python manage.py populate_external_energy_data --days 90
```

Llena las tablas con valores aleatorios marcados como simulados. No lo use en producción, porque mezcla datos inventados con
los reales de XM.
