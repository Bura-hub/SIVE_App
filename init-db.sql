-- Script de inicialización de la base de datos
-- El contenedor de PostgreSQL lo ejecuta automáticamente en el primer arranque
-- (docker-entrypoint-initdb.d) ya conectado a la base de datos de la aplicación
-- creada vía POSTGRES_DB (${name_db}). NO se debe hardcodear el nombre aquí:
-- así las extensiones quedan en la BD correcta que usa Django.

-- Crear extensiones necesarias en la base de datos actual (la de la app)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Configurar encoding
SET client_encoding = 'UTF8';

-- Mensaje de confirmación
SELECT 'Base de datos MTE SIVE inicializada correctamente' as status;
