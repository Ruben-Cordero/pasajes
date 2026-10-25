"""
no_lineal.py - Pregunta 4: umbral de tolerancia al precio, EKF y UKF (Capa 3)

Modelo con umbral de tolerancia: por encima de cierto precio los pasajeros
dejan de pedir viajes. Se multiplica la demanda lineal por una funcion
logistica que vale ~1 a precios normales y cae a 0 pasado el umbral:

    tol(p) = 1 / (1 + exp((p - p_tol) / s))
    D_k    = max(0, D0_k + beta (p_ref - p_k)) * tol(p_k) + eps_k

Con p_tol = 18 Bs y s = 2: a 18 Bs la mitad de los pasajeros deja de pedir.
Oferta y ajuste del precio son los del documento (modelo_euler.py).

Se comparan tres filtros sobre el Escenario B (D0 = 100 entre los minutos
60 y 180), que es donde el precio se acerca al umbral:
  - KF lineal: filtro_kalman.py tal cual, con la F del modelo SIN umbral.
  - EKF: linealiza la dinamica no lineal en cada paso (jacobiano).
  - UKF: propaga 5 sigma-puntos por la dinamica no lineal.
La observacion y = H x + v es lineal (se mide el precio y, si se quiere, las
solicitudes), asi que los tres corrigen con fk.corregir_estado().

Demostracion (desde la raiz):  python -m capa3_kalman.no_lineal
"""

import numpy as np
import pandas as pd

from capa1_euler import modelo_euler as me
from capa3_kalman import filtro_kalman as fk

P_TOLERANCIA = 18.0   # Bs: precio al que la mitad de los pasajeros deja de pedir
ESCALA_TOLERANCIA = 2.0  # Bs: que tan brusco es el corte


# ----------------------------------------------------------------------
# 1. Modelo con umbral de tolerancia
# ----------------------------------------------------------------------
def tolerancia(p, p_tol=P_TOLERANCIA, s=ESCALA_TOLERANCIA):
    return 1.0 / (1.0 + np.exp((p - p_tol) / s))


def demanda(p, D0, par, p_tol=P_TOLERANCIA, s=ESCALA_TOLERANCIA):
    return max(0.0, D0 + par["beta"] * (par["p_ref"] - p)) * tolerancia(p, p_tol, s)


def pendiente_demanda(p, D0, par, p_tol=P_TOLERANCIA, s=ESCALA_TOLERANCIA):
    """dD/dp. Sin umbral seria -beta; con umbral se vuelve mucho mas negativa
    cerca de p_tol, porque ademas del efecto lineal se pierden pasajeros."""
    lineal = D0 + par["beta"] * (par["p_ref"] - p)
    if lineal <= 0:
        return 0.0
    t = tolerancia(p, p_tol, s)
    return -par["beta"] * t + lineal * (-t * (1 - t) / s)


def simular_no_lineal(parametros=None, D0=50.0, S0=50.0, ruido=0.0, semilla=None,
                      p_tol=P_TOLERANCIA, s=ESCALA_TOLERANCIA):
    """Mismo esquema y mismas restricciones que me.simular(), con la demanda
    multiplicada por tol(p). Devuelve el mismo diccionario."""
    par = me._parametros(parametros)
    a, g, dt, p_c = par["alpha"], par["gamma"], par["dt"], par["p_costo"]
    N = int(par["T"] / dt)
    D0s, S0s = me._como_serie(D0, N), me._como_serie(S0, N)
    rng = np.random.default_rng(semilla)
    eps = rng.normal(0.0, ruido, N) if ruido > 0 else np.zeros(N)
    p, D, S = np.zeros(N), np.zeros(N), np.zeros(N)
    p[0] = par["p0"]
    for k in range(N):
        D[k] = max(0.0, demanda(p[k], D0s[k], par, p_tol, s) + eps[k])
        S[k] = max(0.0, S0s[k] + g * (p[k] - p_c))
        if k + 1 < N:
            p[k + 1] = max(p_c, p[k] + dt * a * (D[k] - S[k]))
    return {"t": np.arange(N) * dt, "p": p, "D": D, "S": S,
            "servicios": np.minimum(D, S), "escasez": D > S,
            "eps": eps, "D0": D0s, "S0": S0s, "par": par}


