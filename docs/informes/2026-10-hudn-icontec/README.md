# Indicadores del sistema fotovoltaico del HUDN — calculados por SIVE

**Para:** visita de acreditación ICONTEC del 13-oct-2026 · **Cifras regeneradas:** 2026-10-11, con el 10-oct completo, desde la
API de producción de SIVE (`https://mte.udenar.edu.co/sive/api/solar-indicators/`), con todas las mediciones
sincronizadas, iguales a las del conector MTE.

**Pantalla en SIVE** (pública, sin iniciar sesión): `https://mte.udenar.edu.co/sive/`, menú lateral «Indicadores
Solares». Por defecto muestra el HUDN, desde el 2025-04-04 y agrupado por mes; también se puede agrupar por día o por
año. Cada cifra lleva su periodo y los supuestos de cálculo.

**Archivos de esta carpeta:**
- `hudn_mensual_2025-04_2026-10.csv`: tabla mensual, incluidas las columnas del diagnóstico. La columna
  `irradiacion_hudn_kwh_m2_dia` es la media de los días de la estación del HUDN válidos para el PR (contrastados con
  Alvernia): queda vacía en los meses sin días válidos.
- `hudn_diario_2025-04-04_2026-10-10.csv`: generación, kWh/kWp, demanda M1, cobertura, PR, disponibilidad y cobertura
  de lecturas, por día.

**Cómo se calcula la generación de cada hora:** Σ potencia × 2 min. Si la hora tiene al menos 15 de sus 30 lecturas,
las que faltan se reponen con la media de las presentes, como en la tesis. Con menos lecturas (amanecer, caídas) no se
repone nada. La **cobertura de lecturas** de cada mes dice cuánto falta.

## 1. Verificación de SIVE

| Contraste | SIVE | Referencia | Diferencia |
|---|---|---|---|
| Generación, 2025-04-04 a 2025-12-16 | 12 944,2 kWh | Tesis: 12 930,2 kWh | +0,11 % |
| Factor de capacidad, mismo periodo | 0,120 | Tesis: 0,120 | 0 |
| Pico del inversor | 15 144 W | Tesis: 15 144 W | 0 |
| Disponibilidad del inversor (horas de sol con dato) | 98,3 % | Tesis: 98,3 % | 0 |
| Demanda media M1 | 9,08 kW | Tesis: 9,09 kW | — |
| M1 en importación todas las horas | mínimo +5,3 kW, 0 horas negativas | Tesis: mínimo +6,12 kW, 0 negativas | Igual conclusión |
| Generación may–nov 2025 | 10 711,9 kWh | Solar.web: 10 699,5 kWh | +0,12 % |
| Generación 2026, meses completos (feb–ago y 1–10 oct) | 8 855,9 kWh | Solar.web: 8 982,9 kWh | −1,4 % |

Diferencias mensuales grandes frente a Solar.web, todas explicadas por **datos que no llegaron**, que tampoco están en el
conector:

| Mes | Diferencia | Disponibilidad (horas de sol) | Cobertura de lecturas | Causa |
|---|---|---|---|---|
| abr-2025 | −11,1 % | 97,2 % | 96,6 % | SIVE empieza el 4-abr |
| dic-2025 | −38,4 % | 59,1 % | 57,4 % | Sin datos del SCADA del 23-dic al 27-ene (y huecos el 8–9 y el 13–15-dic) |
| ene-2026 | −93,7 % | 6,5 % | 6,4 % | Mismo corte; solo hay datos el 28 y el 29-ene (otro corte del 30-ene al 1-feb) |
| jul-2026 | −3,7 % | 97,8 % | 92,2 % | La RPi del HUDN perdía lecturas sueltas |
| sep-2026 | −16,2 % | 98,1 % | 75,6 % | Lo mismo, hasta su arreglo del 26-sep |

En sep-2026 llegó lectura casi todas las horas, pero solo el 75,6 % de las lecturas de cada hora. En muchas horas
llegaron menos de 15 de 30, y esas no se reponen.

