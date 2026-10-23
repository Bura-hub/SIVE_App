# Frontend de SIVE

Interfaz en React 19, compilada con Vite 5, con Tailwind CSS y gráficas de Chart.js (`react-chartjs-2` y
`chartjs-plugin-zoom`). Navega por estado, sin rutas de URL, y carga sus archivos con rutas relativas
(`base: './'` en `vite.config.js`), así que funciona bajo `/sive/` sin cambios. Los componentes tienen JSX en archivos
`.js`, que Vite trata como JSX.

## Órdenes

```bash
npm ci
VITE_API_URL=http://localhost:3504 npm start   # servidor de desarrollo en http://localhost:3000
npm test                                       # Vitest con Testing Library
npm run build                                  # compilación de producción en build/
```

`VITE_API_URL` es la URL base de la API (`src/config.js`). Vite la escribe en el JavaScript al compilar. Vacía, el
frontend llama a la API en su mismo origen. En Windows, `start-frontend.bat` la fija en `http://localhost:3504` y arranca
el servidor de desarrollo.

## Imagen de producción

`Dockerfile` compila con Node 20 y sirve `build/` con nginx en el puerto 3000 del contenedor, publicado en
`127.0.0.1:3503`. `nginx.conf` comprime con gzip, guarda en caché un año los archivos con *hash* en el nombre, envía
`index.html` con `Cache-Control: no-cache` para que cada despliegue se vea sin forzar la recarga y responde en
`/health`. La URL de la API llega como argumento de construcción desde `docker-compose.prod.yml`.

## Estructura de `src/`

| Ruta | Contenido |
|---|---|
| `App.js` | Sesión y pantalla activa, con cada pantalla cargada al abrirla |
| `components/Sidebar.js`, `UserMenu.jsx`, `LoginPage.js` | Menú lateral, menú de usuario e inicio de sesión |
| `components/Home.js`, `Dashboard.js`, `ElectricalDetails.js`, `InverterDetails.js`, `WeatherStationDetails.js`, `SolarIndicators.js`, `ExternalEnergyData.js`, `ExportReports.js` | Una pantalla cada uno |
| `components/KPI/` | `KpiCard` y `ChartCard`, las tarjetas de indicadores y de gráficas |
| `components/filters/` | Filtro de dispositivo y selector de rango de fechas |
| `hooks/` | Carga del detalle de un dispositivo y consultas de tamaño de pantalla |
| `utils/` | Llamadas a la API, fechas, unidades, factor de potencia y la explicación de cada tarjeta (`kpiInfo.js`) |

## Gráficas (`ChartCard`)

`ChartCard` dibuja líneas, barras o la rosa de los vientos (`type` igual a `"line"`, `"bar"` o `"polarArea"`). Sus
otras propiedades son `title`, `description`, `data`, `options`, `height` (256px por defecto), `fullscreenHeight`
(600px) y `maxFullscreenHeight` (80vh). Las opciones propias se combinan con las comunes de escalas y formato.

```jsx
<ChartCard title="Generación diaria" type="bar" data={datos} options={opciones} height="300px" />
```

En escritorio, la rueda del ratón y el arrastre hacen zoom en el eje X y Ctrl más arrastre desplaza la vista. En
pantallas táctiles, el zoom es con el pellizco y el arrastre queda para desplazar la página. El botón de restablecer
se activa al hacer zoom. La vista ampliada ocupa la pantalla y se cierra con Escape.
