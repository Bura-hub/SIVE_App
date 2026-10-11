# Indicadores del sistema fotovoltaico del HUDN — calculados por SIVE

**Para:** visita de acreditación ICONTEC del 13-oct-2026 · **Calculado:** 2026-10-10, con el código de la rama
`correccion-indicadores-2026-10` sobre una copia de la base de producción de SIVE tomada **después** del backfill
(mediciones completas, iguales a las del conector MTE).

**Pantalla en SIVE:** menú «Indicadores Solares» (institución HUDN, desde el 2025-04-04, agrupado por mes, día o año).
Allí está cada cifra con su periodo y los supuestos de cálculo, lista para capturas una vez desplegada la rama.

**Archivos de esta carpeta:**
- `hudn_mensual_2025-04_2026-10.csv`: tabla mensual completa.
- `hudn_diario_2025-04-04_2026-10-10.csv`: generación, kWh/kWp, demanda M1, cobertura, PR y disponibilidad por día.

## 1. Verificación de SIVE (antes de usar sus cifras)

| Contraste | SIVE | Referencia | Diferencia |
|---|---|---|---|
| Generación del inversor, 2025-04-04 a 2025-12-16 | 12 913,9 kWh | Tesis: 12 930,2 kWh | −0,13 % |
| Factor de capacidad, mismo periodo | 0,119 | Tesis: 0,120 | — |
| Pico del inversor | 15 144 W | Tesis: 15 144 W | 0 |
| Disponibilidad del inversor (horas de sol con dato) | 98,3 % | Tesis: 98,3 % | 0 |
| Demanda media M1 | 9,08 kW | Tesis: 9,09 kW | — |
| M1 en importación todas las horas | mínimo +5,3 kW, 0 horas negativas | Tesis: mínimo +6,12 kW, 0 horas negativas | Igual conclusión |
| Generación may–nov 2025 | 10 696,2 kWh | Solar.web: 10 699,5 kWh | −0,03 % |
| Generación 2026, meses con datos completos (feb–ago y 1–10 oct) | 8 697,0 kWh | Solar.web: 8 982,9 kWh | −3,2 % |

Diferencias mensuales grandes frente a Solar.web, todas explicadas por **huecos de datos del SCADA**, que tampoco están
en la base del conector:
- dic-2025: −39 %, disponibilidad 59 %.
- ene-2026: −94 %, sin datos desde el 29-ene.
- sep-2026: −25 %, sin datos del 4 al 17-sep.

Durante la verificación se encontraron y corrigieron en SIVE 16 defectos de ingesta y de cálculo. El más grave: SIVE
había perdido hasta el 55 % de las lecturas del HUDN de jul–sep 2026, que llegaron tarde al conector. Ya se
recuperaron y SIVE las reconcilia cada noche. Detalle con el antes y el después:
`docs/superpowers/specs/2026-10-10-correccion-ingesta-e-indicadores-design.md`.

## 2. Cifras clave

**Supuestos:**
- 17,55 kWp (30 módulos Jinko de 585 Wp).
- Diseño: 59,4 kWh/día.
- Ahorro = energía autoconsumida × CU mensual de ASC Ingeniería, nivel 2, sin contribución. Media de 723,6 COP/kWh.
  Desde may-2026 se usa el CU de abr-2026, último publicado en la tabla de la tesis, marcado como extrapolado.
- CO₂ evitado: 0,112 kgCO₂/kWh (UPME, Res. 0705/2024); 545 árboles por 12 t.

| Indicador | 2025-04-04 a 2025-12-31 | 2026-01-01 a 2026-10-10 | Total 2025-04-04 a 2026-10-10 |
|---|---|---|---|
| Energía generada | 13 131,7 kWh | 9 654,1 kWh | **22 785,8 kWh** |
| Rendimiento específico | 748,2 kWh/kWp | 550,1 kWh/kWp | 1 298,3 kWh/kWp |
| Factor de capacidad | 11,5 % | 8,1 % | 9,8 % |
| Producción frente al diseño | — | — | 69,1 % |
| Demanda del circuito M1 | 56 025,7 kWh (media 9,08 kW, pico horario 12,24 kW) | 55 827,0 kWh (media 9,31 kW, pico 12,71 kW) | 111 852,8 kWh |
| Cobertura solar del circuito M1 | 23,4 % | 17,3 % | 20,3 % |
| Autoconsumo | 100 % (exportación 0) | 100 % | 100 % |
| Ahorro estimado | 9,49 MCOP | 7,01 MCOP | **16,50 MCOP** |
| CO₂ evitado | 1,47 t (≈ 67 árboles) | 1,08 t (≈ 49 árboles) | **2,55 t (≈ 116 árboles)** |
| Disponibilidad de datos (horas de sol) | 94,9 % | 88,5 % | 91,7 % |

Las cifras de Solar.web cubren desde el 2024-06-02 (31 064 kWh; 19 316 kWh en 2025). SIVE solo tiene datos desde el
2025-04-04, así que los totales no son comparables directamente: compárense meses iguales (sección 1).

