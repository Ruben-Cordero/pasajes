# Bitácora del equipo

El documento del caso (sección 8) pide revisión cruzada, repositorio con commits por autor, bitácora de aprendizaje y defensa oral individual, y el criterio de evaluación 7 revisa que haya evidencia de ello. Este archivo reúne la revisión cruzada y la bitácora; los commits por autor están en Git. **Cada integrante debe llenar su parte con lo que realmente hizo.**

## Roles

| Persona | Rol | Carpeta | Usuario de Git | Nombre |
|---|---|---|---|---|
| 1 | Coordinador/a de modelo (Euler) | `capa1_euler/` | lucianaaaaaaa | Luciana Leaño |
| 2 | Analista bayesiano/a | `capa2_bayes/` | alous12 | Alejandro Machaca |
| 3 | Ingeniero/a de estimación (Kalman) | `capa3_kalman/` | SarahJhosset | Sarah Cazorla |
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
- Red bayesiana: Aprendí que la red representa el contexto mediante
  probabilidades de demanda, oferta y escasez. La función de traducción
  convierte esas inferencias en los valores `D0` y `S0` que usa Euler; por
  eso la capa bayesiana no calcula directamente el precio.
- Filtro de Kalman: Aprendí que el filtro recibe la dinámica de Euler en forma
  de espacio de estados, con `x_k = (p_k, D_k)` y la matriz `F`. Euler genera
  la trayectoria verdadera y el filtro estima el precio y la demanda cuando
  las mediciones tienen ruido.
- Escenarios y decisión: Aprendí que los escenarios A--C modifican `D0` o
  `S0` por intervalos y permiten comparar el equilibrio teórico con la
  simulación. La capa de decisión usa la probabilidad de escasez de Bayes y
  el precio estimado por Kalman para elegir entre mantener, subir o
  incentivar.

### Persona 2 (Bayes)
- Modelo de Euler: aprendí que esta capa se encarga de calcular el precio según la oferta y la demanda: si la demanda supera a la oferta el precio sube, y si sobra oferta el precio baja, paso a paso con p_{k+1} = p_k + Δt·α·(D_k − S_k). Es un modelo determinista, así que no toma en cuenta el ruido de las mediciones ni las perturbaciones del mercado; eso queda para el filtro de Kalman. También entendí que Euler necesita los valores D0 y S0 que salen de mi red bayesiana a través de `traduccion.py`, y que con ellos llega a un precio de equilibrio (7,86 Bs en el Escenario A).
- Filtro de Kalman: aprendí que el filtro nos ayuda a reducir el error que deja el ruido. Toma la predicción del modelo de Euler y la corrige con lo que se mide, dándole más peso a la que sea más confiable según Q (ruido del proceso) y R (ruido de la medición). Así obtiene una estimación del precio y la demanda más cercana a la real que la medición sola, junto con su incertidumbre. También vi que el filtro funciona mejor cuando recibe el D0 y S0 del contexto que da mi red: sin ese dato se equivoca más cuando cambia el contexto.
- Escenarios y decisión: aprendí que los escenarios sirven para probar el sistema en distintas situaciones (cambios de demanda, de oferta o de contexto) y comparar el equilibrio teórico con la simulación. La decisión junta las tres capas: usa la probabilidad de escasez que calcula la red bayesiana y el precio estimado por Kalman. Si P(escasez) no supera X = 0,30 se mantiene el precio; si la supera y el precio aún no pasa Y = 13 Bs, se sube; y si ya lo pasa, se incentiva a los conductores. Entendí que cada capa resuelve una parte distinta: Bayes da el contexto, Euler la dinámica del precio y Kalman limpia el ruido para decidir con más seguridad.

