import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Migración CRA -> Vite (Ola 5). Notas:
// - base './': rutas de assets relativas (la app se sirve bajo un subpath, /sive), igual
//   que el antiguo "homepage": "." de CRA.
// - outDir 'build': se conserva el nombre de CRA para no tocar el COPY del Dockerfile.
// - loader JSX en .js: el proyecto tiene JSX en archivos .js; en vez de renombrar 19
//   componentes a .jsx, se le indica a esbuild que trate .js como JSX.
export default defineConfig({
  plugins: [react()],
  base: './',
  build: { outDir: 'build' },
  server: { port: 3000, host: true },
  preview: { port: 3000 },
  esbuild: {
    loader: 'jsx',
    include: /src\/.*\.jsx?$/,
    exclude: [],
    // Elimina el ruido de console.log/info/debug del bundle de PRODUCCIÓN (se
    // tree-shakean por 'pure' al minificar; en dev siguen funcionando). Conserva
    // console.warn/error, que son manejo de errores legítimo.
    pure: ['console.log', 'console.info', 'console.debug'],
  },
  optimizeDeps: {
    esbuildOptions: { loader: { '.js': 'jsx' } },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/setupTests.js',
    css: false,
  },
})
