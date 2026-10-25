# Capa 2: Red bayesiana (Persona 2)

Modela cómo el contexto (hora, clima, eventos, tráfico y costos) cambia la demanda, la oferta y la probabilidad de escasez. Le entrega al modelo de Euler los valores D0 y S0 de cada contexto.

## Cómo ejecutar

Las dependencias están en el `requirements.txt` de la raíz (pgmpy es opcional, solo verifica los resultados).

```
cd capa2_bayes
python red.py                    # valida la red
python consultas.py              # consultas, pregunta 6, Monte Carlo y verificación
python traduccion.py             # tabla contexto -> D0, S0 para Euler
python dibujar.py                # guarda las figuras en figuras/
```

Desde la raíz también funciona `python -m capa2_bayes.consultas`. Los demás módulos la importan como `from capa2_bayes import traduccion`.

La inferencia está programada desde cero, igual que en clase: se **multiplica y normaliza**. pgmpy solo se usa para comprobar que el resultado coincide.

## Archivos

| Archivo | Qué hace | Funciones que usan otros |
|---|---|---|
| `red.py` | Variables, aristas y tablas de probabilidad con su justificación | `construir_red()`, `estimar_desde_datos()` |
| `consultas.py` | Inferencia exacta, entropía, Monte Carlo y pregunta 6 | `consultar(var, evidencia)` |
| `traduccion.py` | Puente con Euler: contexto → D0, S0 | `contexto_a_parametros()`, `muestrear_parametros()` |
| `dibujar.py` | Figuras para el informe | — |

## La red

- **Contexto (raíces):** Hora (valle/punta), Clima (seco/lluvia), Evento (no/sí), Costos (normal/alto)
- **Tráfico** ← Hora, Clima
- **Demanda** ← Hora, Clima, Evento
- **Oferta** ← Clima, Tráfico, Costos
- **Escasez** ← Demanda, Oferta

Precio y Servicios realizados quedan fuera de la red porque los calcula el modelo de Euler.

## Resultados principales

- **Consulta del documento** (viernes 19:00, lluvia, evento): P(escasez) = **0.69**. La demanda es alta con 0.75 y la oferta baja con 0.50.
- **Pregunta 6:** la lluvia sube P(demanda alta) en +0.155 en horas valle y en +0.195 en hora punta; la hora punta la sube en +0.25 con clima seco. La interacción es pequeña (+0.04), así que los efectos son casi aditivos. Se pueden separar porque Hora y Clima son padres distintos de Demanda y no tienen causas comunes, de modo que condicionar equivale a intervenir.
- **Monte Carlo vs. exacto:** con 100 000 muestras la diferencia es de 0.005. El muestreo con rechazo desperdicia casi todas las muestras porque el contexto consultado es raro (~0.4 %).
- **pgmpy** da exactamente el mismo resultado (0.690693).

## Calibración con datos (hecha por la Persona 4)

Los cuatro puntos que quedaban pendientes se resolvieron en `integracion/escenario_e.py` con los datos del Escenario E (**sintéticos**, ver `datos/README.md`):

1. **Tablas condicionales:** `estimar_desde_datos()` re-estima la red mezclando el supuesto experto (peso de 20 observaciones) con los datos. Es la "red calibrada" que usan `main.py` e `integracion/decision.py`; la red experta de este archivo sigue siendo la de referencia.
2. **Escasez:** en los datos D > S casi no depende del contexto (el precio equilibra el mercado), así que para calibrar se usó `tarifa_alta` como proxy.
3. **Discretización:** cortes en los terciles de la demanda y la oferta a precio de referencia (`resultados/tablas/E_calibracion_traduccion.csv`).
4. **Valores de traducción:** `VALORES_D0` y `VALORES_S0` de `traduccion.py` quedaron en 47/54/65 y 43/47/50.

Los nodos raíz (Hora, Clima, Evento, Costos) conservan los supuestos expertos; Costos no se observa en los datos.

## Posibles extensiones

- Agregar un nodo **Día** (laboral/viernes/fin de semana), porque la consulta del documento menciona el viernes.
- Agregar **tiempos de espera** como variable observada (relacionado con la pregunta 5).
- La pregunta 6 también se respondió con datos: ver la sección 7.6 del informe y `resultados/tablas/E_efectos_contexto.csv`.
