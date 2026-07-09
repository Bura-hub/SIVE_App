# Despliegue de SIVE bajo `https://mte.udenar.edu.co/sive/`

Guía para publicar SIVE como **subruta `/sive/`** del dominio existente
`mte.udenar.edu.co`, **reutilizando** su certificado Let's Encrypt y su Apache,
sin abrir puertos nuevos en el firewall.

## Arquitectura

```
Navegador ──HTTPS──> Apache (host, :443, cert Let's Encrypt de mte.udenar.edu.co)
                        │
   /sive/api,/auth,... ├─(quita /sive)──> 127.0.0.1:3504  backend  (gunicorn, contenedor)
   /sive/django-static ├─────────────────> 127.0.0.1:3504  (whitenoise)
   /sive/ (resto)      └─────────────────> 127.0.0.1:3503  frontend (nginx, contenedor)
```

- El **frontend** no usa router de URL (navegación por estado) y se construye con
  `homepage: "."` → sus assets cargan de forma relativa bajo `/sive/`.
- El **backend** corre bajo el prefijo con `FORCE_SCRIPT_NAME=/sive`, de modo que
  admin, DRF, Swagger, login y redirecciones generan URLs con `/sive`.
- La API se sirve en el **mismo origen** (`https://mte.udenar.edu.co/sive`) que el
  frontend → sin CORS ni contenido mixto.

## 1. Variables de entorno (`.env`)

```env
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1,mte.udenar.edu.co
CORS_ALLOWED_ORIGINS=https://mte.udenar.edu.co
CSRF_TRUSTED_ORIGINS=https://mte.udenar.edu.co
REACT_APP_API_URL=https://mte.udenar.edu.co/sive

FORCE_SCRIPT_NAME=/sive
STATIC_URL=/sive/django-static/
USE_X_FORWARDED_HOST=True
BEHIND_TLS_PROXY=True
SECURE_HSTS_SECONDS=0        # el dominio es compartido; HSTS lo gestiona Apache
```

## 2. Reconstruir y levantar los contenedores

`REACT_APP_API_URL` se incrusta en el bundle en build-time, así que hay que
**reconstruir el frontend** tras cambiarlo:

```bash
docker compose -f docker-compose.prod.yml build backend frontend
docker compose -f docker-compose.prod.yml up -d
```

Los contenedores siguen escuchando en `127.0.0.1:3503` (frontend) y `:3504`
(backend); **no** se exponen a Internet directamente, solo Apache los alcanza.

## 3. Apache (lo aplica el administrador del servidor)

Requiere módulos `proxy`, `proxy_http` y `headers`:

```bash
sudo a2enmod proxy proxy_http headers
```

Insertar el contenido de [`deploy/apache-sive.conf`](deploy/apache-sive.conf)
**dentro** del `<VirtualHost *:443>` existente de `mte.udenar.edu.co` (el que ya
tiene el `SSLCertificateFile` de Let's Encrypt). Luego:

```bash
sudo apache2ctl configtest && sudo systemctl reload apache2
```

## 4. Verificación

```bash
curl -sk https://mte.udenar.edu.co/sive/health/            # -> 200
curl -sk https://mte.udenar.edu.co/sive/api/                # -> 401 (requiere auth)
curl -skI https://mte.udenar.edu.co/sive/                   # -> 200 (index del frontend)
```

Abrir `https://mte.udenar.edu.co/sive/` en el navegador e iniciar sesión.
El panel de administración queda en `https://mte.udenar.edu.co/sive/admin/`.

## Notas / puntos a validar en el host

- **Estáticos de admin/DRF bajo subpath**: se sirven con **WhiteNoise**.
  `STATIC_URL=/sive/django-static/` hace que el HTML del admin pida
  `/sive/django-static/...`; Apache **quita** el prefijo `/sive` y WhiteNoise
  (que con `FORCE_SCRIPT_NAME` recorta el script name de su prefijo) sirve en
  `/django-static/`. Verificado en Docker: el path recortado devuelve 200.
- **HSTS**: no lo emite la app (`SECURE_HSTS_SECONDS=0`) porque el dominio es
  compartido; si se desea, configurarlo en Apache a nivel de dominio.
- La ruta crítica (frontend + API JSON) **no** depende de estáticos de Django.
