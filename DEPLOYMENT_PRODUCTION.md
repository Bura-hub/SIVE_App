# Despliegue en producción

SIVE se publica en `https://mte.udenar.edu.co/sive/` como una ruta del dominio, con el Apache y el certificado que ya
tiene el servidor. Los contenedores escuchan solo en el *loopback* y no se abren puertos nuevos.

```
Navegador ──HTTPS──> Apache (:443, certificado de mte.udenar.edu.co)
   /sive/api, /auth, /admin, /docs, /health, ...  ──(sin /sive)──> 127.0.0.1:3504  backend (gunicorn)
   /sive/django-static/                           ───────────────> 127.0.0.1:3504  (WhiteNoise)
   /sive/ (el resto)                              ───────────────> 127.0.0.1:3503  frontend (nginx)
```

Apache quita el prefijo `/sive` y Django lo vuelve a poner en sus URL con `FORCE_SCRIPT_NAME`. El frontend carga sus
archivos con rutas relativas y la API está en el mismo origen, así que no hay CORS ni contenido mixto.

Todas las órdenes se corren en el servidor, desde la raíz del repositorio. El proyecto de Compose es `mtesive_app`.

## Primera instalación

1. Crear el `.env` desde `env.example` con las credenciales reales y estos valores para la ruta `/sive/`:

   ```env
   DEBUG=False
   ALLOWED_HOSTS=localhost,127.0.0.1,mte.udenar.edu.co
   CORS_ALLOWED_ORIGINS=https://mte.udenar.edu.co
   CSRF_TRUSTED_ORIGINS=https://mte.udenar.edu.co
   VITE_API_URL=https://mte.udenar.edu.co/sive
   FORCE_SCRIPT_NAME=/sive
   STATIC_URL=/sive/django-static/
   USE_X_FORWARDED_HOST=True
   BEHIND_TLS_PROXY=True
   DOMAIN_NAME=mte.udenar.edu.co
   ```

   `VITE_API_URL` queda escrita en el JavaScript al construir la imagen del frontend. Si cambia, hay que reconstruir
   esa imagen.

2. Crear el volumen de Redis, que el compose define como externo, y levantar los servicios:

   ```bash
   docker volume create mtesive_app_redis_data_prod
   docker compose -p mtesive_app -f docker-compose.prod.yml up -d --build
   docker compose -p mtesive_app -f docker-compose.prod.yml exec backend python manage.py createsuperuser
   ```

   Al arrancar, el backend aplica las migraciones, carga los metadatos del conector SCADA si la base está vacía,
   reúne los estáticos y arranca gunicorn. Celery y el frontend esperan a que el backend esté sano.

3. Insertar en Apache el bloque de [`deploy/apache-sive.conf`](deploy/apache-sive.conf) dentro del
   `<VirtualHost *:443>` del dominio. Requiere los módulos `proxy`, `proxy_http` y `headers`. Lo aplica el
   administrador del servidor:

   ```bash
   sudo apache2ctl configtest && sudo systemctl reload apache2
   ```

4. Traer el histórico de mediciones del conector con `scripts/backfill_mediciones.sh DESDE HASTA`
   ([`scripts/README.md`](scripts/README.md)).

5. Programar el respaldo diario de la base en el `crontab` del usuario que administra el despliegue:

   ```cron
   30 2 * * 1-6  cd /ruta/al/repo && ./scripts/backup_db.sh          >> logs/backup.log 2>&1
   30 2 * * 0    cd /ruta/al/repo && ./scripts/backup_db.sh --weekly >> logs/backup.log 2>&1
   ```

## Verificación

```bash
curl -sk  https://mte.udenar.edu.co/sive/health/                  # 200 (503 si fallan PostgreSQL o Redis)
curl -sk  https://mte.udenar.edu.co/sive/api/dashboard/summary/   # 200, lectura sin sesión
curl -sk  https://mte.udenar.edu.co/sive/api/                     # 401, la raíz de la API pide sesión
curl -skI https://mte.udenar.edu.co/sive/                         # 200, la página del frontend
./scripts/deploy_production.sh health                             # contenedores y puertos del loopback
```

`/health/?full=1` comprueba además los trabajadores de Celery y el acceso al conector SCADA.

## Actualización

```bash
git pull
./scripts/deploy_production.sh deploy
```

El *script* respalda la base con `backup_db.sh --manual` y el volumen de media, etiqueta las imágenes en uso como
`antes-<marca>` y anota los datos en `backups/ultimo_despliegue.txt`. Si el respaldo falla, no despliega. Luego
construye las imágenes de la aplicación, arranca el backend, que migra al arrancar, espera a que esté sano y arranca
Celery y el frontend. PostgreSQL y Redis no se recrean. Si la comprobación de salud falla, vuelve solo a las imágenes
anteriores.

El *script* necesita que exista una instalación previa, porque etiqueta las imágenes en uso antes de construir las
nuevas. La primera instalación se hace con los pasos de arriba.

## Vuelta atrás

```bash
./scripts/deploy_production.sh rollback              # imágenes anteriores, la base queda como está
./scripts/deploy_production.sh rollback --con-base   # además restaura la base del respaldo previo
```

Restaurar la base descarta todo lo ingerido desde el respaldo, por eso solo se hace a pedido y con el respaldo
verificado con `pg_restore --list`.

## Respaldo y restauración

`scripts/backup_db.sh` vuelca la base en el formato propio de PostgreSQL, descarta el volcado si queda vacío o
ilegible y conserva siete diarios, cuatro semanales y diez manuales. Para restaurar uno a mano se detienen los
servicios que escriben, se restaura y se vuelven a arrancar:

```bash
docker compose -p mtesive_app -f docker-compose.prod.yml stop backend celery_worker celery_beat
docker compose -p mtesive_app -f docker-compose.prod.yml exec -T db \
  pg_restore --clean --if-exists --no-owner -U "$user_postgres" -d "$name_db" \
  < backups/sive_db_AAAAMMDD_HHMMSS.dump
docker compose -p mtesive_app -f docker-compose.prod.yml up -d --no-deps backend celery_worker celery_beat
```

Los volcados incluyen los datos de las cuentas de usuario. Deben guardarse con permisos restringidos y, de ser
posible, con una copia fuera del servidor.

## Operación

```bash
docker compose -p mtesive_app -f docker-compose.prod.yml ps
docker compose -p mtesive_app -f docker-compose.prod.yml logs -f --tail=100 celery_worker
docker compose -p mtesive_app -f docker-compose.prod.yml restart celery_worker celery_beat
docker compose -p mtesive_app -f docker-compose.prod.yml exec backend celery -A core inspect active
```

Nunca `docker compose down -v`, que borra los volúmenes con la base. Para reconstruir solo el frontend tras cambiar
`VITE_API_URL`:

```bash
docker compose -p mtesive_app -f docker-compose.prod.yml build frontend
docker compose -p mtesive_app -f docker-compose.prod.yml up -d --no-deps frontend
```

Docker guarda hasta tres archivos de 10 MB de registro por servicio, que se pierden al recrear el contenedor. Las
alertas de fallos van a un *webhook* o a un correo si se definen `ALERT_WEBHOOK_URL` o `ALERT_EMAIL_TO` y, si no,
quedan en el registro.

En Windows, `scripts/deploy_production.ps1` tiene las mismas órdenes, con `-ConBase` en lugar de `--con-base`.
