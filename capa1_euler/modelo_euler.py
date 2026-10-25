"""
modelo_euler.py


Modelo:
    D_k     = D0_k + beta  * (p_ref - p_k) + eps_k
    S_k     = S0_k + gamma * (p_k - p_costo)
    p_{k+1} = p_k  + dt * alpha * (D_k - S_k)
con restricciones: p_k >= p_costo, D_k >= 0, S_k >= 0.


"""

import numpy as np

# Parámetros nominales del Escenario A
PARAMS_BASE = {
    "alpha": 0.1,     # sensibilidad del precio al desequilibrio
    "beta": 2.0,      # sensibilidad de la demanda al precio
    "gamma": 1.5,     # sensibilidad de la oferta al precio
    "p_ref": 10.0,    # precio de referencia
    "p_costo": 5.0,   # costo de operación por viaje
    "dt": 5.0,        # intervalo (min)
    "T": 300.0,       # duración total (min)
    "p0": 10.0,       # precio inicial
}


def _parametros(parametros=None):
    par = dict(PARAMS_BASE)
    if parametros:
        par.update(parametros)
    return par


def _como_serie(valor, N):
    """Acepta un número, un arreglo de largo N o una función f(k)."""
    if callable(valor):
        return np.array([valor(k) for k in range(N)], dtype=float)
    arr = np.asarray(valor, dtype=float)
    if arr.ndim == 0:
        return np.full(N, float(arr))
    if len(arr) != N:
        raise ValueError(f"Se esperaban {N} valores y llegaron {len(arr)}")
    return arr


# ----------------------------------------------------------------------
# 1. Simulación
# ----------------------------------------------------------------------
def simular(parametros=None, D0=50.0, S0=50.0, ruido=0.0, semilla=None,
            restricciones=True):
    """
    Simula el ajuste del precio con Euler explícito.

    parametros : dict con cualquiera de las claves de PARAMS_BASE.
    D0, S0     : demanda y oferta base. Número, arreglo de largo N o
                 función f(k) (sirve para hora punta o lluvia por tramos).
    ruido      : desviación estándar del choque de demanda eps_k ~ N(0, ruido^2).
    semilla    : semilla para que el ruido sea reproducible.
    restricciones : si es False se quitan los límites (modelo lineal puro).

    Devuelve un dict con: t, p, D, S, servicios, escasez, eps, D0, S0, par.
    """
    par = _parametros(parametros)
    a, b, g = par["alpha"], par["beta"], par["gamma"]
    dt, p_ref, p_c = par["dt"], par["p_ref"], par["p_costo"]
    N = int(par["T"] / dt)

    D0s = _como_serie(D0, N)
    S0s = _como_serie(S0, N)
    rng = np.random.default_rng(semilla)
    eps = rng.normal(0.0, ruido, N) if ruido > 0 else np.zeros(N)

    p = np.zeros(N)
    D = np.zeros(N)
    S = np.zeros(N)
    p[0] = par["p0"]

    for k in range(N):
        D[k] = D0s[k] + b * (p_ref - p[k]) + eps[k]
        S[k] = S0s[k] + g * (p[k] - p_c)
        if restricciones:
            D[k] = max(0.0, D[k])
            S[k] = max(0.0, S[k])
        if k + 1 < N:
            p[k + 1] = p[k] + dt * a * (D[k] - S[k])
            if restricciones:
                p[k + 1] = max(p_c, p[k + 1])

    return {
        "t": np.arange(N) * dt,
        "p": p, "D": D, "S": S,
        "servicios": np.minimum(D, S),   # viajes efectivamente realizados
        "escasez": D > S,                # intervalos con demanda > oferta
        "eps": eps, "D0": D0s, "S0": S0s,
        "par": par,
    }


# ----------------------------------------------------------------------
# 2. Equilibrio y estabilidad
# ----------------------------------------------------------------------
def equilibrio(parametros=None, D0=50.0, S0=50.0):
    """
    Precio de equilibrio teórico (D = S):
        p* = (D0 - S0 + beta*p_ref + gamma*p_costo) / (beta + gamma)
    Si p* queda debajo del costo, el precio se queda en el piso p_costo.
    """
    par = _parametros(parametros)
    b, g = par["beta"], par["gamma"]
    p_eq = (D0 - S0 + b * par["p_ref"] + g * par["p_costo"]) / (b + g)
    p_eq_real = max(par["p_costo"], p_eq)
    D_eq = D0 + b * (par["p_ref"] - p_eq_real)
    S_eq = S0 + g * (p_eq_real - par["p_costo"])
    return {"p_eq": p_eq_real, "D_eq": D_eq, "S_eq": S_eq,
            "en_piso": p_eq < par["p_costo"]}