def equilibrio_no_lineal(parametros=None, D0=50.0, S0=50.0, p_tol=P_TOLERANCIA,
                         s=ESCALA_TOLERANCIA):
    """p* con D(p*) = S(p*) (biseccion) y estabilidad local: el error se
    multiplica por r = 1 - dt*alpha*(-dD/dp + gamma) en cada paso."""
    par = me._parametros(parametros)
    exceso = lambda p: demanda(p, D0, par, p_tol, s) - (S0 + par["gamma"] * (p - par["p_costo"]))
    lo, hi = par["p_costo"], 200.0
    if exceso(lo) <= 0:
        p_eq = lo
    else:
        for _ in range(100):
            mid = 0.5 * (lo + hi)
            lo, hi = (mid, hi) if exceso(mid) > 0 else (lo, mid)
        p_eq = 0.5 * (lo + hi)
    beta_local = -pendiente_demanda(p_eq, D0, par, p_tol, s)
    r = 1 - par["dt"] * par["alpha"] * (beta_local + par["gamma"])
    return {"p_eq": p_eq, "beta_local": beta_local, "r": r, "estable": abs(r) < 1,
            "alpha_max": 2.0 / (par["dt"] * (beta_local + par["gamma"]))}


# ----------------------------------------------------------------------
# 2. Transicion no lineal y su jacobiano
# ----------------------------------------------------------------------
def transicion(x, par, D0_k, S0_ant):
    """x_{k-1} -> x_k (sin ruido), en el mismo orden que simular():
    p_k = p_{k-1} + dt*alpha*(D_{k-1} - S_{k-1});  D_k = demanda(p_k)."""
    p, D = x
    p_n = max(par["p_costo"], p + par["dt"] * par["alpha"]
              * (D - S0_ant - par["gamma"] * (p - par["p_costo"])))
    return np.array([p_n, demanda(p_n, D0_k, par)])


def jacobiano(x, par, D0_k, S0_ant):
    """Derivadas de transicion() respecto de (p, D). Sin umbral coincide con
    me.matriz_F(); cuando el precio toca el piso p_costo, p_k no depende de x."""
    a, g, dt = par["alpha"], par["gamma"], par["dt"]
    p_n = transicion(x, par, D0_k, S0_ant)[0]
    fila_p = np.array([1 - dt * a * g, dt * a])
    if p_n <= par["p_costo"]:
        fila_p = np.zeros(2)
    return np.vstack([fila_p, pendiente_demanda(p_n, D0_k, par) * fila_p])


# ----------------------------------------------------------------------
# 3. EKF y UKF
# ----------------------------------------------------------------------
def _sigma_puntos(x, P, alpha_ut=1.0, beta_ut=2.0, kappa=1.0):
    """Sigma-puntos escalados (Julier y Uhlmann; Van der Merwe)."""
    n = len(x)
    lam = alpha_ut ** 2 * (n + kappa) - n
    L = np.linalg.cholesky((n + lam) * P)
    puntos = np.vstack([x, x + L.T, x - L.T])
    wm = np.full(2 * n + 1, 1.0 / (2 * (n + lam)))
    wc = wm.copy()
    wm[0] = lam / (n + lam)
    wc[0] = wm[0] + (1 - alpha_ut ** 2 + beta_ut)
    return puntos, wm, wc


