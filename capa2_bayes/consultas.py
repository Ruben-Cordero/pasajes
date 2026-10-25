"""
consultas.py - Inferencia en la red bayesiana
Persona 2 (Analista bayesiano/a)

Misma receta que en clase: MULTIPLICAR Y NORMALIZAR.
Para P(X | evidencia):
  1. Recorrer todas las combinaciones de las variables que no conozco.
  2. Para cada una, multiplicar las tablas (probabilidad conjunta).
  3. Sumar por cada valor de X.
  4. Dividir por el total para que sume 1.
Con 8 variables son a lo sumo 576 combinaciones: se calcula exacto.

Incluye:
  - consultar(): inferencia exacta por enumeracion.
  - entropia(): cuanta duda queda (bits), como en bayes_filtro.ipynb.
  - monte_carlo(): la misma consulta con muestras (muestreo por rechazo),
    para comparar con la exacta, como el MCL del notebook.
  - Consultas del documento y pregunta 6 (lluvia vs. hora punta).
  - verificar_con_pgmpy(): comprobacion opcional con la libreria pgmpy.
"""

import math
import random
import warnings
from itertools import product

try:
    from .red import construir_red, prob_conjunta, ESTADOS
except ImportError:
    from red import construir_red, prob_conjunta, ESTADOS


def consultar(variable, evidencia=None, red=None):
    """P(variable | evidencia) por enumeracion exacta.

    evidencia: diccionario, p. ej. {"Hora": "punta", "Clima": "lluvia"}
    Devuelve un diccionario {estado: probabilidad}.
    """
    red = red or construir_red()
    evidencia = evidencia or {}
    ocultas = [v for v in red["orden"] if v not in evidencia]
    acumulado = {e: 0.0 for e in red["estados"][variable]}

    for valores in product(*[red["estados"][v] for v in ocultas]):
        asignacion = dict(evidencia)
        asignacion.update(zip(ocultas, valores))
        acumulado[asignacion[variable]] += prob_conjunta(red, asignacion)

    total = sum(acumulado.values())  # = P(evidencia)
    if total == 0:
        raise ValueError("La evidencia es imposible segun el modelo.")
    return {e: p / total for e, p in acumulado.items()}


def entropia(dist):
    """Entropia de Shannon en bits. 0 = certeza; log2(n) = maxima duda."""
    return -sum(p * math.log2(p) for p in dist.values() if p > 0)


# ---------------------------------------------------------------------------
# Monte Carlo: aproximar la misma consulta con muestras
# ---------------------------------------------------------------------------
def muestrear(red, rng):
    """Una muestra de toda la red (muestreo hacia adelante): se sortea cada
    variable en orden topologico, usando los valores ya sorteados de sus
    padres."""
    muestra = {}
    for var in red["orden"]:
        combo = tuple(muestra[p] for p in red["padres"][var])
        muestra[var] = rng.choices(red["estados"][var],
                                   weights=red["tablas"][var][combo])[0]
    return muestra


def monte_carlo(variable, evidencia=None, N=20000, semilla=42, red=None):
    """P(variable | evidencia) por muestreo con rechazo: genero N muestras,
    me quedo con las que coinciden con la evidencia y cuento frecuencias."""
    red = red or construir_red()
    evidencia = evidencia or {}
    rng = random.Random(semilla)
    conteo = {e: 0 for e in red["estados"][variable]}
    aceptadas = 0
    for _ in range(N):
        m = muestrear(red, rng)
        if all(m[k] == v for k, v in evidencia.items()):
            conteo[m[variable]] += 1
            aceptadas += 1
    if aceptadas == 0:
        raise ValueError("Ninguna muestra cumple la evidencia; aumentar N.")
    return {e: c / aceptadas for e, c in conteo.items()}, aceptadas


def distancia_tv(p, q):
    """Distancia de variacion total: 0 = distribuciones iguales."""
    return sum(abs(p[k] - q[k]) for k in p) / 2


