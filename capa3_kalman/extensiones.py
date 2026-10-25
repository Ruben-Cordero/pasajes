"""
extensiones.py - Extensiones del filtro de Kalman (Capa 3)

Usa las funciones de filtro_kalman.py (Persona 3) sin modificarlas.

1. pronosticar(): prediccion x_{k+m|k} con su covarianza. El documento pide
   "predicciones x_{k+m|k} para anticipar decisiones de fijacion de tarifas".
2. ejecutar_filtro_robusto(): el mismo ciclo prediccion-correccion, pero
   descarta una medicion si su innovacion es improbable segun el propio
   filtro (prueba chi-cuadrado sobre el NIS). Responde a "robustez frente a
   valores atipicos" del Escenario D.

Demostracion (desde la raiz):  python -m capa3_kalman.extensiones
"""

import numpy as np
import pandas as pd

from capa1_euler.modelo_euler import matriz_F, termino_entrada
from capa3_kalman import filtro_kalman as fk

# Cuantil 99,9 % de la chi-cuadrado con 1 y 2 grados de libertad: una
# medicion normal solo supera este umbral 1 vez de cada 1000.
UMBRAL_CHI2_999 = {1: 10.828, 2: 13.816}


# ----------------------------------------------------------------------
# 1. Prediccion a m pasos
# ----------------------------------------------------------------------
def pronosticar(estado, covarianza, parametros, D0_futuro, S0_futuro, matriz_Q):
    """
    Aplica solo la etapa de prediccion m veces, sin corregir:
        x_{k+j|k} = F x_{k+j-1|k} + B u_{k+j}
        P_{k+j|k} = F P_{k+j-1|k} F' + Q
    D0_futuro[j] y S0_futuro[j] son los valores en el paso k+j (j = 0..m);
    se usa el mismo B u_k que en ejecutar_filtro_kalman().
    Devuelve (estados, covarianzas) con m filas: j = 1..m.
    """
    F = matriz_F(parametros)
    m = len(D0_futuro) - 1
    x = np.array(estado, dtype=float)
    P = np.array(covarianza, dtype=float)
    estados, covarianzas = np.zeros((m, 2)), np.zeros((m, 2, 2))
    for j in range(1, m + 1):
        Bu = termino_entrada(parametros, D0=D0_futuro[j], S0=S0_futuro[j - 1])
        x, P = fk.predecir_estado(x, P, F, Bu, matriz_Q)
        estados[j - 1], covarianzas[j - 1] = x, P
    return estados, covarianzas


def experimento_pronostico(numero_realizaciones=50, horizontes=(1, 2, 3, 6, 12),
                           paso_inicial=12, numero_desviaciones=2.0, **argumentos_caso):
    """Error y cobertura de x_{k+m|k} frente al precio y la demanda verdaderos,
    promediando todos los origenes k >= paso_inicial (se salta el arranque)."""
    m_max = max(horizontes)
    errores = {m: {"p": [], "D": [], "cub_p": [], "cub_D": []} for m in horizontes}
    for semilla in range(numero_realizaciones):
        caso = fk.ejecutar_caso_completo(semilla=semilla, **argumentos_caso)
        sim, res = caso["simulacion"], caso["resultado"]
        Q = fk.construir_matriz_Q(caso["desviacion_choque_demanda"])
        N = len(sim["p"])
        for k in range(paso_inicial, N - m_max):
            est, cov = pronosticar(res["estimaciones"][k], res["covarianzas"][k], sim["par"],
                                   sim["D0"][k:k + m_max + 1], sim["S0"][k:k + m_max + 1], Q)
            for m in horizontes:
                verdad = np.array([sim["p"][k + m], sim["D"][k + m]])
                e = verdad - est[m - 1]
                sd = np.sqrt(np.diag(cov[m - 1]))
                errores[m]["p"].append(e[0])
                errores[m]["D"].append(e[1])
                errores[m]["cub_p"].append(abs(e[0]) <= numero_desviaciones * sd[0])
                errores[m]["cub_D"].append(abs(e[1]) <= numero_desviaciones * sd[1])
    dt = fk.PARAMS_BASE["dt"] if not argumentos_caso.get("parametros") else \
        argumentos_caso["parametros"].get("dt", fk.PARAMS_BASE["dt"])
    filas = []
    for m in horizontes:
        e = errores[m]
        filas.append({"pasos_m": m, "minutos": m * dt,
                      "error_precio": float(np.sqrt(np.mean(np.square(e["p"])))),
                      "error_demanda": float(np.sqrt(np.mean(np.square(e["D"])))),
                      "cobertura_precio": float(np.mean(e["cub_p"])),
                      "cobertura_demanda": float(np.mean(e["cub_D"]))})
    return pd.DataFrame(filas)


