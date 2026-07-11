# Spec: Menú de usuario flotante (esquina superior derecha)

**Fecha:** 2026-07-11
**Diseño aprobado:** Concepto C (vidrio) refinado por el director — mockup `final-widget-C.html`. Proceso multi-agente (3 conceptos + crítica + refinamiento dirigido).

## Objetivo
Sacar la **tarjeta de usuario** del fondo del sidebar y convertirla en un **widget flotante fijo en la esquina superior derecha** de la app, con diseño profesional (vidrio esmerilado elevado sobre el header de color). Mínimo reflow, sin romper el resto del sidebar.

## Arquitectura
- **Crear `frontend/src/components/UserMenu.jsx`** — componente autónomo que:
  - Renderiza el **chip colapsado** (avatar con punto de presencia verde + nombre + rol como etiqueta + chevron) y el **dropdown** (cabecera con avatar/nombre/rol; acciones: Configuración, Ayuda y Soporte, Cerrar Sesión).
  - Diseño fiel a `final-widget-C.html` (vidrio, elevación, acento solar disciplinado, modo oscuro, accesibilidad, `prefers-reduced-motion`).
  - **Iconos** del set real (`components/icons/index.jsx`); el de Configuración debe verse bien (engranaje Lucide correcto).
  - Contiene su propia lógica: `showProfileMenu` + click-fuera + teclado (Esc/flechas/Home/End), `profileImageUrl` (loadProfileImage), modales `ProfileSettings` y `HelpSupport`, y `handleLogoutClick` (con `TransitionOverlay`). Todo esto se **mueve desde `Sidebar.js`**.
  - Props: `{ username, isSuperuser, onLogout }`.
  - **Datos veraces:** muestra nombre y rol (Administrador/Usuario Aliado). NO inventa correo: solo muestra email si ya está disponible en el estado del usuario; si no, se omite esa línea. Pie institucional "SIVE · Universidad de Nariño".
- **`App.js`**: montar `<UserMenu username={username} isSuperuser={isSuperuser} onLogout={handleLogoutWithAnimation} />` UNA vez, en el layout autenticado (NO en login), posición `fixed` arriba-derecha con `z-index` alto (por encima de los headers). El widget flota; no entra en el flujo del `<main>`.
- **`Sidebar.js`**: **eliminar** el bloque de perfil (markup del `.profile` y su dropdown ~líneas 280-409), los modales (~441-455), el `TransitionOverlay` (~434-438) y toda la lógica exclusiva del perfil (estado `showProfileMenu`/`profileMenuRef`/`showProfileSettings`/`showHelpSupport`/`profileImageUrl` y estados de transición; efectos click-fuera y loadProfileImage; handlers `openProfileSettings`/`openHelpSupport`/`handleProfileImageUpdate`/`loadProfileImage`/`handleLogoutClick`/`showTransitionAnimation`; imports ya no usados). **Conservar intacto** el resto: header con logo + botón colapsar, la navegación (`navItems`, que sigue usando `isSuperuser` para el gating de admin) y el pie "About del sistema". El diseño visible del sidebar no cambia salvo que ya no aparece la tarjeta de perfil al fondo.

## Coexistencia con los headers de pantalla (no disruptivo)
Cada pantalla de contenido (Dashboard, Medidores, Inversores, Estaciones, Datos Externos, Exportar Reportes) tiene un header de color con contenido a la derecha (estado XM/SCADA). El widget flota arriba-derecha por encima. Para que **no tape** ese contenido, reservar espacio a la derecha en el header de cada pantalla: añadir un `padding-right` responsive al contenedor superior del header (amplio en escritorio ~ ancho del chip; reducido en móvil, donde el chip colapsa a solo avatar). Cambio mínimo (una clase por header), sin alterar su diseño.

## Accesibilidad / rendimiento
- Disparador `<button>` con `aria-haspopup`/`aria-expanded`/`aria-controls`; `role=menu`/`menuitem`; foco visible y retorno de foco; cierre por Esc y click-fuera; navegación por teclado. `prefers-reduced-motion` sin animación de apertura. Modo oscuro del widget. Cero recursos externos.

## Verificación
- `npm run build` sin errores. El sidebar sigue funcionando (nav, colapsar, footer) SIN la tarjeta de perfil. El widget aparece arriba-derecha en todas las pantallas de contenido (no en login), abre/cierra con teclado y ratón, y sus tres acciones funcionan (Configuración y Ayuda abren sus modales; Cerrar Sesión ejecuta el logout con su animación). El estado XM de cada header no queda tapado. El icono de Configuración se ve correcto.
