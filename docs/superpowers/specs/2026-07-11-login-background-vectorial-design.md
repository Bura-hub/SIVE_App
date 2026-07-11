# Spec: Fondo vectorial del login SIVE (solar / noche)

**Fecha:** 2026-07-11
**Alcance:** reemplazar el fondo de la pantalla de login por una ilustración **100% vectorial (SVG + CSS)**, temática solar/fotovoltaica, azul noche con acento solar, sutilmente animada. **La tarjeta de login NO cambia** (solo el fondo). Aprobado visualmente por el usuario vía mockup.

## Motivación

El fondo actual (`bg.webp`, ~7.4 KB) sigue siendo una petición HTTP + decode. Un fondo vectorial inline en el bundle elimina esa petición, escala sin pérdida, y permite una composición temática (energía solar) coherente con MTE/SIVE. Cierra el hilo de la ola de rendimiento (QW1) con una solución más limpia.

## Diseño aprobado

Tres capas detrás del card, más el color de respaldo `#0f172a`:

1. **Base (CSS):** degradado noche (`#0d1730 → #0f172a → #0a1122`) + glow solar cálido radial arriba-derecha + leve halo cian.
2. **SVG vectorial:**
   - **Sol** (arriba-derecha): halo cálido que *respira* (`breathe`, 10s), núcleo con degradado dorado, y ráfaga de **rayos en dos anillos** que *rota* lento (`spin`, 90s).
   - **Arreglo fotovoltaico** (abajo, en perspectiva con `skewX`): 3 paneles (cercano/medio/lejano) rellenos con un **patrón SVG de celdas** (rect redondeado + busbars), con un *brillo* tenue intermitente (`twinkle`) donde incide el sol; un `rect` con degradado funde el borde superior con el fondo.
   - **Líneas de energía:** 3 curvas Bézier que *fluyen* (`stroke-dashoffset`, 6/8/10s) desde los paneles hacia el sol, con degradado cian→dorado.
3. **Viñeta (CSS):** radial oscura en los bordes para legibilidad del card.

Paleta: `--night:#0f172a` · `--night-deep:#0a1122` · celdas `#1b2c50` con líneas `rgba(125,180,255,.x)` · `--solar:#f5b942` · `--solar-hot:#ffdf9e` · `--flow:#38bdf8`.

## Integración (arquitectura)

- **Componente nuevo `frontend/src/components/LoginBackground.js`**: renderiza las tres capas (base, SVG inline, viñeta) como una capa absoluta `aria-hidden`, sin props. Una unidad con una sola responsabilidad, testeable/observable de forma aislada.
- **CSS** de las capas y `@keyframes` (`spin`, `breathe`, `flow`, `twinkle`) se añaden a `frontend/src/index.css` bajo el namespace `login-bg-*` (mismo patrón que `login-card-enhanced`, `animate-float`).
- **`LoginPage.js`**: quitar `import background from './bg.webp'` y el `style={{ backgroundImage }}`, quitar el bloque de 6 partículas flotantes; renderizar `<LoginBackground />` como primer hijo del contenedor. Mantener `backgroundColor:'#0f172a'` de respaldo. La tarjeta y el formulario quedan idénticos.
- **Borrar `frontend/src/components/bg.webp`** (queda sin referencias).

## Rendimiento y accesibilidad

- Cero peticiones HTTP nuevas; SVG inline (~2–3 KB gzip en el bundle, menor que el WebP).
- Animaciones solo `transform`/`opacity`/`stroke-dashoffset` (compositor GPU); sin `setInterval` ni JS por frame.
- `@media (prefers-reduced-motion: reduce)` desactiva todas las animaciones (el sol queda con opacidad fija).
- El fondo es decorativo → `aria-hidden="true"`; no interfiere con el foco ni el formulario.

## Verificación

- `npm run build` compila sin errores; el bundle ya no referencia `bg.webp` y el archivo no existe.
- Visual en navegador: el login muestra el fondo solar/noche; la tarjeta se ve **idéntica** a la actual; animaciones fluidas.
- `prefers-reduced-motion` (DevTools > Rendering → Emulate) detiene las animaciones.
- Sin errores de consola.

## Fuera de alcance (posible seguimiento)

- Ajustes a la **tarjeta** de login (el usuario los dejó como propuesta futura, no ahora).
- Variantes de tema claro (el login es un mundo visual oscuro deliberado; se mantiene single-theme).