def ejecutar_filtro_no_lineal(simulacion, mediciones, matriz_H, matriz_R, desviacion_choque_demanda,
                              metodo="EKF", estado_inicial=None, incertidumbre_inicial=25.0):
    """EKF o UKF con la dinamica con umbral. Misma interfaz y salida que
    fk.ejecutar_filtro_kalman() para poder usar fk.resumir_desempeno()."""
    par = simulacion["par"]
    N = len(simulacion["p"])
    if estado_inicial is None:
        estado_inicial = [par["p0"] + 5.0, simulacion["D"][0] - 20.0]
    Q = fk.construir_matriz_Q(desviacion_choque_demanda)
    x = np.array(estado_inicial, dtype=float)
    P = incertidumbre_inicial * np.eye(2)
    estimaciones, covarianzas = np.zeros((N, 2)), np.zeros((N, 2, 2))

    for k in range(N):
        if k > 0:
            D0_k, S0_ant = simulacion["D0"][k], simulacion["S0"][k - 1]
            if metodo == "EKF":
                J = jacobiano(x, par, D0_k, S0_ant)
                x = transicion(x, par, D0_k, S0_ant)
                P = J @ P @ J.T + Q
            elif metodo == "UKF":
                puntos, wm, wc = _sigma_puntos(x, P)
                prop = np.array([transicion(sp, par, D0_k, S0_ant) for sp in puntos])
                x = wm @ prop
                dif = prop - x
                P = (wc[:, None] * dif).T @ dif + Q
            else:
                raise ValueError("metodo debe ser 'EKF' o 'UKF'")
        x, P, _ = fk.corregir_estado(x, P, mediciones[k], matriz_H, matriz_R)
        estimaciones[k], covarianzas[k] = x, P

    desviaciones = np.sqrt(np.stack([covarianzas[:, 0, 0], covarianzas[:, 1, 1]], axis=1))
    return {"estimaciones": estimaciones, "covarianzas": covarianzas, "desviaciones": desviaciones}


# ----------------------------------------------------------------------
# 4. Experimento: KF lineal vs EKF vs UKF
# ----------------------------------------------------------------------
def correr_filtros(sim, solo_precio, semilla, desviacion_choque_demanda=3.0,
                   desviacion_medicion_precio=0.5, desviacion_medicion_demanda=3.0):
    med, H, R = fk.generar_mediciones_ruidosas(sim, desviacion_medicion_precio,
                                               desviacion_medicion_demanda, solo_precio, semilla)
    resultados = {"KF lineal": fk.ejecutar_filtro_kalman(sim, med, H, R, desviacion_choque_demanda)}
    for metodo in ("EKF", "UKF"):
        resultados[metodo] = ejecutar_filtro_no_lineal(sim, med, H, R, desviacion_choque_demanda,
                                                       metodo)
    return med, resultados


def experimento_filtros(parametros, D0, S0, numero_realizaciones=50, desviacion_choque_demanda=3.0,
                        **ruido_medicion):
    filas = []
    for solo_precio in (True, False):
        acumulado = {}
        for semilla in range(numero_realizaciones):
            sim = simular_no_lineal(parametros, D0=D0, S0=S0, ruido=desviacion_choque_demanda,
                                    semilla=semilla)
            _, res = correr_filtros(sim, solo_precio, semilla, desviacion_choque_demanda,
                                    **ruido_medicion)
            for nombre, r in res.items():
                acumulado.setdefault(nombre, []).append(fk.resumir_desempeno(sim, r))
        for nombre, lista in acumulado.items():
            fila = {"mediciones": "solo precio" if solo_precio else "precio + solicitudes",
                    "filtro": nombre}
            fila.update(pd.DataFrame(lista).mean().to_dict())
            filas.append(fila)
    return pd.DataFrame(filas)


if __name__ == "__main__":
    par = {"alpha": 0.03}
    D0 = lambda k: 100.0 if 60 <= k * 5 < 180 else 50.0
    for a in (0.1, 0.03):
        print(f"alpha = {a}:", {k: round(float(v), 3) for k, v in
                                equilibrio_no_lineal({"alpha": a}, D0=100).items()})
    print(experimento_filtros(par, D0, 50.0, numero_realizaciones=10).round(3).to_string(index=False))
