# Bitácora del equipo

El documento del caso (sección 8) pide revisión cruzada, rotación al exponer, repositorio con commits por autor, bitácora de aprendizaje y defensa oral individual, y el criterio de evaluación 7 revisa que haya evidencia de ello. Este archivo reúne esa evidencia; los commits por autor están en Git. **Cada integrante debe llenar su parte con lo que realmente hizo.**

## Roles

| Persona | Rol | Carpeta | Usuario de Git | Nombre |
|---|---|---|---|---|
| 1 | Coordinador/a de modelo (Euler) | `capa1_euler/` | lucianaaaaaaa | _completar_ |
| 2 | Analista bayesiano/a | `capa2_bayes/` | alous12 | _completar_ |
| 3 | Ingeniero/a de estimación (Kalman) | `capa3_kalman/` | Sarah Cazorla | _completar_ |
| 4 | Analista de decisiones y datos | `integracion/`, `datos/`, `informe/` | Rubén Cordero | Rubén Cordero |

## 1. Revisión cruzada

Ningún entregable está terminado hasta que otro integrante lo ejecutó y lo revisó.

| Entregable | Autor | Revisado y ejecutado por | Fecha | Observaciones |
|---|---|---|---|---|
| `capa1_euler/modelo_euler.py` y cuaderno | P1 | | | |
| `capa2_bayes/` (red, consultas, traducción) | P2 | | | |
| `capa3_kalman/filtro_kalman.py` | P3 | | | |
| `capa3_kalman/extensiones.py` y `no_lineal.py` | | | | |
| `integracion/` (escenarios A–E, Monte Carlo, decisión) | P4 | | | |
| `informe/informe.docx` | P4 | | | |


## 2. Bitácora de aprendizaje

Cada integrante anota, en pocas líneas, qué aprendió de las **otras tres** capas. Sirve para preparar la defensa oral individual (regla 5): cualquiera debe poder explicar cualquier sección.

### Persona 1 (Euler)
- Red bayesiana:
- Filtro de Kalman:
- Escenarios y decisión:

### Persona 2 (Bayes)
- Modelo de Euler:
- Filtro de Kalman:
- Escenarios y decisión:

### Persona 3 (Kalman)
- Modelo de Euler:
- Red bayesiana:
- Escenarios y decisión:

### Persona 4 (decisión y datos)
- Modelo de Euler: el precio sube cuando falta oferta y baja cuando sobra, con la ecuación p_{k+1} = p_k + Δt·α·(D_k − S_k). Igualando demanda y oferta sale el precio de equilibrio p* = (D0 − S0 + β·p_ref + γ·p_costo)/(β + γ), que da 7,86 Bs en el Escenario A. Aprendí a leer la estabilidad con r = 1 − Δt·α·(β + γ): con los valores del documento r = −0,75, así que el sistema es estable pero oscila. Por eso el Escenario A converge oscilando desde p0 = 10 y no "permanece estable". Esa oscilación también explicó un problema de mi regla de decisión: cambiar de acción a cada rato generaba transitorios, y por eso agregué una permanencia mínima de 30 min. También vi que con datos observados una regresión simple no recupera α, β y γ (pregunta 2, identificabilidad), así que usé los valores nominales.
- Red bayesiana: entendí cómo se calcula P(escasez | contexto) multiplicando las tablas y normalizando, y cómo `traduccion.py` convierte las categorías baja/media/alta en los D0 y S0 que necesita Euler. Al calibrarla con los datos aprendí dos cosas. Primero, la escasez D > S casi no depende del contexto porque el precio equilibra el mercado, así que usé `tarifa_alta` como indicador. Segundo, hay que discretizar la demanda a precio de referencia y no las solicitudes crudas. Además, con solo tres niveles la red se satura en contextos extremos, como el viernes 19:00 con lluvia y evento (P(escasez) = 0,69).
- Filtro de Kalman: el filtro combina lo que predice el modelo con lo que se mide, según cuánto confía en cada uno (Q y R). Con datos reales no hay valor verdadero, así que el filtro se evalúa con el error de predicción a un paso y con las innovaciones (NIS ≈ número de mediciones). En el Escenario E el filtro solo funcionó bien cuando le pasé el D0 y S0 del contexto que da la red: el error bajó de 4,7 a 1,5 Bs. Medir las solicitudes además del precio mejora la estimación, que es el valor de la información (pregunta 5). Para la decisión uso el límite inferior del intervalo de credibilidad, para estar seguro de que el precio ya es alto antes de incentivar.


