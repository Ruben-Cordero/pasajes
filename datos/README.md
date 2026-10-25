# Datos del Escenario E (Cochabamba)

> **Aviso de transparencia.** `cotizaciones_indrive.csv` y `escenario_e.csv` contienen datos
> **sintéticos**: se generaron con el modelo de Euler del proyecto y *no* son mediciones de inDrive
> ni de ninguna plataforma. Cada fila lo declara en la columna `fuente`. Sirven para que el pipeline
> Bayes → Euler → Kalman → decisión funcione de punta a punta mientras el equipo recolecta datos
> reales. Deben presentarse en el informe como lo que son (ver sección 8).

## 1. Qué es real y qué no

| Archivo / dato | Estado | Origen |
|---|---|---|
| `crudo/lluvia_senamhi.csv`, filas con `fuente = senamhi` (enero 2026 y diciembre 2023) | **Real** | Transcritas de dos PDF de SENAMHI. Las filas `grafico_aprox` fueron leídas a ojo de un gráfico |
| `crudo/lluvia_senamhi.csv`, filas con `origen_valor = supuesto` (sep y oct 2026) | **Supuesto** | Inventadas, sin documento. Reemplazar por el resumen climático mensual de SENAMHI |
| `crudo/cotizaciones_indrive.csv` | **Sintético** | `generar_sintetico.py` (semilla 2026) |
| `procesado/escenario_e.csv` | **Derivado de sintético** | `preparar.py` |
| Pasaje urbano de 2,50 Bs y estudio de costos de 2,49 Bs (usados como orden de magnitud para `p_ref` y `p_costo`) | Real, pero de transporte público regulado, no de apps | Ley Municipal 1575/2024 (Los Tiempos, 2024-2025) |

## 2. Estructura

```
datos/
├── README.md
├── generar_sintetico.py     # crea cotizaciones sintéticas y agrega filas supuestas de clima
├── preparar.py              # une todo y escribe procesado/escenario_e.csv
├── crudo/
│   ├── lluvia_senamhi.csv
│   └── cotizaciones_indrive.csv
├── procesado/
│   └── escenario_e.csv
└── capturas/                # para las capturas reales cuando se recolecten
```

Para regenerar todo: `python generar_sintetico.py` y luego `python preparar.py`. La semilla es fija, así que
el resultado es reproducible.

## 3. Columnas

### `crudo/cotizaciones_indrive.csv` (1351 filas)

| Columna | Tipo | Descripción |
|---|---|---|
| `timestamp` | `YYYY-MM-DD HH:MM` | Cada 5 min, de 06:00 a 22:00, del lunes 26-oct-2026 al domingo 1-nov-2026 |
| `precio_bs` | float | Precio mostrado, en pasos de 0.5 Bs |
| `solicitudes` | int | Solicitudes por intervalo de 5 min en la zona (escala relativa) |
| `vehiculos` | int | Vehículos disponibles observados |
| `lluvia` | `seco` / `lluvia` | |
| `trafico` | `bajo` / `alto` | |
| `evento` | 0 / 1 | Evento masivo en el centro |
| `ruta` | texto | `ucb_plaza_14_septiembre` (una sola ruta fija) |
| `fuente` | texto | `sintetico` en todas las filas |

### `procesado/escenario_e.csv` (1351 filas)

Mismas variables, ya numéricas, más derivadas: `t_min` (minutos desde las 06:00 de cada día), `dia_semana` (0 = lunes),
`escasez`, `tarifa_alta`, `lluvia` (0/1), `trafico_alto` (0/1), `evento`, `hora_punta` (0/1), `ruta`, `fuente`.

- `escasez` = 1 si `solicitudes − vehiculos ≥ 5` (definición D > S del documento del caso).
- `tarifa_alta` = 1 si `precio_bs ≥ 13` (1.3 × `p_ref`). Es observable en la app y se agregó por la razón de la sección 6.

### `crudo/lluvia_senamhi.csv` (27 filas)

Estructura original sin cambios (`origen_valor` ∈ `tabla`, `texto_grafico`, `grafico_aprox`, `supuesto`): 22 filas reales más 5 filas supuestas:
septiembre y octubre de 2026, estación `cochabamba_aeropuerto`.

## 4. Cómo se generaron las cotizaciones y por qué

### 4.1 Mecanismo

Para cada día se simula el modelo del documento a Δt = 5 min, con los parámetros del Escenario A:

```
D_k = D0 + β (p_ref − p_k) + ε_k          β = 2.0,  ε_k ~ N(0, 1²)
S_k = S0 + γ (p_k − p_costo)              γ = 1.5
p_{k+1} = max(p_costo, p_k + Δt α (D_k − S_k))     α = 0.1,  p_ref = 10,  p_costo = 5,  p_0 = 10
```

Lo que aparece en el CSV es lo que "vería" un observador: el estado verdadero más ruido de medición
(precio ± 0.4 Bs y redondeo a 0.5; solicitudes ± 2.5; vehículos ± 2).
Con estos parámetros Δt·α·(β+γ) = 1.75 < 2: el sistema es estable pero oscila, como indica el documento.

### 4.2 El contexto determina D0 y S0

| Factor | Efecto en D0 | Efecto en S0 |
|---|---|---|
| Base (valle, seco) | 50 | 48 |
| Hora punta | +12 | — |
| Lluvia | +10 | −6 |
| Evento masivo | +10 | — |
| Tráfico alto | +3 | −4 |
| Sábado / domingo | −2 / −6 | — |

Los cambios de contexto se suavizan con una media móvil de 15 a 30 min para que la demanda y la oferta
cambien gradualmente, como ocurre en la práctica.

**Calendario simulado**
- Hora punta entre semana: 07:00–09:00, 12:30–14:00 y 17:30–20:00. En fin de semana: 18:00–21:00.
- Lluvia: martes 27-oct 17:00–19:30 y viernes 30-oct 18:15–20:15 (2 de 7 días ≈ 0.29, igual que el P(día lluvioso) supuesto de octubre).
- Evento: viernes 30-oct 18:00–21:30. Coincide con lluvia a propósito: es la consulta del documento
  ("viernes a las 19:00, con lluvia y un evento masivo").
- Tráfico: se decide por bloques de 30 min, con probabilidad 0.15 en valle, 0.75 en punta, y mayor con lluvia o evento.

### 4.3 Justificación de los supuestos

Ningún valor de la tabla anterior proviene de datos medidos. Son supuestos elegidos con estos criterios:
1. **Que el precio de equilibrio por contexto sea plausible.** El valle da ≈ 8.4 Bs y el peor caso (punta + lluvia + evento + tráfico) ≈ 21 Bs,
   cerca del equilibrio del Escenario B del documento (22.14 Bs). Los signos de los efectos (lluvia sube la demanda y baja la oferta) son
   consistentes con lo que describe la literatura de tarifa dinámica y con el mecanismo que Uber documenta públicamente.
2. **Anclaje en magnitudes reales de Cochabamba.** El pasaje de 2,50 Bs y el estudio de costos de 2,49 Bs ayudan a situar `p_costo` y `p_ref` en un orden de magnitud creíble, pero no son tarifas de apps.
3. **Ruido pequeño frente a la señal.** Así el filtro de Kalman tiene algo claro que estimar. Para estudiar robustez se pueden inyectar valores atípicos aparte.

## 5. Verificación realizada

Comprobaciones sobre `escenario_e.csv`:
- Sin valores nulos, pasos de tiempo uniformes de 5 min, 7 días, precio entre 5.0 y 22.0 Bs (5 lecturas en el piso de `p_costo`).
- Precio medio observado por contexto frente al equilibrio teórico de Euler:

| Contexto | Precio medio observado | p* teórico aprox. |
|---|---|---|
| Valle, seco | 8.4 Bs | 8.4 |
| Punta, seco | 12.9 Bs | 13.4 |
| Punta + lluvia | 17.9 Bs | 18.3 |
| Punta + lluvia + evento | 20.9 Bs | 21.2 |

- Terciles útiles para `discretizar()`: solicitudes 52 / 56, vehículos 52 / 56, precio 8.5 / 11.0 Bs.
- Viernes 30-oct 19:00–19:55 (lluvia + evento): precio medio 21.2 Bs y `tarifa_alta` = 1 en el 100 % de las lecturas.

## 6. Limitaciones y hallazgos que conviene decir en el informe

