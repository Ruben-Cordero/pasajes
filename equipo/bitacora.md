# Bitácora del equipo

El documento del caso (sección 8) pide revisión cruzada, repositorio con commits por autor, bitácora de aprendizaje y defensa oral individual, y el criterio de evaluación 7 revisa que haya evidencia de ello. Este archivo reúne la revisión cruzada y la bitácora; los commits por autor están en Git. **Cada integrante debe llenar su parte con lo que realmente hizo.**

## Roles

| Persona | Rol | Carpeta | Usuario de Git | Nombre |
|---|---|---|---|---|
| 1 | Coordinador/a de modelo (Euler) | `capa1_euler/` | lucianaaaaaaa | Luciana Leaño |
| 2 | Analista bayesiano/a | `capa2_bayes/` | alous12 | Alejandro Machaca |
| 3 | Ingeniero/a de estimación (Kalman) | `capa3_kalman/` | Sarah Cazorla | Sarah Cazorla |
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
- Modelo de Euler:
- Filtro de Kalman:
- Escenarios y decisión:

### Persona 3 (Kalman)
- Modelo de Euler:
- Red bayesiana:
- Escenarios y decisión:

### Persona 4 (decisión y datos)
- Modelo de Euler:
- Red bayesiana:
- Filtro de Kalman:

