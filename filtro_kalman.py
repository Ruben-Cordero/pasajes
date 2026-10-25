"""
filtro_kalman.py  (Persona 3: estimación con filtro de Kalman)

Usa modelo_euler.py de la Persona 1. Debe estar en la misma carpeta.

Estado:        x_k = (p_k, D_k)   (precio y demanda)
Dinámica:      x_k = F x_{k-1} + B u_k + w_k,   w_k ~ N(0, Q)
Observación:   y_k = H x_k + v_k,               v_k ~ N(0, R)

"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from modelo_euler import simular, matriz_F, termino_entrada, PARAMS_BASE


# ----------------------------------------------------------------------
# 1. Mediciones ruidosas
# ----------------------------------------------------------------------
def generar_mediciones_ruidosas(simulacion,
                                desviacion_medicion_precio=0.5,
                                desviacion_medicion_demanda=3.0,
                                solo_precio=False,
                                semilla=None,
                                indices_valores_atipicos=None,
                                magnitud_atipico_en_desviaciones=10.0):
    
    generador_aleatorio = np.random.default_rng(
        None if semilla is None else semilla + 10_000)

    estado_verdadero = np.column_stack([simulacion["p"], simulacion["D"]])

    if solo_precio:
        matriz_H = np.array([[1.0, 0.0]])
        desviaciones_medicion = np.array([desviacion_medicion_precio])
        valores_verdaderos_medidos = estado_verdadero[:, [0]]
    else:
        matriz_H = np.eye(2)
        desviaciones_medicion = np.array([desviacion_medicion_precio,
                                          desviacion_medicion_demanda])
        valores_verdaderos_medidos = estado_verdadero

    ruido_medicion = generador_aleatorio.normal(
        0.0, 1.0, valores_verdaderos_medidos.shape) * desviaciones_medicion
    mediciones = valores_verdaderos_medidos + ruido_medicion

    if indices_valores_atipicos is not None:
        for indice in indices_valores_atipicos:
            mediciones[indice, :] += (magnitud_atipico_en_desviaciones
                                      * desviaciones_medicion)

    matriz_R = np.diag(desviaciones_medicion ** 2)
    return mediciones, matriz_H, matriz_R

# ----------------------------------------------------------------------
# 2. Filtro de Kalman escrito a mano
# ----------------------------------------------------------------------
def construir_matriz_Q(desviacion_choque_demanda, factor_escala_q=1.0):
    return factor_escala_q * np.diag(
        [1e-4, desviacion_choque_demanda ** 2 + 1e-4])

def predecir_estado(estado_anterior, covarianza_anterior, matriz_F_transicion, entrada_constante, matriz_Q):
    estado_predicho = matriz_F_transicion @ estado_anterior + entrada_constante
    covarianza_predicha = (matriz_F_transicion @ covarianza_anterior
                           @ matriz_F_transicion.T + matriz_Q)
    return estado_predicho, covarianza_predicha

def calcular_ganancia_kalman(covarianza_predicha, matriz_H, matriz_R):
    covarianza_de_la_innovacion = (matriz_H @ covarianza_predicha
                                   @ matriz_H.T + matriz_R)
    return (covarianza_predicha @ matriz_H.T
            @ np.linalg.inv(covarianza_de_la_innovacion))

def corregir_estado(estado_predicho, covarianza_predicha, medicion,
                    matriz_H, matriz_R):
    """
        x = x_pred + K (y - H x_pred)
        P = (I - K H) P_pred
    """
    ganancia = calcular_ganancia_kalman(covarianza_predicha, matriz_H, matriz_R)
    innovacion = medicion - matriz_H @ estado_predicho
    estado_corregido = estado_predicho + ganancia @ innovacion

    identidad = np.eye(len(estado_predicho))
    covarianza_corregida = (identidad - ganancia @ matriz_H) @ covarianza_predicha
    # Se simetriza para evitar que errores de redondeo la desbalanceen
    covarianza_corregida = 0.5 * (covarianza_corregida + covarianza_corregida.T)
    return estado_corregido, covarianza_corregida, ganancia

def ejecutar_filtro_kalman(simulacion, mediciones, matriz_H, matriz_R, desviacion_choque_demanda,
                           estado_inicial=None, incertidumbre_inicial=25.0, factor_escala_q=1.0, factor_escala_r=1.0):

    parametros = simulacion["par"]
    cantidad_pasos = len(simulacion["p"])
    cantidad_mediciones = matriz_H.shape[0]

    if estado_inicial is None:
        estado_inicial = [parametros["p0"] + 5.0, simulacion["D"][0] - 20.0]

    matriz_F_transicion = matriz_F(parametros)
    matriz_Q = construir_matriz_Q(desviacion_choque_demanda, factor_escala_q)
    matriz_R_escalada = factor_escala_r * matriz_R

    estado_actual = np.array(estado_inicial, dtype=float)
    covarianza_actual = incertidumbre_inicial * np.eye(2)

    estimaciones = np.zeros((cantidad_pasos, 2))
    covarianzas = np.zeros((cantidad_pasos, 2, 2))
    ganancias = np.zeros((cantidad_pasos, 2, cantidad_mediciones))

    for k in range(cantidad_pasos):
        if k > 0:
            # Término constante: usa S0 del paso anterior y D0 del paso actual
            entrada_constante = termino_entrada(
                parametros,
                D0=simulacion["D0"][k],
                S0=simulacion["S0"][k - 1])
            estado_actual, covarianza_actual = predecir_estado(
                estado_actual, covarianza_actual,
                matriz_F_transicion, entrada_constante, matriz_Q)

        estado_actual, covarianza_actual, ganancia = corregir_estado(
            estado_actual, covarianza_actual, mediciones[k],
            matriz_H, matriz_R_escalada)

        estimaciones[k] = estado_actual
        covarianzas[k] = covarianza_actual
        ganancias[k] = ganancia

    desviaciones = np.sqrt(np.stack(
        [covarianzas[:, 0, 0], covarianzas[:, 1, 1]], axis=1))
    return {"estimaciones": estimaciones,
            "covarianzas": covarianzas,
            "desviaciones": desviaciones,
            "ganancias": ganancias}

def ejecutar_caso_completo(semilla=0,
                           desviacion_choque_demanda=3.0, desviacion_medicion_precio=0.5, desviacion_medicion_demanda=3.0,
                           solo_precio=False, D0=50.0, S0=50.0, parametros=None,
                           indices_valores_atipicos=None, estado_inicial=None, incertidumbre_inicial=25.0,
                           factor_escala_q=1.0, factor_escala_r=1.0):

    simulacion = simular(parametros, D0=D0, S0=S0,
                         ruido=desviacion_choque_demanda, semilla=semilla)
    mediciones, matriz_H, matriz_R = generar_mediciones_ruidosas(
        simulacion, desviacion_medicion_precio, desviacion_medicion_demanda,
        solo_precio, semilla, indices_valores_atipicos)
    resultado = ejecutar_filtro_kalman(
        simulacion, mediciones, matriz_H, matriz_R,
        desviacion_choque_demanda, estado_inicial, incertidumbre_inicial,
        factor_escala_q, factor_escala_r)
    return {"simulacion": simulacion, "mediciones": mediciones,
            "matriz_H": matriz_H, "matriz_R": matriz_R,
            "desviacion_choque_demanda": desviacion_choque_demanda,
            "solo_precio": solo_precio, "resultado": resultado}

# ----------------------------------------------------------------------
# 3. Métricas de desempeño
# ----------------------------------------------------------------------
def calcular_raiz_error_cuadratico_medio(valores_verdaderos, valores_estimados):
    return float(np.sqrt(np.mean((valores_verdaderos - valores_estimados) ** 2)))

def calcular_errores_estimacion(simulacion, resultado):
    return {
        "error_precio": calcular_raiz_error_cuadratico_medio(
            simulacion["p"], resultado["estimaciones"][:, 0]),
        "error_demanda": calcular_raiz_error_cuadratico_medio(
            simulacion["D"], resultado["estimaciones"][:, 1]),
    }

def calcular_cobertura_intervalos(simulacion, resultado, numero_desviaciones=2.0):
    valores_verdaderos = np.column_stack([simulacion["p"], simulacion["D"]])
    error_absoluto = np.abs(valores_verdaderos - resultado["estimaciones"])
    dentro_del_intervalo = error_absoluto <= (
        numero_desviaciones * resultado["desviaciones"])
    return {"cobertura_precio": float(dentro_del_intervalo[:, 0].mean()),
            "cobertura_demanda": float(dentro_del_intervalo[:, 1].mean())}

def calcular_tiempo_convergencia(simulacion, resultado, tolerancia_error_precio=1.0):
    error_precio = np.abs(simulacion["p"] - resultado["estimaciones"][:, 0])
    pasos_fuera_de_tolerancia = error_precio > tolerancia_error_precio
    if not pasos_fuera_de_tolerancia.any():
        return 0.0
    if pasos_fuera_de_tolerancia[-1]:
        return float("nan")
    ultimo_paso_fuera = np.where(pasos_fuera_de_tolerancia)[0][-1]
    return float(simulacion["t"][ultimo_paso_fuera + 1])

def resumir_desempeno(simulacion, resultado):
    resumen = {}
    resumen.update(calcular_errores_estimacion(simulacion, resultado))
    resumen.update(calcular_cobertura_intervalos(simulacion, resultado))
    resumen["tiempo_convergencia_min"] = calcular_tiempo_convergencia(
        simulacion, resultado)
    return resumen

# ----------------------------------------------------------------------
# 4. Experimentos pedidos en el documento
# ----------------------------------------------------------------------
def experimento_calibracion_q_r(caso, factores_escala_q=(0.01, 1.0, 100.0), factores_escala_r=(0.01, 1.0, 100.0)):
    filas = []
    for factor_q in factores_escala_q:
        for factor_r in factores_escala_r:
            resultado = ejecutar_filtro_kalman(
                caso["simulacion"], caso["mediciones"],
                caso["matriz_H"], caso["matriz_R"],
                caso["desviacion_choque_demanda"],
                factor_escala_q=factor_q, factor_escala_r=factor_r)
            fila = {"factor_escala_q": factor_q, "factor_escala_r": factor_r}
            fila.update(resumir_desempeno(caso["simulacion"], resultado))
            filas.append(fila)
    return pd.DataFrame(filas)


def repetir_experimento(numero_realizaciones=50, **argumentos_caso):
    filas = []
    for semilla in range(numero_realizaciones):
        caso = ejecutar_caso_completo(semilla=semilla, **argumentos_caso)
        filas.append(resumir_desempeno(caso["simulacion"], caso["resultado"]))
    return pd.DataFrame(filas)

def experimento_valor_informacion(numero_realizaciones=50, **argumentos_caso):
    solo_precio = repetir_experimento(
        numero_realizaciones, solo_precio=True, **argumentos_caso)
    precio_y_demanda = repetir_experimento(
        numero_realizaciones, solo_precio=False, **argumentos_caso)
    return pd.DataFrame({"solo_precio": solo_precio.mean(), "precio_y_demanda": precio_y_demanda.mean()})

def experimento_valores_atipicos(numero_realizaciones=50, indices_valores_atipicos=(20, 21, 40), **argumentos_caso):
    sin_atipicos = repetir_experimento(numero_realizaciones, **argumentos_caso)
    con_atipicos = repetir_experimento(
        numero_realizaciones,
        indices_valores_atipicos=list(indices_valores_atipicos),
        **argumentos_caso)
    return pd.DataFrame({"sin_atipicos": sin_atipicos.mean(),
                         "con_atipicos": con_atipicos.mean()})

# ----------------------------------------------------------------------
# 5. Gráficas y exportación
# ----------------------------------------------------------------------
def graficar_estimacion(caso, titulo="Estimación con filtro de Kalman", numero_desviaciones=2.0, ruta_guardado=None):
    simulacion = caso["simulacion"]
    mediciones = caso["mediciones"]
    resultado = caso["resultado"]
    tiempo = simulacion["t"]

    figura, ejes = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
    nombres = ["Precio", "Demanda"]
    verdaderos = [simulacion["p"], simulacion["D"]]

    for i in range(2):
        estimacion = resultado["estimaciones"][:, i]
        banda = numero_desviaciones * resultado["desviaciones"][:, i]
        ejes[i].plot(tiempo, verdaderos[i], "k-", label="Valor verdadero")
        if i < mediciones.shape[1]:
            ejes[i].plot(tiempo, mediciones[:, i], ".", alpha=0.4,
                         label="Mediciones ruidosas")
        ejes[i].plot(tiempo, estimacion, "r-", label="Estimación Kalman")
        ejes[i].fill_between(tiempo, estimacion - banda, estimacion + banda,
                             color="r", alpha=0.15,
                             label=f"±{numero_desviaciones:g} desviaciones")
        ejes[i].set_ylabel(nombres[i])
        ejes[i].grid(alpha=0.3)
        ejes[i].legend(loc="best")

    ejes[0].set_title(titulo)
    ejes[1].set_xlabel("Tiempo (min)")
    plt.tight_layout()
    if ruta_guardado:
        plt.savefig(ruta_guardado, dpi=150)
    plt.show()

def exportar_estimaciones_csv(caso, ruta_archivo="estimaciones_kalman.csv", numero_desviaciones=2.0):
    simulacion = caso["simulacion"]
    resultado = caso["resultado"]
    estimaciones = resultado["estimaciones"]
    banda = numero_desviaciones * resultado["desviaciones"]

    tabla = pd.DataFrame({
        "tiempo_min": simulacion["t"],
        "precio_estimado": estimaciones[:, 0],
        "precio_limite_inferior": estimaciones[:, 0] - banda[:, 0],
        "precio_limite_superior": estimaciones[:, 0] + banda[:, 0],
        "demanda_estimada": estimaciones[:, 1],
        "demanda_limite_inferior": estimaciones[:, 1] - banda[:, 1],
        "demanda_limite_superior": estimaciones[:, 1] + banda[:, 1],
    })
    tabla.to_csv(ruta_archivo, index=False)
    return tabla

# ----------------------------------------------------------------------
# Demostración (Escenario A)
# ----------------------------------------------------------------------
if __name__ == "__main__":
    caso_base = ejecutar_caso_completo(semilla=0)
    print("Desempeño:", resumir_desempeno(caso_base["simulacion"],
                                          caso_base["resultado"]))
    graficar_estimacion(caso_base, "Escenario A: precio y demanda")
    exportar_estimaciones_csv(caso_base)