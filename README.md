# Precio dinámico de transporte

Un sistema que modela cómo cambia el precio de un viaje en una plataforma de transporte según la oferta y la demanda. Con eso decide, cada 5 minutos, si conviene **mantener** el precio, **subirlo** o **incentivar** a los conductores (pregunta 7 del caso).

Se combinan tres capas:

1. **Modelo dinámico (Euler):** cómo evoluciona el precio cuando hay exceso de demanda.
2. **Red bayesiana:** cómo el contexto (hora, clima, eventos, tráfico y costos) cambia la demanda, la oferta y la probabilidad de escasez.
3. **Filtro de Kalman:** estima el precio y la demanda reales a partir de mediciones con ruido.

```
contexto ──► red bayesiana ──► modelo de Euler ──► filtro de Kalman ──► decisión
             P(escasez), D0, S0   precio, demanda     precio ± 2 desv.     MANTENER / SUBIR / INCENTIVAR
```

> **Los datos del Escenario E son sintéticos.** Se generaron con el propio modelo porque no hay series públicas de precios de plataformas en Cochabamba. Sirven para validar que el sistema funciona, no para predecir el mercado real. Ver [datos/README.md](datos/README.md).

## Estructura

Cada capa del caso vive en su propia carpeta, en el mismo orden que el documento.

```
pasajes/
├── README.md
├── requirements.txt
├── reproducir.py                 regenera TODO (resultados, informe y presentación)
├── main.py                       pipeline completo por línea de comandos
│
├── capa1_euler/                  Capa 1 · Persona 1
│   ├── modelo_euler.py           simular(), equilibrio, estabilidad, métricas, matriz F
│   └── precio_dinamico_transporte.ipynb   análisis paso a paso y sensibilidad
│
├── capa2_bayes/                  Capa 2 · Persona 2 (tiene su propio README)
│   ├── red.py                    DAG y tablas de probabilidad
│   ├── consultas.py              inferencia exacta, pregunta 6, Monte Carlo, pgmpy
│   ├── traduccion.py             contexto → D0, S0 para Euler
│   ├── dibujar.py
│   └── figuras/
│
├── capa3_kalman/                 Capa 3 · Persona 3
│   ├── filtro_kalman.py          filtro escrito a mano, Q/R, valor de la información
│   ├── extensiones.py            predicción x(k+m|k) y filtro robusto a atípicos
│   └── no_lineal.py              umbral de tolerancia al precio, EKF y UKF (pregunta 4)
│
├── integracion/                  Integración · Persona 4
│   ├── params.py                 única fuente de parámetros y escenarios A–E
│   ├── comun.py                  carpetas, gráficas e import de las capas
│   ├── escenarios.py             escenarios A–D y preguntas 1, 3, 4 y 5
│   ├── escenario_e.py            escenario E, calibración y pregunta 6
│   ├── montecarlo.py             Monte Carlo Bayes → Euler
│   └── decision.py               regla de decisión y barrido de X e Y (pregunta 7)
│
├── datos/                        Escenario E (sintético) + clima de SENAMHI
├── resultados/                   figuras/, tablas/ y pregunta7.md (todo generado)
├── informe/                      generar_informe.py → informe.docx y presentacion.pptx
└── equipo/
    └── bitacora.md               roles, revisión cruzada y bitácora de aprendizaje
```

## Cómo reproducir todo

Se necesita Python 3.11 o superior. Los resultados son deterministas (semilla 2026). Todos los comandos se corren **desde la carpeta raíz** `pasajes/`.

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/Mac: source .venv/bin/activate)
pip install -r requirements.txt