# ---------------------------------------------------------------------------
# Consultas del proyecto
# ---------------------------------------------------------------------------
def _fmt(dist):
    return "  ".join(f"{k}={v:.3f}" for k, v in dist.items())


def consulta_documento(red=None):
    """Pregunta del documento: probabilidad de escasez un viernes a las
    19:00, con lluvia y un evento masivo en el centro.
    Viernes 19:00 = hora punta (el dia de la semana no es una variable de
    esta red; ver README, posibles extensiones)."""
    evid = {"Hora": "punta", "Clima": "lluvia", "Evento": "si"}
    return evid, consultar("Escasez", evid, red)


def escasez_por_contexto(red=None):
    """P(Escasez=si) y entropia para las 8 combinaciones de Hora, Clima y
    Evento. Es la tabla que usa la Persona 4 para decidir tarifas."""
    filas = []
    for h, c, e in product(ESTADOS["Hora"], ESTADOS["Clima"], ESTADOS["Evento"]):
        evid = {"Hora": h, "Clima": c, "Evento": e}
        dist = consultar("Escasez", evid, red)
        filas.append((evid, dist["si"], entropia(dist)))
    return filas


def pregunta6(red=None):
    """Pregunta 6: como distinguir el efecto de la lluvia del de la hora
    punta sobre la demanda.

    Idea: en la red, Hora y Clima son padres DISTINTOS de Demanda, asi que
    se puede fijar uno y mover el otro (comparacion ceteris paribus).
    Como Hora y Clima no tienen causas comunes en la red, condicionar
    equivale a intervenir: P(D | do(lluvia)) = P(D | lluvia).

    Devuelve P(Demanda=alta) en las 4 combinaciones y los efectos.
    """
    p = {}
    for h, c in product(ESTADOS["Hora"], ESTADOS["Clima"]):
        p[(h, c)] = consultar("Demanda", {"Hora": h, "Clima": c}, red)["alta"]
    efectos = {
        "lluvia (en valle)": p[("valle", "lluvia")] - p[("valle", "seco")],
        "lluvia (en punta)": p[("punta", "lluvia")] - p[("punta", "seco")],
        "punta (con seco)":  p[("punta", "seco")] - p[("valle", "seco")],
        "punta (con lluvia)": p[("punta", "lluvia")] - p[("valle", "lluvia")],
    }
    # Interaccion: cuanto cambia el efecto de la lluvia segun la hora.
    # Si es 0, los efectos simplemente se suman.
    efectos["interaccion"] = efectos["lluvia (en punta)"] - efectos["lluvia (en valle)"]
    return p, efectos


def explicacion_alternativa(red=None):
    """'Explaining away': si observo demanda alta, la lluvia y la hora punta
    compiten como explicaciones. Saber que llueve baja la probabilidad de
    que sea hora punta. Muestra por que con DATOS hay que registrar las dos
    variables: si solo se ve la demanda, los efectos se confunden."""
    a = consultar("Hora", {"Demanda": "alta"}, red)["punta"]
    b = consultar("Hora", {"Demanda": "alta", "Clima": "lluvia"}, red)["punta"]
    c = consultar("Hora", {"Demanda": "alta", "Clima": "seco"}, red)["punta"]
    return a, b, c


