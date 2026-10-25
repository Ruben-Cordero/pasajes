"""
params.py - Unica fuente de parametros para los scripts de integracion
Persona 4 (escenarios, datos, decision e integracion)

Los valores nominales son los del documento del caso (Escenario A) y
coinciden con modelo_euler.PARAMS_BASE (Persona 1). escenarios.py
comprueba al arrancar que no se hayan desincronizado.
"""

import os

RAIZ = os.path.dirname(os.path.abspath(__file__))
RESULTADOS = os.path.join(RAIZ, "resultados")
FIGURAS = os.path.join(RESULTADOS, "figuras")
TABLAS = os.path.join(RESULTADOS, "tablas")
DATOS_E = os.path.join(RAIZ, "datos", "procesado", "escenario_e.csv")

# ---------------------------------------------------------------------------
# Parametros nominales del modelo (claves iguales a modelo_euler.PARAMS_BASE)
# ---------------------------------------------------------------------------
PARAMS = {
    "alpha": 0.1,     # sensibilidad del precio al desequilibrio
    "beta": 2.0,      # sensibilidad de la demanda al precio
    "gamma": 1.5,     # sensibilidad de la oferta al precio
    "p_ref": 10.0,    # precio de referencia (Bs)
    "p_costo": 5.0,   # costo de operacion por viaje (Bs)
    "dt": 5.0,        # intervalo (min)
    "T": 300.0,       # duracion total (min)
    "p0": 10.0,       # precio inicial (Bs)
}
D0_BASE = 50.0
S0_BASE = 50.0

# Ventana de perturbacion de los escenarios B y C (minutos)
VENTANA = (60.0, 180.0)


def en_ventana(k, dt=PARAMS["dt"], ventana=VENTANA):
    """True si el paso k cae dentro de la ventana [inicio, fin)."""
    return ventana[0] <= k * dt < ventana[1]


def escalon(valor_base, valor_ventana, ventana=VENTANA):
    """Funcion f(k) para simular(): valor_ventana dentro de la ventana."""
    return lambda k: valor_ventana if en_ventana(k, ventana=ventana) else valor_base


# ---------------------------------------------------------------------------
# Escenarios del documento
# ---------------------------------------------------------------------------
ESCENARIOS = {
    "A": {"nombre": "Base (equilibrio)",
          "descripcion": "Parametros nominales. Con p0 = 10 el precio no arranca "
                         "en equilibrio (p* = 7.86): converge oscilando.",
          "D0": D0_BASE, "S0": S0_BASE,
          "D0_ventana": D0_BASE, "S0_ventana": S0_BASE},
    "B": {"nombre": "Hora punta",
          "descripcion": "D0 = 100 entre los minutos 60 y 180.",
          "D0": escalon(D0_BASE, 100.0), "S0": S0_BASE,
          "D0_ventana": 100.0, "S0_ventana": S0_BASE},
    "C": {"nombre": "Lluvia",
          "descripcion": "S0 = 30 entre los minutos 60 y 180.",
          "D0": D0_BASE, "S0": escalon(S0_BASE, 30.0),
          "D0_ventana": D0_BASE, "S0_ventana": 30.0},
    "D": {"nombre": "Estimacion con Kalman",
          "descripcion": "Dinamica del Escenario A con choque de demanda y "
                         "mediciones ruidosas; solo precio vs precio + solicitudes.",
          "D0": D0_BASE, "S0": S0_BASE,
          "D0_ventana": D0_BASE, "S0_ventana": S0_BASE},
    "E": {"nombre": "Datos de Cochabamba (SINTETICOS)",
          "descripcion": "datos/procesado/escenario_e.csv, generado con el propio "
                         "modelo (ver datos/README.md). No son mediciones reales.",
          "archivo": DATOS_E},
}

# ---------------------------------------------------------------------------
# Ruido (Escenario D). Mismos valores por defecto que filtro_kalman.py.
# ---------------------------------------------------------------------------
KALMAN_D = {
    "desviacion_choque_demanda": 3.0,
    "desviacion_medicion_precio": 0.5,
    "desviacion_medicion_demanda": 3.0,
    "realizaciones": 50,
}

# ---------------------------------------------------------------------------
# Escenario E: ruido con que se generaron los datos (datos/README.md, sec. 7)
# R = diag(0.18, 6.25): 0.4^2 + redondeo a 0.5 Bs (0.5^2/12) y 2.5^2.
# ---------------------------------------------------------------------------
KALMAN_E = {
    "var_medicion_precio": 0.4 ** 2 + 0.5 ** 2 / 12,
    "var_medicion_solicitudes": 2.5 ** 2,
    "desviacion_choque_demanda": 1.0,
}
TARIFA_ALTA = 1.3 * PARAMS["p_ref"]   # 13 Bs, igual que datos/preparar.py

# ---------------------------------------------------------------------------
# Regla de decision (pregunta 7). Valores elegidos con el barrido de
# decision.py (ver resultados/pregunta7.md).
# ---------------------------------------------------------------------------
UMBRAL_X = 0.30          # P(escasez) a partir de la cual se actua
UMBRAL_Y = TARIFA_ALTA   # precio (Bs) a partir del cual subir mas expulsa pasajeros
NIVEL_CONFIANZA_Z = 2.0  # intervalo = estimacion +- 2 desviaciones (~95 %)
PERMANENCIA_MIN = 6      # intervalos (30 min) que una accion se mantiene antes de cambiar

# Efecto supuesto de cada accion (para evaluar la regla en simulacion)
RECARGO_SUBIR = 2.0      # Bs que se suman al precio al SUBIR
BONO_INCENTIVO = 2.0     # Bs por viaje que se pagan al conductor al INCENTIVAR

SEMILLA = 2026