python reproducir.py            # corre todos los pasos en orden (~40 s)
```

Paso a paso (el orden importa: `decision` lee las estimaciones de `escenario_e`, y el informe lee todas las tablas):

```bash
python -m integracion.escenarios     # A, B, C, D + preguntas 1, 3, 4, 5
python -m integracion.escenario_e    # E (datos sintéticos), calibración, pregunta 6
python -m integracion.montecarlo     # bandas de precio por contexto
python -m integracion.decision       # regla y barrido de X e Y (pregunta 7)
python main.py                       # pipeline: viernes 19:00, lluvia y evento
python main.py --escenario E         # pipeline sobre un día de datos
python informe/generar_informe.py    # informe.docx y presentacion.pptx
```

Cada capa también se puede correr sola:

```bash
python -m capa1_euler.modelo_euler
python -m capa2_bayes.consultas       # o: cd capa2_bayes && python consultas.py
python -m capa3_kalman.filtro_kalman  # guarda su demo en capa3_kalman/salidas/
python -m capa3_kalman.no_lineal
```

El cuaderno `capa1_euler/precio_dinamico_transporte.ipynb` se abre desde su carpeta (importa `modelo_euler` directamente).

Para regenerar los datos sintéticos: `cd datos && python generar_sintetico.py && python preparar.py`.

### Pipeline (`main.py`)

```bash
python main.py --hora punta --clima lluvia --evento si             # red experta (Persona 2)
python main.py --hora valle --clima seco --red calibrada --mediciones precio
python main.py --escenario E --fecha 2026-10-30 --hora-consulta 19:00
python main.py --help
```

Imprime D0, S0 y P(escasez) de la red, el p\* teórico, el precio estimado por Kalman con su intervalo del 95 % y la decisión con su motivo. Guarda una figura en `resultados/figuras/pipeline_*.png`.

## Qué parte del caso responde cada archivo

| Lo que pide el documento | Dónde está | Sección del informe |
|---|---|---|
| Escenarios A, B, C | `integracion/escenarios.py` | 3.1, 3.2 |
| Escenario D (Kalman, Q/R, atípicos) | `integracion/escenarios.py`, `capa3_kalman/` | 3.3, 7.3, 7.8 |
| Escenario E (datos) | `integracion/escenario_e.py`, `datos/` | 3.4, 4 |
| Pregunta 1: sensibilidad | `integracion/escenarios.py`, cuaderno de la capa 1 | 7.1 |
| Pregunta 2: identificabilidad | `integracion/escenario_e.py` | 3.4.2, 7.2 |
| Pregunta 3: calibración de Q y R | `integracion/escenarios.py`, `integracion/escenario_e.py` | 3.4.4, 7.3 |
| Pregunta 4: no linealidad, EKF/UKF | `capa3_kalman/no_lineal.py` | 7.4 |
| Pregunta 5: valor de la información | `integracion/escenarios.py` | 3.3, 7.5 |
| Pregunta 6: lluvia vs hora punta | `capa2_bayes/consultas.py`, `integracion/escenario_e.py` | 7.6 |
| Pregunta 7: subir o incentivar | `integracion/decision.py`, `resultados/pregunta7.md` | 6, 7.7 |
| Predicciones x(k+m\|k) | `capa3_kalman/extensiones.py` | 7.8 |
| Trabajo en equipo (RACI, bitácora) | `equipo/bitacora.md` | 8 |

## Resultados principales

| | |
|---|---|
| Escenario A | p\* = 7,86 Bs. Arranca en p0 = 10 y **converge oscilando** (Δt·α·(β+γ) = 1,75 < 2, r = −0,75). Llega al equilibrio en 60 min. |
| Escenarios B / C | p\* durante la ventana = 22,14 Bs (D0 = 100) y 13,57 Bs (S0 = 30) |
| Pregunta 1 | α nominal a 14 % del límite de inestabilidad (α < 0,114); con α/2 llega al equilibrio en 10 min sin oscilar |
| Pregunta 3 | Solo Q×1, R×1 da a la vez el menor error y ~95 % de cobertura; Q muy chico → lento, R muy chico → copia el ruido |
| Pregunta 4 | Con umbral de tolerancia (18 Bs) el α nominal es inestable (precio salta 5 ↔ 35 Bs). Con α = 0,03, midiendo solo el precio: KF lineal 1,48 Bs de error, EKF 0,38, UKF 0,36 |
| Pregunta 5 / Escenario D | Medir también las solicitudes baja el error RMS de la demanda de 3,99 a 2,19 |
| Pregunta 6 | Efecto de la lluvia en los datos: diferencia ingenua +22,6, regresión completa +10,0 (valor real del generador: +10) |
| Atípicos (D) | 3 lecturas atípicas duplican el error del precio (0,44 → 0,97 Bs); el filtro robusto lo deja en 0,50 |
| Escenario E | Kalman con D0/S0 del contexto: error de predicción a un paso de 1,47 Bs (solo precio: 2,63), NIS ≈ 2 |
| Consulta del documento | Viernes 19:00 con lluvia y evento: P(escasez) = 0,691 (red experta) y 0,647 (red calibrada) |
| Pregunta 7 | X = 0,30, Y = 13 Bs, permanencia mínima de 30 min. Ver [resultados/pregunta7.md](resultados/pregunta7.md) |

## Notas para el equipo

- **Pendiente antes de entregar:** completar los nombres de las Personas 1–3 en la portada (`informe/generar_informe.py`, función `construir`) y llenar [equipo/bitacora.md](equipo/bitacora.md).
- **capa2_bayes/traduccion.py:** lo único que se cambió de la lógica de otra persona son las constantes `VALORES_D0` y `VALORES_S0`, calibradas con los datos del Escenario E. Ahora son D0 = 47/54/65 y S0 = 43/47/50; antes eran 30/50/100 y 30/50/70. Los escenarios B (D0 = 100) y C (S0 = 30) siguen definidos en `integracion/params.py`.
- **Reorganización por carpetas:** al mover los archivos solo se cambiaron las rutas de los `import`; `git log --follow <archivo>` conserva la autoría de cada uno.
