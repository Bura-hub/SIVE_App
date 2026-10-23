@echo off
rem Servidor de desarrollo del frontend (Vite). VITE_API_URL es la URL base del backend.
echo Configurando variables de entorno para SIVE...
set VITE_API_URL=http://localhost:3504
echo VITE_API_URL=%VITE_API_URL%
echo.
echo Iniciando servidor de desarrollo...
npm run dev