### Persona 3 (Kalman)
- Modelo de Euler: el filtro de Kalman parte de la ecuación de Euler escrita en espacio de estados, con x_k = (p_k, D_k). De ahí salen la matriz F = [[0,25, 0,5], [−0,5, −1,0]] y el término constante B·u, que depende de D0 y S0. Aprendí que F tiene valores propios 0 y −0,75, y que −0,75 es el mismo r = 1 − Δt·α·(β+γ) de la condición de estabilidad. Por eso el precio converge oscilando en el Escenario A (p* = 7,86 Bs) y el filtro hereda esa oscilación. También aprendí que el modelo es lineal solo mientras no se activen las restricciones (precio ≥ costo, demanda ≥ 0). Cuando se activan, el filtro deja de ser exacto, y de ahí sale la pregunta 4 (EKF/UKF). En la sensibilidad vi que subir α, β o γ un 25 % acerca o llevar al límite de inestabilidad (r = −1), así que esos parámetros deben estimarse con cuidado.
- Red bayesiana: entendí que la red no entrega un precio sino categorías (demanda alta, oferta baja) y una P(escasez), calculada multiplicando las tablas de probabilidad y normalizando. Con `traduccion.py` esas categorías se convierten en D0 y S0, que son justo la entrada B·u de mi filtro. Sin ese puente el filtro asume D0 = S0 = 50 y se equivoca cuando cambia el contexto: en el Escenario E, al pasarle el D0 y S0 del contexto, el error de predicción bajó de ≈4,7 a ≈1,5 Bs. De la pregunta 6 aprendí que la diferencia de medias ingenua mezcla factores que ocurren juntos (efecto de la lluvia +22,6) y que una regresión múltiple los separa (+10,0). También aprendí que la escasez D > S casi no depende del contexto porque el precio equilibra el mercado, y por eso se usó `tarifa_alta` como proxy.
- Escenarios y decisión: mi filtro entrega el precio estimado y su desviación, y la regla de decisión usa el límite inferior (estimación − 2 desviaciones) para afirmar con ≈97,5 % de confianza que el precio ya supera Y = 13 Bs. Por eso importa que Q y R estén bien calibrados: si la cobertura de los intervalos queda muy por debajo del 95 %, ese límite inferior no vale lo que dice y se podría pagar bonos de más. La regla es: si P(escasez) > X = 0,30 y el límite inferior > Y, se incentiva; si no supera Y, se sube el precio; si P(escasez) ≤ X, se mantiene. También aprendí por qué se agregó una permanencia mínima de 30 min (la dinámica oscila y cambiar de acción a cada rato genera transitorios). Y vi que el bono es caro (≈65 Bs por pasajero retenido) y que todo el Escenario E es sintético, así que valida el sistema pero no predice el mercado real.

### Persona 4 (decisión y datos)
- Modelo de Euler: el precio sube cuando falta oferta y baja cuando sobra, con la ecuación p_{k+1} = p_k + Δt·α·(D_k − S_k). Igualando demanda y oferta sale el precio de equilibrio p* = (D0 − S0 + β·p_ref + γ·p_costo)/(β + γ), que da 7,86 Bs en el Escenario A. Aprendí a leer la estabilidad con r = 1 − Δt·α·(β + γ): con los valores del documento r = −0,75, así que el sistema es estable pero oscila. Por eso el Escenario A converge oscilando desde p0 = 10 y no "permanece estable". Esa oscilación también explicó un problema de mi regla de decisión: cambiar de acción a cada rato generaba transitorios, y por eso agregué una permanencia mínima de 30 min. También vi que con datos observados una regresión simple no recupera α, β y γ (pregunta 2, identificabilidad), así que usé los valores nominales.
- Red bayesiana: entendí cómo se calcula P(escasez | contexto) multiplicando las tablas y normalizando, y cómo `traduccion.py` convierte las categorías baja/media/alta en los D0 y S0 que necesita Euler. Al calibrarla con los datos aprendí dos cosas. Primero, la escasez D > S casi no depende del contexto porque el precio equilibra el mercado, así que usé `tarifa_alta` como indicador. Segundo, hay que discretizar la demanda a precio de referencia y no las solicitudes crudas. Además, con solo tres niveles la red se satura en contextos extremos, como el viernes 19:00 con lluvia y evento (P(escasez) = 0,69).
- Filtro de Kalman: el filtro combina lo que predice el modelo con lo que se mide, según cuánto confía en cada uno (Q y R). Con datos reales no hay valor verdadero, así que el filtro se evalúa con el error de predicción a un paso y con las innovaciones (NIS ≈ número de mediciones). En el Escenario E el filtro solo funcionó bien cuando le pasé el D0 y S0 del contexto que da la red: el error bajó de 4,7 a 1,5 Bs. Medir las solicitudes además del precio mejora la estimación, que es el valor de la información (pregunta 5). Para la decisión uso el límite inferior del intervalo de credibilidad, para estar seguro de que el precio ya es alto antes de incentivar.