def estabilidad(parametros=None):
    """
    Restando p* a ambos lados: e_{k+1} = r * e_k, con
        r = 1 - dt*alpha*(beta + gamma).
    Estable si |r| < 1  <=>  0 < dt*alpha*(beta+gamma) < 2.
    Oscila (cambia de signo cada paso) si r < 0  <=>  producto > 1.
    """
    par = _parametros(parametros)
    prod = par["dt"] * par["alpha"] * (par["beta"] + par["gamma"])
    r = 1.0 - prod
    return {
        "producto": prod,
        "r": r,
        "estable": abs(r) < 1,
        "oscila": r < 0,
        "alpha_max": 2.0 / (par["dt"] * (par["beta"] + par["gamma"])),
        "pasos_para_reducir_error_a_1pct": (np.log(0.01) / np.log(abs(r))
                                            if 0 < abs(r) < 1 else np.inf),
    }


# ----------------------------------------------------------------------
# 3. Forma de espacio de estados (para la Persona 3)
# ----------------------------------------------------------------------
def matriz_F(parametros=None):
    """
    Estado x_k = (p_k, D_k). Sin restricciones activas:
        p_{k+1} = (1 - dt*a*g) p_k + dt*a D_k + c1
        D_{k+1} = -b (1 - dt*a*g) p_k - b*dt*a D_k + c2 + eps_{k+1}
    """
    par = _parametros(parametros)
    a, b, g, dt = par["alpha"], par["beta"], par["gamma"], par["dt"]
    return np.array([
        [1 - dt * a * g,          dt * a],
        [-b * (1 - dt * a * g),  -b * dt * a],
    ])


def termino_entrada(parametros=None, D0=50.0, S0=50.0):
    """
    Término constante B*u_k tal que x_{k+1} = F x_k + B u_k + w_k.
    (D0 y S0 son los de ese intervalo; si cambian, B u_k cambia.)
    El ruido de proceso es w_k = (0, eps_{k+1}), o sea Q = diag(0, ruido^2).
    """
    par = _parametros(parametros)
    a, b, g, dt = par["alpha"], par["beta"], par["gamma"], par["dt"]
    c1 = dt * a * (g * par["p_costo"] - S0)
    c2 = D0 + b * par["p_ref"] - b * c1
    return np.array([c1, c2])


# ----------------------------------------------------------------------
# 4. Métricas
# ----------------------------------------------------------------------
def metricas(sim, p_eq=None, tol_rel=0.01, umbral_escasez=1.0):
    """
    tol_rel: banda alrededor de p* para considerar que ya llegó al equilibrio
    (1 % por defecto). El tiempo hasta equilibrio es el primer instante a
    partir del cual el precio ya no sale de esa banda.
    umbral_escasez: se cuenta escasez solo si faltan al menos este número de
    vehículos (D - S >= umbral), para no contar oscilaciones despreciables.
    """
    p, t = sim["p"], sim["t"]
    if p_eq is None:
        p_eq = equilibrio(sim["par"], sim["D0"][-1], sim["S0"][-1])["p_eq"]
    fuera = np.abs(p - p_eq) > tol_rel * p_eq
    if not fuera.any():
        t_eq = 0.0
    elif fuera[-1]:
        t_eq = np.nan          # no llegó al equilibrio en el horizonte
    else:
        t_eq = t[np.where(fuera)[0][-1] + 1]
    return {
        "precio_equilibrio": p_eq,
        "precio_medio": p.mean(),
        "precio_max": p.max(),
        "precio_min": p.min(),
        "tiempo_hasta_equilibrio_min": t_eq,
        "intervalos_con_escasez": int(((sim["D"] - sim["S"]) >= umbral_escasez).sum()),
        "servicios_totales": sim["servicios"].sum(),
    }


# ----------------------------------------------------------------------
# 5. Análisis de sensibilidad (pregunta 1)
# ----------------------------------------------------------------------
def sensibilidad(nombre, valores, parametros=None, D0=50.0, S0=50.0):
    """Barre un parámetro y devuelve una fila de resultados por valor."""
    filas = []
    for v in valores:
        par = _parametros(parametros)
        par[nombre] = v
        est = estabilidad(par)
        eq = equilibrio(par, D0, S0)
        sim = simular(par, D0, S0)
        m = metricas(sim, eq["p_eq"])
        filas.append({
            nombre: v,
            "dt*a*(b+g)": est["producto"],
            "r": est["r"],
            "estable": est["estable"],
            "p_eq": eq["p_eq"],
            "precio_max": m["precio_max"],
            "t_equilibrio_min": m["tiempo_hasta_equilibrio_min"],
        })
    return filas


if __name__ == "__main__":
    eq = equilibrio()
    est = estabilidad()
    sim = simular()
    print("Precio de equilibrio p* =", round(eq["p_eq"], 4))
    print("dt*alpha*(beta+gamma) =", est["producto"], "-> r =", est["r"])
    print("F =\n", matriz_F())
    print(metricas(sim, eq["p_eq"]))
