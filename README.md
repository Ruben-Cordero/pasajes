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

## Quién hizo cada parte

| Persona | Capa | Archivos |
|---|---|---|
| 1 | Modelo dinámico (Euler): `simular()`, equilibrio, estabilidad, métricas, sensibilidad, matriz F | [modelo_euler.py](modelo_euler.py), [precio_dinamico_transporte.ipynb](precio_dinamico_transporte.ipynb) |
| 2 | Red bayesiana: DAG, tablas de probabilidad, inferencia, pregunta 6, tabla de traducción a D0/S0 | [Bayes/](Bayes/) (tiene su propio [README](Bayes/README.md)) |
| 3 | Filtro de Kalman: mediciones ruidosas, calibración de Q y R, valor de la información, valores atípicos | [filtro_kalman.py](filtro_kalman.py) |
| 4 | Escenarios, datos, calibración, Monte Carlo, decisión, pipeline e informe | todo lo demás (abajo) |

## Estructura

```
pasajes/
├── modelo_euler.py              Persona 1
├── precio_dinamico_transporte.ipynb
├── filtro_kalman.py             Persona 3
├── Bayes/                       Persona 2
├── datos/                       Escenario E (sintético) + clima de SENAMHI
│   ├── README.md                qué es real y qué no
│   ├── generar_sintetico.py, preparar.py
│   ├── crudo/  procesado/  capturas/
├── params.py                    única fuente de parámetros y escenarios A-E
├── comun.py                     utilidades (carpetas, gráficas, import de Bayes/)
├── escenarios.py                escenarios A, B, C y D
├── escenario_e.py               escenario E: frecuencias, identificabilidad, calibración, Kalman
├── montecarlo.py                Monte Carlo Bayes → Euler por contexto
├── decision.py                  regla de decisión y barrido de X e Y (pregunta 7)
├── main.py                      pipeline completo por línea de comandos
├── resultados/
│   ├── figuras/  tablas/
│   └── pregunta7.md             respuesta a la pregunta 7 con sus límites
├── informe/
│   ├── generar_informe.py       arma informe.docx y presentacion.pptx
│   ├── informe.docx
│   └── presentacion.pptx
└── requirements.txt
```

## Cómo reproducir todo

Se necesita Python 3.11 o superior. Los resultados son deterministas (semilla 2026).

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python escenarios.py               # A, B, C, D  -> resultados/
python escenario_e.py              # E (datos sintéticos) y calibración
python montecarlo.py               # bandas de precio por contexto
python decision.py                 # regla y barrido de X e Y
python main.py                     # pipeline: viernes 19:00, lluvia y evento
python main.py --escenario E       # pipeline sobre un día de datos
python informe/generar_informe.py  # informe.docx y presentacion.pptx
```

El orden importa por dos motivos:

- `decision.py` lee las estimaciones de Kalman que guarda `escenario_e.py`.
- El informe lee todas las tablas de `resultados/` y comprueba que cada archivo esté citado.

Para regenerar los datos sintéticos: `cd datos && python generar_sintetico.py && python preparar.py`.

Los scripts de las Personas 1–3 también se pueden correr solos: `python modelo_euler.py`, `python filtro_kalman.py`, `cd Bayes && python consultas.py`.

### Pipeline (`main.py`)

```bash
python main.py --hora punta --clima lluvia --evento si             # red experta (Persona 2)
python main.py --hora valle --clima seco --red calibrada --mediciones precio
python main.py --escenario E --fecha 2026-10-30 --hora-consulta 19:00
python main.py --help
```

Imprime D0, S0 y P(escasez) de la red, el p\* teórico, el precio estimado por Kalman con su intervalo del 95 % y la decisión con su motivo. Guarda una figura en `resultados/figuras/pipeline_*.png`.

## Resultados principales

| | |
|---|---|
| Escenario A | p\* = 7,86 Bs. Arranca en p0 = 10 y **converge oscilando** (Δt·α·(β+γ) = 1,75 < 2, r = −0,75). Llega al equilibrio en 60 min. |
| Escenarios B / C | p\* durante la ventana = 22,14 Bs (D0 = 100) y 13,57 Bs (S0 = 30) |
| Escenario D | Medir también las solicitudes baja el error RMS de la demanda de 3,99 a 2,19 |
| Escenario E | Kalman con D0/S0 del contexto: error de predicción a un paso de 1,47 Bs (solo precio: 2,63), NIS ≈ 2 |
| Consulta del documento | Viernes 19:00 con lluvia y evento: P(escasez) = 0,691 (red experta) y 0,647 (red calibrada) |
| Pregunta 7 | X = 0,30, Y = 13 Bs, permanencia mínima de 30 min. Ver [resultados/pregunta7.md](resultados/pregunta7.md) |

## Notas para el equipo

- **Bayes/traduccion.py:** lo único que se cambió del código de otra persona son las constantes `VALORES_D0` y `VALORES_S0`, calibradas con los datos del Escenario E (commit propio). Ahora son D0 = 47/54/65 y S0 = 43/47/50; antes eran 30/50/100 y 30/50/70. Los escenarios B (D0 = 100) y C (S0 = 30) siguen definidos en `params.py`.
- **`filtro_kalman.py`, al correrlo solo**, escribe `estimaciones_kalman.csv` en la raíz y llama a `plt.show()`. Los scripts de integración lo importan sin ejecutar esa parte.
