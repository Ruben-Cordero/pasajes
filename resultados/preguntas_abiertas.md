# Respuestas a las preguntas abiertas del caso

Resumen de las 7 preguntas de la sección 5 del documento del caso. El desarrollo completo está en la **sección 7 del informe** (`informe/informe.docx`); aquí van la respuesta corta, el número clave y dónde verificarlo. Todas las tablas están en `resultados/tablas/` y se regeneran con `python reproducir.py`.

> El Escenario E usa **datos sintéticos** (ver `datos/README.md`). Los resultados que salen de E validan el sistema, no predicen el mercado real.

## 1. Sensibilidad: ¿qué parámetro pesa más en las oscilaciones?

**α y β.** El error respecto del equilibrio se multiplica por r = 1 − Δt α (β + γ) en cada intervalo. Cuando r < 0, la oscilación siempre tiene periodo de 10 minutos; los parámetros cambian su amplitud y su duración, no su frecuencia.

- **α** no cambia el precio de equilibrio, pero decide la estabilidad: subirlo un 14 % (hasta 0,114) vuelve inestable el precio. Con α a la mitad, el precio llega al equilibrio en 10 minutos y sin sobreimpulso.
- **β y γ** mueven el equilibrio en sentidos opuestos (elasticidades +0,156 y −0,156) y afectan la dinámica solo a través de su suma. Un 25 % más de β ya lleva a r = −1.
- **Conviene estimar con más precisión α y β.**

Detalle: informe 7.1 · `sensibilidad_parametros.csv` · `figuras/sensibilidad_parametros.png` · cuaderno `capa1_euler/precio_dinamico_transporte.ipynb`

## 2. Identificabilidad: ¿se pueden estimar la demanda latente y los parámetros?

**La demanda latente sí; los parámetros, no con una regresión simple.** El filtro de Kalman estima la demanda aunque solo se mida el precio. Pero en los datos de E una regresión simple da pendientes muy distintas de las verdaderas:

| Parámetro | Valor verdadero | Regresión simple |
|---|---|---|
| Δt α | 0,50 | 0,23 |
| −β | −2,00 | +0,58 (signo contrario) |
| γ | 1,50 | 0,84 |

La causa es la simultaneidad (el precio responde a la demanda y la demanda al precio), más el ruido de medición. Mejorarían la identificabilidad: rechazos de viaje y tiempos de espera, cambios de precio exógenos que sirvan como variables instrumentales, o estimar α, β y γ como estados del filtro.

Detalle: informe 3.4.2 y 7.2 · `E_identificabilidad.csv`

## 3. Calibración del filtro: ¿cómo elegir Q y R?

**R con el error conocido de cada sensor y Q ajustado hasta que el NIS medio sea igual al número de mediciones.** En el Escenario D, escalando Q y R:

| Q × | R × | Qué pasa |
|---|---|---|
| 1 | 1 | Menor error (0,44 Bs) y cobertura de 95 %: bien calibrado |
| 0,01 | 1 | Confía de más en el modelo: lento (289 min) y cobertura de 22 % |
| 1 | 0,01 | Confía de más en las mediciones: copia el ruido, cobertura de 16 % |
| 100 | 100 | Intervalos demasiado anchos (cobertura de 98 %) y más error |

En los datos de E, la prueba NIS llevó a escalar Q por 30 (NIS medio = 2,11, esperado 2).

Detalle: informe 3.4.4 y 7.3 · `kalman_sensibilidad_QR.csv` · `E_kalman_innovaciones.csv`

## 4. No linealidades: umbral de tolerancia al precio, ¿EKF o UKF?

**Con umbral, el α nominal vuelve inestable el precio; para estimar, el EKF basta.** Se modeló que a 18 Bs la mitad de los pasajeros deja de pedir (`capa3_kalman/no_lineal.py`).

- En hora punta el equilibrio baja de 22,14 a 15,81 Bs. Pero cerca del umbral la demanda cae 9,8 solicitudes por boliviano en vez de 2, así que r = −4,65 y el precio salta entre 5 y 35 Bs. El límite de estabilidad baja a α < 0,035.
- Con α = 0,03 y midiendo solo el precio:

| Filtro | Error del precio | Cobertura |
|---|---|---|
| KF lineal (modelo sin umbral) | 1,48 Bs | 57 % |
| EKF | 0,38 Bs | 95 % |
| UKF | 0,36 Bs | 95 % |

El EKF y el UKF dan casi lo mismo; el UKF solo se nota en el arranque. El EKF es suficiente y más barato; el UKF conviene con umbrales más bruscos.

Detalle: informe 7.4 · `no_lineal_estabilidad.csv` · `no_lineal_filtros.csv` · `figuras/no_lineal_*.png`

## 5. Valor de la información: ¿cuánto aporta una segunda señal?

**Medir también las solicitudes mejora mucho la demanda y poco el precio**, porque el precio ya se mide directamente.

- Escenario D: el error de la demanda baja de 3,98 a 2,19 (−45 %).
- Escenario E: el error de predicción del precio baja de 2,63 a 1,47 Bs.
- Con umbral de tolerancia (EKF): el error de la demanda baja de 4,45 a 2,26.

Una tercera señal, como los tiempos de espera, aportaría sobre todo a la oferta, que hoy el filtro no observa.

Detalle: informe 3.3 y 7.5 · `kalman_valor_informacion.csv`

## 6. Inferencia causal: ¿cómo separar el efecto de la lluvia del de la hora punta?

**En la red, fijando un factor y moviendo el otro; en los datos, con una regresión que incluya todos los factores.**

- **Red bayesiana:** la lluvia sube P(demanda alta) en +0,155 en valle y +0,195 en punta; la hora punta la sube en +0,25. La interacción es de 0,04, así que los efectos son casi aditivos. Condicionar equivale a intervenir porque Hora y Clima no tienen causas comunes.
- **Datos:** casi toda la lluvia cae en hora punta y coincide con el evento, así que comparar promedios confunde los efectos.

| Efecto de la lluvia sobre la demanda base | Solicitudes |
|---|---|
| Diferencia de medias ingenua | +22,6 |
| Regresión con hora y lluvia | +15,6 |
| Regresión con todos los factores | +10,0 ± 0,5 |
| Valor con que se generaron los datos | +10 |

Para separar bien los efectos hacen falta intervalos con lluvia fuera de la hora punta (aquí solo hay 9) y registrar todo el contexto.

Detalle: informe 7.6 · `E_efectos_contexto.csv` · `capa2_bayes/consultas.py` · `capa2_bayes/figuras/pregunta6.png`

## 7. Decisión: ¿cuándo subir el precio y cuándo incentivar la oferta?

**Si P(escasez) > 0,30 se actúa. Se sube el precio mientras no sea seguro que ya supera 13 Bs, y se incentiva a los conductores cuando sí lo es. Cada acción se mantiene al menos 30 minutos.**

- Detecta el 100 % de los intervalos de estrés en B y C, y el 98 % en E.
- En los tres escenarios retiene pasajeros en vez de expulsarlos.
- El bono cuesta unos 65 Bs por pasajero retenido, así que se justifica por proteger al pasajero de precios altos, no por eficiencia.

Detalle completo, con la elección de X e Y y sus límites: [pregunta7.md](pregunta7.md) · informe 6 y 7.7

## Extras del Escenario D

- **Valores atípicos:** tres lecturas atípicas duplican el error del precio (0,44 → 0,97 Bs). Un filtro robusto con prueba chi-cuadrado (`capa3_kalman/extensiones.py`) los detecta todos y deja el error en 0,50 Bs. Ver `kalman_atipicos.csv`.
- **Predicción a m pasos:** el error del precio es de 1,00 Bs a 5 minutos y de 1,77 Bs a 15 minutos, y después casi no crece. La regla puede anticipar unos 10 a 15 minutos. Ver `kalman_pronostico.csv`.

Detalle: informe 7.8