Durante la verificación se encontraron y corrigieron en SIVE 20 defectos de ingesta y de cálculo. El detalle, con el
antes y el después, está en `docs/superpowers/specs/2026-10-10-correccion-ingesta-e-indicadores-design.md`. El más
grave: SIVE había perdido hasta el 55 % de las lecturas del HUDN de jul–sep 2026, que llegaron tarde al conector. Ya se
recuperaron y SIVE las reconcilia cada noche.

## 2. Cifras clave

**Supuestos:**
- 17,55 kWp (30 módulos Jinko de 585 Wp).
- Diseño: 59,4 kWh/día.
- Ahorro = energía autoconsumida × CU mensual de ASC Ingeniería, nivel 2, sin contribución. Desde may-2026 se usa el CU
  de abr-2026, último publicado en la tabla de la tesis, marcado como extrapolado.
- CO₂ evitado: 0,112 kgCO₂/kWh (UPME, Res. 0705/2024); 545 árboles por 12 t.

| Indicador | 2025-04-04 a 2025-12-31 | 2026-01-01 a 2026-10-10 | Total 2025-04-04 a 2026-10-10 |
|---|---|---|---|
| Energía generada | 13 164,0 kWh | 9 915,0 kWh | **23 079,0 kWh** |
| Rendimiento específico | 750,1 kWh/kWp | 565,0 kWh/kWp | 1 315,0 kWh/kWp |
| Factor de capacidad | 11,5 % | 8,3 % | 9,9 % |
| Producción frente al diseño | — | — | 70,0 % |
| Demanda del circuito M1 | 56 025,7 kWh (media 9,08 kW, pico horario 12,24 kW) | 55 846,1 kWh (media 9,31 kW, pico 12,71 kW) | 111 871,8 kWh |
| Cobertura solar del circuito M1 | 23,5 % | 17,7 % | 20,6 % |
| Autoconsumo | 100 % (exportación 0) | 100 % | 100 % |
| Ahorro estimado | 9,51 MCOP | 7,20 MCOP | **16,71 MCOP** |
| CO₂ evitado | 1,47 t (≈ 67 árboles) | 1,11 t (≈ 50 árboles) | **2,58 t (≈ 117 árboles)** |
| Disponibilidad de datos (horas de sol) | 94,9 % | 88,5 % | 91,7 % |

Los totales de 2025 y 2026 subestiman la energía real en los meses con datos perdidos (dic-2025, ene-2026 y sep-2026;
ver sección 1). Para totales de energía, Solar.web es la fuente completa. SIVE solo tiene datos desde el 2025-04-04.

**Eficiencia del inversor (P_AC / P_DC): no se puede calcular con los datos del MTE.** El inversor solo reporta la
potencia DC de una de sus entradas MPPT (`dcPower` ≈ 0,55 × `acPower`).

**Performance Ratio: 0,75**, con 27 días válidos de ago y nov 2025.
- Se calcula con la estación meteorológica del HUDN, que mide en plano **horizontal**, no en el plano de los módulos.
- Cada día se contrasta con la estación de referencia de Alvernia, a ±25 % por día.
- Además, se descartan los meses en que la estación del HUDN tiene un sesgo sistemático mayor del 10 % (mediana de la
  razón diaria, con al menos 5 días para contrastar).
- La estación del HUDN marcaba 1,26–1,68 veces Alvernia en abr–jun 2025, 1,16 en jul, 1,13 en sep y 0,79–0,84 en
  feb–mar 2026, y no tiene datos desde marzo de 2026. **No hay PR fiable de 2026** con ella.
- Para comparar plantas en 2026, ver la sección 3.

## 3. Diagnóstico de la caída de 2026

En Solar.web, ene–sep 2026 queda **un 25,3 % por debajo** de ene–sep 2025. Con SIVE, frente a Mariana, una planta de la
misma capacidad (tesis, H-67):

