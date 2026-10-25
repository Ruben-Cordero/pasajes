"""
traduccion.py - Puente entre la red bayesiana y el modelo de Euler
Persona 2 (Analista bayesiano/a)  ->  entrega a Persona 1 y Persona 4

La red habla en categorias (demanda "alta", oferta "baja"); el modelo de
Euler necesita numeros (D0, S0). Este archivo traduce una cosa en la otra.

Funciones que usan los demas:
  contexto_a_parametros(evidencia)  -> D0, S0, P(escasez) para un contexto
  muestrear_parametros(evidencia, n) -> n pares (D0, S0) para Monte Carlo:
        la Persona 4 corre Euler con cada par y obtiene una banda de
        precios en vez de un solo valor (incertidumbre cuantificada).
"""

import random
from itertools import product

try:
    from .red import construir_red, prob_conjunta, ESTADOS
    from .consultas import consultar, entropia
except ImportError:
    from red import construir_red, prob_conjunta, ESTADOS
    from consultas import consultar, entropia

# ---------------------------------------------------------------------------
# Tabla de traduccion: estado de la red -> valor numerico para Euler
# ---------------------------------------------------------------------------
# media = valores nominales del Escenario A (D0 = S0 = 50).
# Demanda alta = 100 (Escenario B, hora punta).
# Oferta baja  = 30  (Escenario C, lluvia).
# Demanda baja = 30 y Oferta alta = 70: supuestos simetricos.
# CALIBRADO (Persona 4) con datos/procesado/escenario_e.csv, que son datos
# SINTETICOS (ver datos/README.md, secciones 5 a 7). Cada valor es el
# promedio, dentro de su categoria, de la demanda y la oferta a precio de
# referencia: D0_hat = solicitudes - beta*(p_ref - precio) y
# S0_hat = vehiculos - gamma*(precio - p_costo). Las categorias salen de los
# terciles de D0_hat (50, 58) y S0_hat (45.5, 48). Detalle y comparacion con
# los valores orientativos del README de datos: integracion/escenario_e.py y
# resultados/tablas/E_calibracion_traduccion.csv.
# Valores anteriores (supuestos): D0 = 30/50/100, S0 = 30/50/70. Los
# escenarios B (D0=100) y C (S0=30) del documento siguen definidos aparte en
# integracion/params.py: son choques mas fuertes que cualquier contexto de los datos.
VALORES_D0 = {"baja": 47.0, "media": 54.0, "alta": 65.0}
VALORES_S0 = {"baja": 43.0, "media": 47.0, "alta": 50.0}

# Parametros nominales del documento (Escenario A); solo se usan para la
# vista previa del precio de equilibrio. El modelo oficial es el de Persona 1.
PARAMS_DOC = {"alpha": 0.1, "beta": 2.0, "gamma": 1.5,
              "p_ref": 10.0, "p_costo": 5.0, "dt": 5.0}


def distribucion_conjunta(evidencia=None, red=None):
    """P(Demanda, Oferta | evidencia). Se calcula conjunta porque, si no se
    conoce el clima, demanda y oferta NO son independientes (la lluvia sube
    una y baja la otra a la vez)."""
    red = red or construir_red()
    evidencia = evidencia or {}
    ocultas = [v for v in red["orden"] if v not in evidencia]
    acum = {(d, s): 0.0 for d, s in product(ESTADOS["Demanda"], ESTADOS["Oferta"])}
    for valores in product(*[red["estados"][v] for v in ocultas]):
        a = dict(evidencia)
        a.update(zip(ocultas, valores))
        acum[(a["Demanda"], a["Oferta"])] += prob_conjunta(red, a)
    total = sum(acum.values())
    return {k: v / total for k, v in acum.items()}


def precio_equilibrio(D0, S0, p=PARAMS_DOC):
    """Igualando D = S en las ecuaciones (2) y (3) del documento:
    p* = (D0 - S0 + beta*p_ref + gamma*p_costo) / (beta + gamma)."""
    pe = (D0 - S0 + p["beta"] * p["p_ref"] + p["gamma"] * p["p_costo"]) / (p["beta"] + p["gamma"])
    return max(p["p_costo"], pe)