# ----------------------------------------------------------------------
# 2. Filtro robusto a valores atipicos
# ----------------------------------------------------------------------
def ejecutar_filtro_robusto(simulacion, mediciones, matriz_H, matriz_R, desviacion_choque_demanda,
                            estado_inicial=None, incertidumbre_inicial=25.0, umbral_nis=None,
                            pasos_sin_prueba=3):
    """
    Igual que fk.ejecutar_filtro_kalman(), con una prueba antes de corregir:
        NIS_k = nu' S^-1 nu,  nu = y_k - H x_pred,  S = H P_pred H' + R
    Si NIS_k supera el cuantil 99,9 % de la chi-cuadrado, la medicion se
    considera atipica y se descarta (se queda la prediccion). Con
    umbral_nis=None se usa ese cuantil; con umbral_nis=np.inf no descarta
    nada y reproduce el filtro estandar.

    Los primeros `pasos_sin_prueba` intervalos (15 min) se aceptan siempre:
    el estado inicial esta lejos del verdadero y, si se rechazaran esas
    mediciones, el filtro nunca se corregiria.
    """
    parametros = simulacion["par"]
    cantidad_pasos = len(simulacion["p"])
    m = matriz_H.shape[0]
    umbral = UMBRAL_CHI2_999[m] if umbral_nis is None else umbral_nis
    if estado_inicial is None:
        estado_inicial = [parametros["p0"] + 5.0, simulacion["D"][0] - 20.0]

    F = matriz_F(parametros)
    Q = fk.construir_matriz_Q(desviacion_choque_demanda)
    x = np.array(estado_inicial, dtype=float)
    P = incertidumbre_inicial * np.eye(2)
    estimaciones = np.zeros((cantidad_pasos, 2))
    covarianzas = np.zeros((cantidad_pasos, 2, 2))
    rechazadas = np.zeros(cantidad_pasos, dtype=bool)

    for k in range(cantidad_pasos):
        if k > 0:
            Bu = termino_entrada(parametros, D0=simulacion["D0"][k], S0=simulacion["S0"][k - 1])
            x, P = fk.predecir_estado(x, P, F, Bu, Q)
        nu = mediciones[k] - matriz_H @ x
        S = matriz_H @ P @ matriz_H.T + matriz_R
        if k >= pasos_sin_prueba and float(nu @ np.linalg.solve(S, nu)) > umbral:
            rechazadas[k] = True
        else:
            x, P, _ = fk.corregir_estado(x, P, mediciones[k], matriz_H, matriz_R)
        estimaciones[k], covarianzas[k] = x, P

    desviaciones = np.sqrt(np.stack([covarianzas[:, 0, 0], covarianzas[:, 1, 1]], axis=1))
    return {"estimaciones": estimaciones, "covarianzas": covarianzas,
            "desviaciones": desviaciones, "rechazadas": rechazadas}


def experimento_atipicos_robusto(numero_realizaciones=50, indices_valores_atipicos=(20, 21, 40),
                                 **argumentos_caso):
    """Filtro estandar vs robusto, con y sin valores atipicos (10 desviaciones,
    los mismos que fk.experimento_valores_atipicos)."""
    columnas = {}
    for nombre, atipicos in [("sin_atipicos", None), ("con_atipicos", list(indices_valores_atipicos))]:
        estandar, robusto, n_rech, rech_ok = [], [], [], []
        for semilla in range(numero_realizaciones):
            caso = fk.ejecutar_caso_completo(semilla=semilla, indices_valores_atipicos=atipicos,
                                             **argumentos_caso)
            sim = caso["simulacion"]
            estandar.append(fk.resumir_desempeno(sim, caso["resultado"]))
            r = ejecutar_filtro_robusto(sim, caso["mediciones"], caso["matriz_H"], caso["matriz_R"],
                                        caso["desviacion_choque_demanda"])
            robusto.append(fk.resumir_desempeno(sim, r))
            n_rech.append(int(r["rechazadas"].sum()))
            if atipicos:
                rech_ok.append(float(r["rechazadas"][atipicos].mean()))
        for filtro, filas in [("estandar", estandar), ("robusto", robusto)]:
            serie = pd.DataFrame(filas).mean()
            serie["mediciones_descartadas"] = 0.0 if filtro == "estandar" else float(np.mean(n_rech))
            serie["atipicos_detectados"] = (float(np.mean(rech_ok)) if filtro == "robusto" and rech_ok
                                            else np.nan)
            columnas[f"{nombre}_{filtro}"] = serie
    tabla = pd.DataFrame(columnas)
    tabla.index.name = "metrica"
    return tabla


if __name__ == "__main__":
    print(experimento_pronostico(10).round(3).to_string(index=False))
    print(experimento_atipicos_robusto(10).round(3).to_string())