| Mes | HUDN kWh | Mariana kWh | Razón HUDN / Mariana | Irradiación Alvernia (kWh/m², mes) | PR HUDN (Alvernia) | PR Mariana (Alvernia) | p99 AC mediodía HUDN (W) |
|---|---|---|---|---|---|---|---|
| may-2025 | 1 525,1 | 1 466,1 | 1,04 | 90,6 | 0,96 | 0,92 | 15 130 |
| jul-2025 | 1 617,8 | 1 491,8 | 1,08 | 104,0 | 0,89 | 0,82 | 15 126 |
| sep-2025 | 1 506,7 | 1 572,1 | 0,96 | 109,7 | 0,78 | 0,82 | 15 128 |
| nov-2025 | 1 412,5 | 1 446,9 | 0,98 | 106,0 | 0,76 | 0,78 | 15 109 |
| feb-2026 | 1 120,4 | 1 394,6 | 0,80 | 105,4 | 0,61 | 0,75 | 13 870 |
| abr-2026 | 1 322,3 | 1 568,7 | 0,84 | 113,1 | 0,67 | 0,79 | 14 045 |
| may-2026 | 1 197,8 | 1 596,8 | 0,75 | 117,1 | 0,58 | 0,78 | 13 458 |
| jun-2026 | 1 121,2 | 1 468,5 | 0,76 | 110,5 | 0,58 | 0,76 | 12 970 |
| ago-2026 | 1 121,0 | 1 359,2 | 0,83 | 105,4 | 0,61 | 0,74 | 13 712 |
| 1–10 oct-2026 | 366,2 | 514,9 | 0,71 | 40,8 | 0,51 | 0,72 | 12 739 |

Notas sobre la tabla:
- La irradiación mensual de Alvernia es la media de los días válidos multiplicada por los días del mes.
- El PR con Alvernia usa irradiancia horizontal de otra sede: sirve para comparar las dos plantas, no como PR absoluto.
  Por eso sale ≈ 1 en abr–jun 2025.
- Jul y sep de 2026 no se comparan porque la RPi del HUDN perdió lecturas: razón 0,85 y 0,65, con 92 % y 76 % de
  cobertura de lecturas.

**Conclusión: la pérdida es del sistema del HUDN, no del clima.**
- En 2025 el HUDN producía lo mismo que Mariana: razón 0,95–1,14.
- Desde feb-2026 produce **entre un 8 y un 29 % menos**, con la misma irradiación. Lo más bajo es may–jun y oct (0,71–0,76).
- Mariana mantiene su PR (0,70–0,79) y el del HUDN baja a 0,51–0,67.

**Pico de mediodía** (percentil 99 de la potencia AC entre 11:00 y 12:59):
- En 2025 el inversor del HUDN llegaba al techo de 15,13 kW todos los meses.
- Desde feb-2026 se queda en 12,7–14,4 kW.
- Mariana sigue llegando al techo, salvo en jul-2026.

**Corriente del MPPT medido:**
- Baja de unos 6,0 A en 2025 a 4,0–5,0 A en may–oct de 2026.
- La de Mariana también varía con el clima: 4,05 A en jul-2026.
- Frente a Mariana, la caída se ve en may–jun y sep–oct, pero no en jul–ago.
- El inversor solo reporta una de sus entradas MPPT. Un *string* caído en la entrada que no se mide no aparecería en
  esta corriente.
- **Con estos datos no se puede distinguir entre suciedad o sombra del arreglo y una falla de *string*.**

**Recomendación:** inspección en sitio: limpieza de los módulos, revisión de sombras nuevas y medición de la corriente
de cada *string* en las dos entradas MPPT.

## 4. Fuentes

- Mediciones: conector SCADA MTE (los mismos datos del Control Panel), sincronizados y reconciliados en SIVE.
- Tesis de B. S. López-Méndez (SistemaBL): cifras de referencia 2025-04-04 a 2025-12-16, tarifas ASC (CAL-47),
  capacidad instalada (H-67) y medidores (H-7).
- Fronius Solar.web, inversor del HUDN (cifras mensuales entregadas por el proyecto).
- Fotos de la instalación o capturas de SIVE con datos del HUDN: se buscaron en el servidor (repositorios del proyecto,
  `recursos_adicionales/SIVE_images` de SIVE y la biblioteca de medios de WordPress) y no hay ninguna.