1. **`escasez` (D > S) casi no depende del contexto** (≈ 16 % en todos los contextos). No es un error: en el modelo, el precio se ajusta hasta
   igualar demanda y oferta, así que la escasez solo aparece en los transitorios. Por eso se añadió `tarifa_alta`, que sí varía:
   P(tarifa alta) es 0.01 en valle y 0.63 en punta, y 0.19 sin lluvia frente a 0.95 con lluvia. Para calibrar el nodo Escasez de la red bayesiana conviene usar `tarifa_alta`
   (o la presión de escasez a precio de referencia) y explicarlo en el informe.
2. **Los parámetros no se recuperan con una regresión ingenua.** Una regresión simple de estos datos da pendientes atenuadas
   (≈ 0.23 en lugar de Δt·α = 0.5; ≈ +0.58, con el signo contrario, en lugar de −β = −2; ≈ 0.84 en lugar de γ = 1.5; ver `resultados/tablas/E_identificabilidad.csv`) por el ruido de medición y la simultaneidad precio–demanda.
   Es justamente la pregunta de identificabilidad (pregunta 2 del documento). **Usar los valores nominales del documento**; no estimarlos de este CSV.
3. **No hay estado verdadero en el CSV**, igual que con datos reales. El error de estimación del filtro debe medirse en el Escenario D (con `simular()`);
   en el E se puede medir el error de predicción a un paso y la consistencia de las innovaciones.
4. **Una sola semana, una sola ruta, sin eventos aleatorios más allá de los programados.** No hay estacionalidad mensual ni dependencia de feriados.
5. **Las fechas (26-oct a 1-nov de 2026) son la semana prevista de recolección**, no fechas de mediciones ya hechas.
6. **Las filas de clima de sep/oct 2026 son supuestas.** P(día lluvioso): enero 0.68 (real, aproximado de un gráfico), octubre 0.29 y septiembre 0.13 (supuestos).

## 7. Cómo usarlos en cada capa

- **Euler (Persona 1).** `p_ref = 10`, `p_costo = 5`, Δt = 5 min. Para validar, se pueden comparar los precios medios por contexto con los equilibrios de la sección 5.
- **Red bayesiana (Persona 2).**
  - Priors de lluvia: tabla de `lluvia_senamhi.csv` filtrada por `dias_con_lluvia`.
  - Cortes de `discretizar()`: terciles de la sección 5.
  - Tabla de traducción: ya calibrada en `capa2_bayes/traduccion.py` con estos datos (D0 = 47 / 54 / 65 y S0 = 43 / 47 / 50; detalle en `resultados/tablas/E_calibracion_traduccion.csv`). Los valores orientativos iniciales eran D0 ≈ 50 / 62 / 75 y S0 ≈ 48 / 44 / 38.
  - Frecuencias condicionales: ejecutar `preparar.py` e imprimir las tablas de P(tarifa_alta) y P(escasez) por contexto.
- **Kalman (Persona 3).** Medir con `precio_bs` y `solicitudes`. Valores de ruido con los que se generaron los datos (sirven de referencia para calibrar Q y R):
  R ≈ diag(0.18, 6.25) (error de precio incluye el redondeo) y Q ≈ diag(0.25, 1.0).
- **Decisión (Persona 4).** Comparar el precio estimado con 13 Bs (`tarifa_alta`) y la probabilidad de escasez que entregue la red.

## 8. Texto sugerido para el informe

> El Escenario E se construyó con datos sintéticos generados con el modelo de Euler del propio caso
> (parámetros del Escenario A y efectos de contexto supuestos), porque no se encontraron series públicas
> de precios y solicitudes de plataformas de transporte en Cochabamba. Los únicos datos reales son los de
> precipitación de SENAMHI (diciembre 2023 y enero 2026) y las tarifas del transporte público municipal
> (Ley Municipal 1575/2024), que se usaron para acotar rangos. Los resultados obtenidos sobre estos datos
> validan el funcionamiento del sistema, no su capacidad predictiva en el mercado real.

## 9. Cómo pasar a datos reales

1. Registrar las cotizaciones reales con las mismas columnas y convenciones en `crudo/cotizaciones_indrive.csv` con `fuente = captura_indrive` (guardar capturas en `capturas/`).
2. Si se mantienen filas sintéticas, no mezclarlas con las reales: conservar `fuente` y filtrar por ella en `preparar.py`.
3. Reemplazar las filas `supuesto` de `lluvia_senamhi.csv` por los resúmenes climáticos de SENAMHI de septiembre y octubre de 2026.
4. Volver a ejecutar `preparar.py` y actualizar las secciones 1, 4, 5 y 6 de este README.
