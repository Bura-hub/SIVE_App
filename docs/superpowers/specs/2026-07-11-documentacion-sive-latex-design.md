# Spec: Documentación LaTeX de SIVE (desarrollo, manual, ficha)

**Fecha:** 2026-07-11
**Objetivo:** reescribir por completo los 3 documentos de SIVE (Documento de Desarrollo, Manual de Usuario, Ficha de Catalogación) en LaTeX, con redacción profesional en **párrafos** (no itemizado), completa, honesta (sin overselling) y fiel al código real, adoptando el **formato de las plantillas SW_AR_LabRE**.

## Decisiones (usuario)
- **Contenido honesto:** eliminar secciones no fundamentables del doc de desarrollo actual (ROI, análisis de costos, métricas de uso/adopción, impacto inflado). Mantener solo lo verificable en el código/arquitectura/sistema.
- **Imágenes:** TODO como placeholders marcados `[ PLACEHOLDER: <qué capturar> ]` (el usuario captura de cero con la app ya rediseñada). No reutilizar las imágenes actuales.
- **Formato:** adoptar preámbulo/clase/portada/estilo de las plantillas SW_AR_LabRE, con identidad SIVE (marca/colores).
- **Corrección:** la app se llama **SIVE**, no "SIVET" (24 apariciones en la ficha) ni "SiVE" (casing en el manual) — corregir todas.

## Insumos (en `recursos_adicionales/`, extraídos a scratch)
- Plantillas de FORMATO: `Documento_de_Desarrollo_SW_AR_LabRE/main.tex` (+ `Bibliografia.bib`), `Manual_de_Usuario_SW_AR_LabRE/main.tex`.
- Contenido ACTUAL de SIVE (minería de ideas, NO de redacción): `Documento_de_desarrollo_SIVE/main.tex` (1916 líneas), `Manual_de_Usuario_SIVE/main.tex` (1027), `Ficha_de_Catalogacion_SIVE/main.tex` (500).
- **Brief de hechos del sistema** (`_sive_facts.md`): fuente de verdad del código real (arquitectura, apps, módulos, despliegue, seguridad, rediseño reciente) para redactar sin inventar.

## Estructura objetivo por documento
- **Desarrollo:** Introducción · Visión del sistema (componentes, flujo de datos, fundamentos energía transactiva/FNCE) · Arquitectura (microservicios: Django+DRF, React+Vite, PostgreSQL, Redis, Celery, Docker; conector SCADA; XM) · Desarrollo backend (apps authentication/indicators/scada_proxy/external_energy; modelos, tareas Celery, API/OpenAPI) · Desarrollo frontend (módulos, KPIs, gráficas, auth, reportes) · Integración y flujo completo · Configuración y despliegue · Pruebas y calidad · Seguridad, riesgos y limitaciones · Glosario · Bibliografía. (Sin ROI/costos/adopción.)
- **Manual:** Introducción · Acceso (login, roles Administrador/Usuario Aliado) · Interfaz (sidebar, menú de usuario flotante, pantalla Inicio) · Módulos (Dashboard, Medidores, Inversores, Estaciones, Datos Externos [admin], Exportar Reportes [admin]) · Arquitectura para el usuario · Resolución de problemas (FAQ real).
- **Ficha:** conservar las 12 secciones del formato con datos precisos; corregir SIVET→SIVE.

## Proceso multi-agente (por documento)
1. **Ideación:** varios agentes leen plantilla + doc actual + brief de hechos y proponen esquema/ideas fundamentadas.
2. **Consenso:** un director consolida qué ideas entran (completo, honesto) → esquema final anotado.
3. **Redacción:** agentes escriben el LaTeX en párrafos (no itemizado), formato plantilla + identidad SIVE, con placeholders de imagen.
4. **Ensamblaje + revisión:** unir en `main.tex`; revisar coherencia, prosa, cero "SIVET", y que compile.

## Salida
- `recursos_adicionales/SIVE_docs_final/{Documento_de_desarrollo,Manual_de_usuario,Ficha_de_catalogacion}/main.tex` (+ `Bibliografia.bib` en desarrollo si aplica). Originales intactos. Probablemente local-only (gitignore, como `AUDITORIA_SIVE/`).

## Verificación
- Cada `main.tex` compila (o al menos es LaTeX válido/estructurado; sin dependencias de imágenes reales gracias a los placeholders).
- 0 apariciones de "SIVET"/"SiVE"; nombre "SIVE" consistente.
- Redacción en párrafos, sin listas como sustituto de explicación; sin secciones de overselling; contenido fiel al brief de hechos.
- Formato/portada/estilo alineado con las plantillas SW_AR_LabRE, con identidad SIVE.

## Orden de ejecución
Piloto con la **Ficha** (más corta, valida formato + honestidad + fix SIVET), luego **Manual**, luego **Desarrollo** (el más extenso). Revisión entre documentos.
