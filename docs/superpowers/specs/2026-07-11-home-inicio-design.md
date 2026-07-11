# Spec: Nueva pestaña «Inicio» (presentación) + renombrar «Inicio»→«Dashboard»

**Fecha:** 2026-07-11
**Diseño aprobado:** el **híbrido A+C** (mockup `hybrid.html`): base editorial de A con el hero, las cifras y el bloque institucional del concepto C. Proceso de diseño multi-agente (3 conceptos + crítica + dirección + merge dirigido por el usuario).

## Alcance
1. **Renombrar** la pestaña actual «Inicio» (que va al dashboard) a **«Dashboard»** — mismo destino (`page:'dashboard'`), ícono de dashboard.
2. **Nueva pestaña «Inicio»** arriba del todo → nueva página de **presentación del proyecto** (`page:'home'`).
3. **Aterrizaje por defecto tras login = `'home'`** (decisión del usuario: ver la presentación primero).
4. El **sidebar NO cambia de diseño**: solo se editan las dos entradas de `navItems` (añadir Inicio, renombrar a Dashboard) siguiendo el patrón existente. Nada más de su apariencia se toca.

## Componentes / archivos
- **Crear `frontend/src/components/Home.js`** — port React fiel del `<main>` de `hybrid.html`. Recibe `navigateTo` e `isSuperuser` (de `commonProps`). Una sola responsabilidad: renderizar la presentación.
- **`frontend/src/index.css`** — añadir las reglas de CONTENIDO del híbrido (clases `c-*` y `hc-*`, vars locales). NO se copian los estilos del shell/sidebar del mockup (el app ya tiene el `Sidebar` real).
- **`frontend/src/components/icons/index.jsx`** — añadir `IconDashboard` (gráfico de barras) para la pestaña Dashboard.
- **`frontend/src/components/Sidebar.js`** — `navItems`: nueva entrada `{ name:'Inicio', page:'home', icon:IconHome, azul }` primero; renombrar la existente a `{ name:'Dashboard', page:'dashboard', icon:IconDashboard, azul }`. Sin otros cambios.
- **`frontend/src/App.js`** — `lazy(() => import('./components/Home'))`; `case 'home'` → `<Home {...commonProps} />`; default de aterrizaje `'dashboard'`→`'home'` (estado inicial línea ~36 y `handleLoginSuccess` ~56-57).

## Integración visual (evitar que sea disruptivo)
- El contenido de `Home` se renderiza dentro de `App.js` `<main className="flex-1 p-8 bg-gray-100 rounded-tl-3xl shadow-inner">`. El **hero debe sangrar** (márgenes negativos que anulan el `p-8`) para quedar a todo el ancho como en el mockup, igual que el `<header ... -mx-8 -mt-8>` del Dashboard. El resto del contenido respeta el espaciado.
- Fuente Inter, paleta del app; sin recursos externos; todo SVG/CSS inline.

## Cableado de acciones
- CTA «Ir al Dashboard» → `navigateTo('dashboard')`.
- CTA «Conocer el proyecto» → ancla interna a la sección `#proyecto` (que existe en `Home`).
- Tarjetas de módulo → `navigateTo(page)`: Dashboard→`dashboard`, Medidores→`electricalDetails`, Inversores→`inverterDetails`, Estaciones→`weatherDetails`, Datos Externos→`externalEnergy`, Exportar Reportes→`exportReports`.
- **Seguridad/coherencia:** las tarjetas «Datos Externos» y «Exportar Reportes» solo se muestran si `isSuperuser` (igual que el sidebar las oculta a no-admins; `App.js` no protege esas vistas por rol, así que Home no debe crear un acceso para no-admins).

## Accesibilidad / rendimiento
- Contenido decorativo (SVG del hero) `aria-hidden`; foco visible; `prefers-reduced-motion` respetado si hay animación. Ilustraciones vectoriales inline (cero peticiones). Componente en su propio chunk (lazy).

## Verificación
- `npm run build` sin errores; `case 'home'` operativo; tras login se ve la presentación; pestañas «Inicio» y «Dashboard» ambas funcionan; el hero se ve a todo el ancho; las tarjetas navegan; en no-admin no aparecen las dos tarjetas restringidas.