**Eficiencia del inversor (P_AC / P_DC): no se puede calcular con los datos del MTE.** El inversor solo reporta la
potencia DC de una entrada MPPT: `dcPower` es en promedio 0,55 × `acPower`, así que el cociente no mide la
eficiencia. Para el hospital debe tomarse la eficiencia de la ficha técnica del inversor o la de Solar.web.

**Performance Ratio.** Se calcula con la estación meteorológica del HUDN, que mide en plano **horizontal**, no en el
plano de los módulos.
- 2025: 0,57–0,77 por mes; 0,69 para el periodo 2025-04-04 a 2025-12-16, con 101 días válidos.
- La estación del HUDN **no tiene datos desde marzo de 2026**, tiene huecos y lee bajo frente a las estaciones vecinas.
  Su PR de 2026 (0,81–0,85 en feb–mar) no es fiable. Para el diagnóstico de 2026 se usa la estación de Alvernia
  (sección 3).

## 3. Diagnóstico de la caída de 2026

En Solar.web, ene–sep 2026 queda **un 25,3 % por debajo** de ene–sep 2025. Con SIVE:

| Mes | HUDN kWh | Mariana kWh (planta idéntica) | Razón HUDN / Mariana | PR HUDN (H Alvernia) | PR Mariana (H Alvernia) |
|---|---|---|---|---|---|
| may-2025 | 1 523,6 | 1 465,0 | 1,04 | 0,96 | 0,92 |
| jul-2025 | 1 615,2 | 1 490,7 | 1,08 | 0,88 | 0,82 |
| sep-2025 | 1 506,0 | 1 571,5 | 0,96 | 0,78 | 0,82 |
| nov-2025 | 1 408,0 | 1 445,9 | 0,97 | 0,76 | 0,78 |
| feb-2026 | 1 117,5 | 1 392,9 | 0,80 | 0,61 | 0,75 |
| abr-2026 | 1 321,0 | 1 523,8 | 0,87 | 0,67 | 0,77 |
| may-2026 | 1 185,3 | 1 588,0 | 0,75 | 0,58 | 0,77 |
| jun-2026 | 1 086,9 | 1 462,9 | 0,74 | 0,56 | 0,76 |
| jul-2026 | 959,8 | 1 193,7 | 0,80 | 0,57 | 0,70 |
| ago-2026 | 1 076,4 | 1 357,0 | 0,79 | 0,58 | 0,73 |
| 1–10 oct-2026 | 365,4 | 514,6 | 0,71 | 0,51 | 0,72 |

(PR con la irradiación horizontal de la estación de Alvernia, a unos 2 km; sirve para comparar las dos plantas, no
como PR absoluto.)

**Conclusión: la pérdida es del sistema del HUDN, no del clima.**
- En 2025 el HUDN producía lo mismo que Mariana: razón 0,95–1,14.
- Desde feb-2026 produce **entre un 13 y un 29 % menos**, con la misma irradiación.
- Mariana mantiene su PR (0,70–0,77) y el HUDN baja de ~0,76–0,88 a ~0,51–0,67.
- En abr–jun de 2026, la irradiación de Alvernia fue incluso mayor que en 2025.

**Pico de mediodía** (percentil 99 de la potencia AC entre 11:00 y 12:59):
- En 2025 el inversor del HUDN llegaba al techo de 15,13 kW todos los meses.
- Desde feb-2026 se queda en 12,7–14,4 kW.
- Mariana sigue llegando al techo, salvo en jul-2026.

**Corriente del MPPT medido** (corrección del 2026-10-10: una versión anterior de este informe la presentaba como
prueba de una pérdida uniforme del arreglo, y no lo es):
- Baja de unos 6,0 A en 2025 a 4,0–5,0 A en may–oct de 2026.
- La de Mariana también varía con el clima: 4,05 A en jul-2026.
- Frente a Mariana, la caída se ve en may–jun y sep–oct, pero no en jul–ago.
- El inversor solo reporta una de sus entradas MPPT (DC ≈ 0,55 × AC). Un *string* caído en la entrada que no se mide no
  aparecería en esta corriente.
- **Con estos datos no se puede distinguir entre suciedad o sombra del arreglo y una falla de *string*.**

**Recomendación:** inspección en sitio: limpieza de los módulos, revisión de sombras nuevas y medición de la corriente
de cada *string* en las dos entradas MPPT.

## 4. Fuentes

- Mediciones: conector SCADA MTE (los mismos datos del Control Panel), sincronizados y reconciliados en SIVE.
- Tesis de B. S. López-Méndez (SistemaBL): cifras de referencia 2025-04-04 a 2025-12-16, tarifas ASC (CAL-47) y
  capacidad instalada (H-67).
- Fronius Solar.web, inversor del HUDN (cifras mensuales entregadas por el proyecto).
- Fotos de la instalación o capturas de SIVE con datos del HUDN: se buscaron en el servidor (repositorios del proyecto,
  `recursos_adicionales/SIVE_images` de SIVE y la biblioteca de medios de WordPress) y no hay ninguna.
