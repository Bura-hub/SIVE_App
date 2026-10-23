# Scripts

Los de Bash se corren en el servidor desde la raíz del repositorio y leen el `.env` sin ejecutarlo. Los de Python se
corren dentro del contenedor del backend. Los que escriben en la base lo hacen de forma idempotente.

| Script | Para qué | Uso |
|---|---|---|
| `deploy_production.sh` | Actualizar producción, comprobar la salud, respaldar y volver atrás. Detalle en [`DEPLOYMENT_PRODUCTION.md`](../DEPLOYMENT_PRODUCTION.md) | `./scripts/deploy_production.sh deploy\|health\|backup\|rollback [--con-base]\|ssl\|help` |
| `deploy_production.ps1` | La misma lógica en PowerShell | `.\scripts\deploy_production.ps1 deploy\|health\|backup\|rollback [-ConBase]\|ssl\|help` |
| `run_deployment.ps1` | Atajo que llama a `deploy_production.ps1`, también con `-ConBase` | `.\scripts\run_deployment.ps1 rollback -ConBase` |
| `backup_db.sh` | Respaldo verificado de la base con `pg_dump -Fc`. Aborta si el volcado queda vacío o ilegible. Conserva 7 diarios, 4 semanales y 10 manuales | `./scripts/backup_db.sh [--weekly\|--manual]` |
| `backfill_mediciones.sh` | Vuelve a descargar del conector las mediciones de un rango y recalcula sus indicadores, con un respaldo manual previo | `./scripts/backfill_mediciones.sh 2026-05-01 2026-10-11` (el segundo día no se incluye) |
| `recalcular_historico.sh` | Recalcula con las fórmulas vigentes todos los indicadores guardados de un rango. Encola las tareas en Celery, que siguen en el *worker* cuando el *script* termina | `./scripts/recalcular_historico.sh 2025-02-01 2026-10-10` (ambos días incluidos) |
| `audit_indicators.py` | Recalcula la energía integrando la potencia y la compara con lo guardado. Solo lee | `docker compose -f docker-compose.prod.yml exec backend python scripts/audit_indicators.py [--days 30]` |
| `count_db_records.py` | Cuenta las filas de las tablas principales | `docker compose -f docker-compose.prod.yml exec backend python scripts/count_db_records.py` |
| `validate_resync.py` | Compara las mediciones guardadas con las del conector tras una resincronización masiva | `docker compose -f docker-compose.prod.yml exec backend python scripts/validate_resync.py [--quick\|--sample N]` |

`deploy_production.sh ssl` crea un certificado autofirmado en `ssl/`. Producción no lo usa, porque el TLS lo termina
Apache.

Los registros de los *scripts* quedan en `logs/` y los respaldos, en `backups/`. Ni los registros ni los respaldos
entran en el control de versiones.

En Windows, si PowerShell bloquea los *scripts*, se habilitan para la sesión con
`Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process`.
