# Ola 0 — Runbook de ejecución (contención)

Estado tras esta sesión. Los cambios de **código/config** ya están hechos en la rama `feature/docker-setup` (pendientes de tu `git push` + deploy). Los pasos **operativos** los ejecutas tú en el host porque tocan secretos vivos, otros proyectos o requieren reinicio coordinado.

---

## ✅ Hecho en el repo (revisar diff + push + deploy)

| # | Ítem | Archivos | Efecto |
|---|---|---|---|
| 1 | Backup verificado de la BD | `scripts/backup_db.sh` (nuevo) | Script `-Fc`, aborta si vacío, verifica con `pg_restore --list`, retención 7+4. **Ya se generó `backups/sive_db_20260710_135958.dump` (280M) verificado.** |
| 2 | Bypass de `cache_page` | `indicators/views.py`, `external_energy/views.py` | `vary_on_headers('Authorization')` en 16 vistas → un anónimo no recibe la caché de un autenticado |
| 3 | IDOR descarga/estado de reportes | `indicators/tasks.py`, `indicators/views.py` | `get_report_file`/`get_report_status` filtran por `user_id`; las vistas pasan `request.user.id` |
| 3b | `/media/reports/` cerrado | `core/urls.py` | Los reportes solo salen por `/api/reports/download/` (con dueño); avatares siguen públicos |
| 5 | Puertos a loopback | `docker-compose.prod.yml` | Backend/frontend en `127.0.0.1` (Apache proxya); ya no en HTTP plano por `0.0.0.0` |

**Estos fixes se activan al reconstruir y desplegar el backend/frontend** (el contenedor corre el código viejo). Verificado a nivel de sintaxis (`py_compile`) y `docker compose config`; el runtime se valida tras el deploy (abajo).

### Deploy para activarlos
```bash
git push                                   # tú
docker compose -f docker-compose.prod.yml up -d --build backend frontend
```
> Nota puertos: `REACT_APP_API_URL` ya es `https://mte.udenar.edu.co/sive` (Apache), así que el bind a loopback NO rompe el frontend. **Pero** el `scripts/deploy_production.sh` hace health checks a `DOMAIN:PORT` directo — ajústalos a `127.0.0.1:PORT` o fallarán.

### Verificación post-deploy (copiar/pegar)
```bash
# cache_page: anónimo NO debe recibir 200 cacheado
curl -s -o /dev/null -w "anon dashboard => %{http_code}\n" http://127.0.0.1:3504/api/dashboard/summary/
# esperado: 401  (antes: 200 con datos)

# /media/reports cerrado
curl -s -o /dev/null -w "media reports => %{http_code}\n" http://127.0.0.1:3504/media/reports/cualquier.pdf
# esperado: 404

# suite backend
docker compose -f docker-compose.prod.yml exec backend python manage.py test
```

---

## ⏳ Operativo — ejecutar tú en el host

### 1. Instalar el backup en cron (item 1)
```bash
crontab -e
# añadir (ajusta la ruta absoluta al repo):
30 2 * * 1-6  cd /RUTA/REPO && ./scripts/backup_db.sh          >> logs/backup.log 2>&1
30 2 * * 0    cd /RUTA/REPO && ./scripts/backup_db.sh --weekly >> logs/backup.log 2>&1
```
Además, configura una **copia off-host** de `backups/` (rsync/scp a otra máquina): el volumen de Postgres vive en el mismo disco del host.

### 4. Rotar SECRET_KEY y blindar .env  (invalida sesiones de /admin — hazlo en ventana tranquila)
```bash
# generar clave nueva
NEW_KEY=$(docker compose -f docker-compose.prod.yml exec -T backend python -c "from django.core.management.utils import get_random_secret_key as g; print(g())")
# editar .env: reemplazar la línea SECRET_KEY=django-insecure-... por SECRET_KEY=$NEW_KEY
# (los tokens de la app viven en BD; solo caen sesiones de admin)
chmod 600 .env
# purgar variables legacy no usadas por el compose:
#   password_postgres, wsl_password, password_SIVE  (borrar esas líneas)
docker compose -f docker-compose.prod.yml up -d backend celery_worker celery_beat
```

### 6. Disco al 86% — limpieza COORDINADA (afecta a otros proyectos del host)
```bash
df -h /
docker system df                      # ver qué es reclamable
# NO ejecutar prune a ciegas: hay stacks de otros proyectos (qwc-docker, superset...).
# Coordinar con los dueños del host qué imágenes/containers parados se pueden borrar.
docker image prune -a --filter "until=720h"   # ejemplo conservador, revisar antes
```

### 7. Rotar contraseña de Redis (reinicio coordinado)
```bash
# editar .env: REDIS_PASSWORD=<nueva-contraseña-fuerte>
docker compose -f docker-compose.prod.yml up -d redis backend celery_worker celery_beat
# verificar que worker/beat reconectan:
docker compose -f docker-compose.prod.yml logs --tail=30 celery_worker
```

---

## Residual conocido (no bloquea Ola 0, va a olas siguientes)
- `ReportStatusView` tiene un fallback a Celery `AsyncResult` que aún revela *progreso* (no datos) de un `task_id` ajeno; el archivo sí está protegido. Se afina en Ola 2/3.
- El `deploy_production.sh` (rollback que restaura backups vacíos, `2>/dev/null` en el dump) sigue pendiente de endurecer — Ola 2. El nuevo `backup_db.sh` ya no tiene esos defectos; conviene que el deploy lo invoque.