def verificar_con_pgmpy(red=None):
    """Comprobacion opcional: arma la misma red en pgmpy y compara la
    consulta del documento. Requiere: pip install pgmpy"""
    warnings.filterwarnings("ignore", category=FutureWarning)
    try:
        try:
            from pgmpy.models import DiscreteBayesianNetwork as Modelo
        except ImportError:
            from pgmpy.models import BayesianNetwork as Modelo
        from pgmpy.factors.discrete import TabularCPD
        from pgmpy.inference import VariableElimination
    except ImportError:
        return None

    red = red or construir_red()
    aristas = [(p, v) for v in red["orden"] for p in red["padres"][v]]
    modelo = Modelo(aristas)
    for v in red["orden"]:
        padres = red["padres"][v]
        combos = list(product(*[red["estados"][p] for p in padres]))
        # pgmpy: una fila por estado, una columna por combinacion de padres
        valores = [[red["tablas"][v][c][i] for c in combos]
                   for i in range(len(red["estados"][v]))]
        modelo.add_cpds(TabularCPD(
            v, len(red["estados"][v]), valores,
            evidence=padres or None,
            evidence_card=[len(red["estados"][p]) for p in padres] or None,
            state_names={x: red["estados"][x] for x in [v] + padres}))
    assert modelo.check_model()
    evid, nuestra = consulta_documento(red)
    q = VariableElimination(modelo).query(["Escasez"], evidence=evid, show_progress=False)
    p_pgmpy = q.values[q.state_names["Escasez"].index("si")]
    return nuestra["si"], float(p_pgmpy)


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    red = construir_red()

    print("=" * 72)
    print("1. Probabilidades a priori (sin evidencia)")
    print("=" * 72)
    for v in ["Trafico", "Demanda", "Oferta", "Escasez"]:
        d = consultar(v, red=red)
        print(f"  P({v}): {_fmt(d)}   H={entropia(d):.3f} bits")

    print("\n" + "=" * 72)
    print("2. Consulta del documento: viernes 19:00, lluvia y evento masivo")
    print("=" * 72)
    evid, d = consulta_documento(red)
    print(f"  Evidencia: {evid}")
    print(f"  P(Escasez): {_fmt(d)}   H={entropia(d):.3f} bits")
    print(f"  P(Demanda): {_fmt(consultar('Demanda', evid, red))}")
    print(f"  P(Oferta):  {_fmt(consultar('Oferta', evid, red))}")

    print("\n" + "=" * 72)
    print("3. Probabilidad de escasez en cada contexto")
    print("=" * 72)
    print(f"  {'Hora':<7}{'Clima':<8}{'Evento':<8}{'P(escasez)':>11}{'H (bits)':>10}")
    for evid, p_si, h in escasez_por_contexto(red):
        print(f"  {evid['Hora']:<7}{evid['Clima']:<8}{evid['Evento']:<8}{p_si:>11.3f}{h:>10.3f}")

    print("\n" + "=" * 72)
    print("4. Pregunta 6: efecto de la lluvia vs. efecto de la hora punta")
    print("=" * 72)
    p, ef = pregunta6(red)
    for (h, c), v in p.items():
        print(f"  P(Demanda=alta | {h}, {c}) = {v:.3f}")
    for k, v in ef.items():
        print(f"  efecto {k:<20} {v:+.3f}")
    a, b, c = explicacion_alternativa(red)
    print("  Explicacion alternativa (explaining away):")
    print(f"    P(punta | demanda alta)          = {a:.3f}")
    print(f"    P(punta | demanda alta, lluvia)  = {b:.3f}  <- la lluvia ya explica parte")
    print(f"    P(punta | demanda alta, seco)    = {c:.3f}")

    print("\n" + "=" * 72)
    print("5. Exacto vs. Monte Carlo (consulta del documento)")
    print("=" * 72)
    evid, exacta = consulta_documento(red)
    for N in [1000, 10000, 100000]:
        aprox, acept = monte_carlo("Escasez", evid, N=N, red=red)
        print(f"  N={N:<7} aceptadas={acept:<6} P(si)={aprox['si']:.3f}  "
              f"exacta={exacta['si']:.3f}  distancia={distancia_tv(exacta, aprox):.3f}")
    print("  (Pocas muestras cumplen la evidencia: solo ~0.4 % de los")
    print("   intervalos son punta + lluvia + evento. Por eso el rechazo")
    print("   desperdicia muestras y conviene la enumeracion exacta.)")

    print("\n" + "=" * 72)
    print("6. Verificacion con pgmpy")
    print("=" * 72)
    r = verificar_con_pgmpy(red)
    if r is None:
        print("  pgmpy no esta instalado (opcional: pip install pgmpy)")
    else:
        print(f"  nuestra={r[0]:.6f}  pgmpy={r[1]:.6f}  "
              f"{'COINCIDEN' if math.isclose(*r, abs_tol=1e-9) else 'DIFIEREN'}")
