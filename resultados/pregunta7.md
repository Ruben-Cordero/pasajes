# Pregunta 7: ¿cuándo incentivar a los conductores en vez de subir el precio?

> El Escenario E usa **datos sintéticos** generados con el propio modelo (ver `datos/README.md`).
> Los números de E validan que el sistema funciona, no su capacidad predictiva en el mercado real.

## Respuesta

En cada intervalo de 5 minutos:

| Condición | Acción |
|---|---|
| P(escasez) > **X = 0.30** y límite inferior del precio estimado > **Y = 13 Bs** | **INCENTIVAR** a los conductores (bono) |
| P(escasez) > X = 0.30 y límite inferior ≤ 13 Bs | **SUBIR** el precio |
| P(escasez) ≤ 0.30 | **MANTENER** |

- **P(escasez)** viene de la red bayesiana (Persona 2) para el contexto: hora, clima, evento y tráfico.
- **El precio estimado y su desviación** vienen del filtro de Kalman (Persona 3).
- **Límite inferior:** es la estimación menos 2 desviaciones (≈95 %). Se usa este límite y no la estimación puntual para que "el precio ya supera Y" tenga una confianza de 97,5 %. Así solo se deja de subir el precio y se paga el bono cuando estamos seguros de que el precio ya es alto. Si se usara la estimación puntual, el ruido haría pagar bonos cuando el precio real todavía está bajo Y.
- **Permanencia mínima:** cada acción se mantiene al menos 30 minutos (6 intervalos) antes de cambiar.

Implementación: `decision.py` (`decidir`, `decidir_secuencia`, `explicar`). Los umbrales están en `params.py`.

## Cómo se eligieron X e Y

Se probaron X de 0,05 a 0,95 e Y de 8 a 22 Bs sobre tres escenarios:

- **B y C:** los escenarios del documento, con Kalman sobre mediciones simuladas.
- **E:** los 7 días de datos sintéticos, con Kalman sobre `precio_bs` y `solicitudes`.

Cada acción se traduce en un cambio de D0 y S0, y se vuelve a simular con `simular()`:

- **SUBIR:** recargo de 2 Bs. D0 baja en β·2 y S0 sube en γ·2.
- **INCENTIVAR:** bono de 2 Bs por viaje. S0 sube en γ·2.

Archivos:

- `resultados/tablas/decision_barrido.csv`
- `decision_eleccion_X.csv`
- `decision_eleccion_Y.csv`
- `decision_permanencia.csv`
- `resultados/figuras/decision_barrido.png`

**X = 0,30.** Se busca que la regla actúe en los intervalos de estrés y no en los tranquilos. Los intervalos de estrés son la ventana de B y C, y en E los intervalos con `tarifa_alta`. El índice de Youden (detección − falsa alarma, promedio de B, C y E) forma una meseta de **0,893 entre X = 0,25 y 0,35**:

- Por debajo de 0,25 baja a 0,275, porque la regla también actúa en valle seco, donde P(escasez) es 0,215 con la red experta.
- Por encima de 0,65 cae a 0, porque ya no actúa ni en hora punta con lluvia, donde P(escasez) es 0,66–0,67.

Se tomó el punto medio de la meseta para tener margen en ambos sentidos.

**Y = 13 Bs.** Bajar Y hace que se incentive en más intervalos y se suba en menos. Por eso se retienen más pasajeros, pero se pagan más bonos.

- Para cada paso de Y+1 a Y se calculó el costo marginal por pasajero retenido.
- El mínimo está en **Y = 13 Bs: 64,6 Bs de bono por pasajero retenido**. En el resto de la grilla va de 65 a 93 Bs.
- 13 Bs es también 1,3 × p_ref, el umbral de `tarifa_alta` que se observa en los datos.
- **Advertencia:** la curva es bastante plana entre 8 y 15 Bs (65–69 Bs por pasajero). Y queda poco identificado, y en la práctica es una decisión de política sobre cuánto se quiere proteger al pasajero.

## Resultados con X = 0,30, Y = 13 Bs y permanencia de 30 min

| Escenario | MANTENER | SUBIR | INCENTIVAR | Detección | Falsa alarma | Δ servicios | Demanda insatisfecha (base → regla) | Costo de bonos |
|---|---|---|---|---|---|---|---|---|
| B (hora punta) | 60 % | 10 % | 30 % | 100 % | 0 % | +1,1 % | 149 → 142 | 2 742 Bs |
| C (lluvia) | 53 % | 27 % | 20 % | 100 % | 11 % | +1,2 % | 80 → 66 | 1 108 Bs |
| E (7 días, sintético) | 65 % | 22 % | 13 % | 98 % | 18 % | +0,1 % | 1 593 → 1 831 | 20 739 Bs |

En los tres escenarios la regla atrae pasajeros en vez de expulsarlos: B 32, C 20, E 306. La razón es que el bono aumenta la oferta, el precio de mercado baja y entra más demanda.

## Límites de esta respuesta

1. **La evaluación es en lazo abierto respecto de la información.** Las decisiones se toman con las estimaciones de Kalman de la trayectoria sin intervenir, y después se simula el efecto. En un sistema real la acción cambiaría las mediciones siguientes.
2. **Un recargo fijo lo absorbe el precio dinámico.** En el modelo lineal, si el algoritmo de Euler sigue ajustando el precio, un recargo fijo δ baja el precio de equilibrio de mercado en δ. El pasajero termina pagando lo mismo en equilibrio, y SUBIR solo actúa en el transitorio. El bono, en cambio, mueve el equilibrio: p* baja γb/(β+γ) = 0,86 Bs y salen β·0,86 ≈ 1,7 viajes más por intervalo.
3. **El parpadeo.** Sin permanencia mínima, la acción cambiaba 20 veces en 60 intervalos en C y 179 veces en E. Con la dinámica oscilante (r = −0,75), cada cambio genera un transitorio y la demanda insatisfecha **subía** (C: 80 → 106). Con 30 minutos de permanencia C queda en 66. **En E la demanda insatisfecha todavía sube un 15 %** (1 593 → 1 831), porque los contextos cambian rápido y las acciones siguen generando transitorios. Una regla de producción necesitaría una acción gradual (rampa) en lugar de un escalón.
4. **El bono es caro.** Se paga en todos los viajes del intervalo para retener pocos pasajeros: unos 65 Bs por pasajero retenido. Con estos supuestos, incentivar solo se justifica para proteger al pasajero de precios altos, no por eficiencia. El monto del bono (2 Bs) y el del recargo (2 Bs) son supuestos (`params.py`).
5. **La P(escasez) de la red depende de supuestos expertos** (Persona 2) o de una calibración con datos sintéticos que usa `tarifa_alta` como proxy de escasez. La escasez D > S casi no depende del contexto en los datos (≈16 % en todos), porque el precio equilibra el mercado.
6. **Ningún dato es real.** Con datos de una plataforma habría que recalibrar X e Y con el mismo script (`python decision.py`).