def contexto_a_parametros(evidencia=None, modo="esperado", red=None):
    """Traduce un contexto a parametros para Euler.

    modo="esperado": D0 = sum P(estado) * valor   (promedio ponderado)
    modo="moda":     D0 = valor del estado mas probable

    Devuelve un diccionario con D0, S0, p_escasez, las distribuciones y
    su entropia (cuanta duda hay sobre el contexto).
    """
    red = red or construir_red()
    evidencia = evidencia or {}
    dd = consultar("Demanda", evidencia, red)
    ds = consultar("Oferta", evidencia, red)
    if modo == "esperado":
        D0 = sum(dd[e] * VALORES_D0[e] for e in dd)
        S0 = sum(ds[e] * VALORES_S0[e] for e in ds)
    elif modo == "moda":
        D0 = VALORES_D0[max(dd, key=dd.get)]
        S0 = VALORES_S0[max(ds, key=ds.get)]
    else:
        raise ValueError("modo debe ser 'esperado' o 'moda'")
    return {
        "D0": D0,
        "S0": S0,
        "p_escasez": consultar("Escasez", evidencia, red)["si"],
        "dist_demanda": dd,
        "dist_oferta": ds,
        "H_demanda": entropia(dd),
        "H_oferta": entropia(ds),
    }


def muestrear_parametros(evidencia=None, n=200, semilla=0, red=None):
    """n pares (D0, S0) sorteados de P(Demanda, Oferta | evidencia).
    Uso tipico (Persona 4):
        for D0, S0 in muestrear_parametros({"Clima": "lluvia"}, n=200):
            t, p, D, S = simular(params, D0, S0)   # funcion de Persona 1
    """
    conj = distribucion_conjunta(evidencia, red)
    rng = random.Random(semilla)
    pares = rng.choices(list(conj.keys()), weights=list(conj.values()), k=n)
    return [(VALORES_D0[d], VALORES_S0[s]) for d, s in pares]


if __name__ == "__main__":
    red = construir_red()
    print("Tabla de traduccion (entregar a Persona 1 y Persona 4)")
    print(f"  Demanda -> D0: {VALORES_D0}")
    print(f"  Oferta  -> S0: {VALORES_S0}\n")

    print("Parametros para Euler en cada contexto (modo esperado)")
    print(f"  {'Hora':<7}{'Clima':<8}{'Evento':<8}{'D0':>7}{'S0':>7}{'p*':>7}{'P(esc)':>8}")
    for h, c, e in product(ESTADOS["Hora"], ESTADOS["Clima"], ESTADOS["Evento"]):
        r = contexto_a_parametros({"Hora": h, "Clima": c, "Evento": e}, red=red)
        print(f"  {h:<7}{c:<8}{e:<8}{r['D0']:>7.1f}{r['S0']:>7.1f}"
              f"{precio_equilibrio(r['D0'], r['S0']):>7.2f}{r['p_escasez']:>8.3f}")
    print("  p* = precio de equilibrio de vista previa con parametros del documento")
    print("  (Escenario A nominal: D0=50, S0=50 -> p* =",
          f"{precio_equilibrio(50, 50):.2f})")

    print("\nMonte Carlo para la Persona 4: 10 pares (D0, S0) con lluvia en punta")
    pares = muestrear_parametros({"Hora": "punta", "Clima": "lluvia"}, n=10, red=red)
    print("  ", pares)
    precios = sorted(precio_equilibrio(d, s) for d, s in
                     muestrear_parametros({"Hora": "punta", "Clima": "lluvia"}, n=2000, red=red))
    print(f"  Con 2000 muestras: p* mediana={precios[1000]:.2f}, "
          f"intervalo 90 % = [{precios[100]:.2f}, {precios[1900]:.2f}]")
