# Spec: Correcciones del flujo "Crear una cuenta" (auditoría)

**Fecha:** 2026-07-11
**Origen:** auditoría multiagente del registro (4 lentes: frontend, backend, seguridad, contrato).
**Decisiones del usuario:**
- **Registro abierto** (se mantiene): el auto-registro sigue creando cuenta ACTIVA inmediata. Se arreglan los bugs de UX/errores, NO se cambia a inactiva/aprobación.
- **Endpoints admin-only protegidos en el backend** (`IsAdminUser`), no solo ocultos en el menú.
- **Enumeración NO se "arregla"** (mantener mensajes por-campo tipo "ese correo ya está registrado" es buena UX con registro abierto).

## Alcance de correcciones

### A. Frontend — registro (`frontend/src/components/LoginPage.js`)
1. **[crítico] Mostrar los errores reales del backend.** En `handleRegister`, al recibir `!response.ok`, parsear el 400 de DRF de forma genérica (no `errorData.error`): recolectar `non_field_errors` y errores por-campo (`{campo:[msgs]}`) y mostrar el/los mensaje(s) reales (en español). Eliminar el matcheo por substring en inglés (líneas ~198-206). **Mejor UX:** mapear por campo (`username`/`email`/`password`/`non_field_errors`) y mostrar el error junto a su input; fallback a mensaje global.
2. **[crítico] Alinear política de contraseña del cliente** a `minLength: 12` (`validatePassword` ~82) para igualar `MinimumLengthValidator`. El detalle fino (comunes/similitud) lo aporta el mensaje del servidor ya visible por (1).
3. **[importante] Accesibilidad del modal:** `role="dialog"` + `aria-modal="true"` + `aria-labelledby` al `<h2>`; cerrar con Escape; cerrar al click en backdrop (con `stopPropagation` en la tarjeta); enfocar el primer campo al abrir y devolver el foco al botón "Crear una cuenta" al cerrar. Seguir el patrón ya usado en otros overlays de la app.
4. **[importante] Asociar `<label>`↔`<input>`** con `id`/`htmlFor` en los 5 campos (patrón del login).
5. **[importante] Anti doble-envío + limpieza de timers:** `if (registerLoading) return;` al inicio de `handleRegister`; guardar los `setTimeout` en un ref y limpiarlos en `closeRegisterModal` y en cleanup de desmontaje.
6. **[menor] Toggles de contraseña** del modal con `aria-label`/`aria-pressed` (patrón del login).
7. **[menor] Estado de mensaje independiente** para el modal (`registerMessage`) y cerrar siempre por `closeRegisterModal` (no `setShowRegisterModal(false)` suelto) para no "filtrar" el éxito a la tarjeta de login.
8. **[menor] Error de red en español:** si el fallo no es HTTP (sin `status`), mostrar "No se pudo conectar con el servidor. Revisa tu conexión e inténtalo de nuevo." (patrón de `handleSubmit`).

### B. Backend — registro (`authentication/`)
9. **[crítico] Activar el rate-limit real.** `django-ratelimit` sin `block=True` es inerte. En `UserRegistrationView.post` comprobar `getattr(request, 'limited', False)` al inicio y devolver **429** con mensaje en español. Aplicar el mismo patrón (chequear `request.limited` → 429) a las demás vistas con `ratelimit` inerte (`LoginView`, `RefreshTokenView`, `ProfileImageView`) — mismo bug, gap de seguridad real. `views.py:585,95,345,664`.
10. **[importante] Validar el avatar en el registro.** El `avatar` que entra por `UserProfileSerializer` (registro, AllowAny) no pasa por los límites de `ProfileImageView` (≤5MB, whitelist jpeg/png/webp). Extraer esa validación a un validador común y aplicarla al `ImageField`/serializer del avatar. `serializers.py:340,476`, `models.py:44`.
11. **[menor] `email` UNIQUE en BD** (migración) para cerrar el TOCTOU (dos cuentas con el mismo correo por carrera SELECT+INSERT). Manejar `IntegrityError` de `serializer.save()` devolviendo **409/400** claro en vez de que el `except Exception` genérico lo convierta en 500. `serializers.py:365-366,400`, `views.py:603-615`.
12. **[menor] Validar longitudes mínimas en el servidor** (username≥3, first/last_name≥2) para que la regla no sea solo cosmética del cliente.
13. **[menor] Test anti mass-assignment:** enviar `is_staff=true`/`is_superuser=true` al registro y verificar que el usuario creado los tiene en `False` (blinda `Meta.fields`).

### C. Backend — endurecer endpoints admin-only (decisión del usuario)
14. **[crítico] Proteger en el servidor** los endpoints que el menú trata como admin-only (`externalEnergy`, `exportReports`): cambiar `permission_classes` de `IsAuthenticated` a `IsAdminUser` (o permiso por rol) en las vistas de `external_energy` y en las de generación/exportación de reportes de `indicators`. Identificar el conjunto exacto durante la implementación (mapear rutas ↔ vistas) y verificar que el frontend (que ya oculta esas pestañas a no-admin) sigue coherente. No confiar en `localStorage.isSuperuser`.

## Verificación
- Backend: `python manage.py test` verde (incluye nuevos tests: rate-limit 429 en registro; mass-assignment; validación de avatar; endpoints admin-only devuelven 403 a un usuario no-admin autenticado y 200 a admin).
- Frontend: `npm run build` OK; probar registro con: email duplicado (muestra "…ya está registrado"), contraseña corta (muestra el mensaje real del servidor), contraseñas que no coinciden, y éxito (cuenta creada, modal se cierra, no filtra mensaje al login). Modal accesible (Escape/foco/labels). Doble-Enter no dispara dos POST.
- Migración de `email` UNIQUE aplicada en contenedor.

## Fuera de alcance (documentado)
- Cambiar la política de registro a inactiva/aprobación o verificación por email (el usuario eligió mantenerlo abierto).
- Unificar mensajes de duplicado (se mantienen por-campo por UX, coherente con registro abierto).
- Exponer la política de contraseña desde el backend como fuente única (mejora futura).
