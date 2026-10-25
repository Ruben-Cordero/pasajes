"""
decision.py - Regla de decision de tarifa (pregunta 7)
Persona 4 (escenarios, datos, decision e integracion)

Entradas por intervalo:
  - P(escasez) de la red bayesiana (Persona 2) para el contexto,
  - precio estimado por Kalman (Persona 3) con su desviacion,
  - umbrales X (probabilidad) e Y (precio, Bs).

Regla:
  si P(escasez) > X y li > Y   -> INCENTIVAR (pagar bono a conductores)
  si P(escasez) > X y li <= Y  -> SUBIR (recargo al pasajero)
  si no                        -> MANTENER
donde li = precio estimado - z * desviacion es el limite inferior del
intervalo de credibilidad (z = 2, ~95 %). Se usa el limite inferior para
que "el precio ya supera Y" sea una afirmacion con 97.5 % de confianza:
solo se renuncia a subir el precio cuando estamos seguros de que ya es alto.

Evaluacion (barrido de X e Y sobre los escenarios B, C y E): cada accion se
traduce en un cambio de D0/S0 y se re-simula con simular() (Persona 1):
  SUBIR       recargo d al pasajero: D0 - beta*d (menos pasajeros) y
              S0 + gamma*d (el conductor cobra mas)
  INCENTIVAR  bono b al conductor: S0 + gamma*b, la demanda no cambia
Es una evaluacion en lazo abierto (las decisiones se toman sobre la
trayectoria sin intervenir); ver limitaciones en resultados/pregunta7.md.

Uso (desde la raiz):  python -m integracion.decision
"""

import os

import numpy as np
import pandas as pd

from integracion import comun
from integracion import params as P
from capa1_euler import modelo_euler as me
from capa3_kalman import filtro_kalman as fk
from integracion import escenario_e

ACCIONES = ("MANTENER", "SUBIR", "INCENTIVAR")
X_GRID = np.round(np.arange(0.05, 0.951, 0.05), 2)
Y_GRID = np.arange(8.0, 22.01, 1.0)

# Contexto (evidencia de la red) dentro y fuera de la ventana de B y C.
# B y C se definen en el documento por su efecto (demanda alta, oferta
# baja), asi que esa es la evidencia que se le da a la red.
EVIDENCIA_ESC = {
    "B": {"fuera": {"Hora": "valle", "Clima": "seco"},
          "ventana": {"Hora": "punta", "Demanda": "alta"}},
    "C": {"fuera": {"Hora": "valle", "Clima": "seco"},
          "ventana": {"Hora": "valle", "Clima": "lluvia", "Oferta": "baja"}},
}


# ---------------------------------------------------------------------------
# Regla
# ---------------------------------------------------------------------------
def decidir(p_escasez, precio_estimado, desviacion, X=P.UMBRAL_X, Y=P.UMBRAL_Y,
            z=P.NIVEL_CONFIANZA_Z):
    """Decision para un intervalo. Acepta escalares o arreglos."""
    p_escasez = np.asarray(p_escasez, float)
    li = np.asarray(precio_estimado, float) - z * np.asarray(desviacion, float)
    accion = np.where(p_escasez > X, np.where(li > Y, "INCENTIVAR", "SUBIR"), "MANTENER")
    return accion if accion.ndim else str(accion)


def decidir_secuencia(p_escasez, precio_estimado, desviacion, X=P.UMBRAL_X, Y=P.UMBRAL_Y,
                      z=P.NIVEL_CONFIANZA_Z, permanencia=P.PERMANENCIA_MIN):
    """Decision intervalo a intervalo con permanencia minima: una accion se
    mantiene al menos `permanencia` intervalos antes de cambiar. Evita el
    'parpadeo' entre acciones cuando el precio estimado ronda Y, que con la
    dinamica oscilante del modelo (r = -0.75) genera transitorios."""
    cruda = decidir(p_escasez, precio_estimado, desviacion, X, Y, z)
    final = cruda.copy()
    actual, desde = cruda[0], 0
    for k in range(1, len(cruda)):
        if cruda[k] != actual and k - desde >= permanencia:
            actual, desde = cruda[k], k
        final[k] = actual
    return final


def explicar(p_escasez, precio_estimado, desviacion, X=P.UMBRAL_X, Y=P.UMBRAL_Y,
             z=P.NIVEL_CONFIANZA_Z):
    accion = decidir(p_escasez, precio_estimado, desviacion, X, Y, z)
    li, ls = precio_estimado - z * desviacion, precio_estimado + z * desviacion
    if accion == "MANTENER":
        motivo = f"P(escasez) = {p_escasez:.2f} <= X = {X:.2f}"
    elif accion == "SUBIR":
        motivo = (f"P(escasez) = {p_escasez:.2f} > X = {X:.2f} y el precio no supera Y = {Y:.1f} "
                  f"con seguridad (limite inferior {li:.2f} <= {Y:.1f})")
    else:
        motivo = (f"P(escasez) = {p_escasez:.2f} > X = {X:.2f} y el precio ya supera Y = {Y:.1f} "
                  f"(limite inferior {li:.2f} > {Y:.1f}): subirlo mas expulsaria pasajeros")
    return {"accion": accion, "motivo": motivo, "precio_li": li, "precio_ls": ls}


# ---------------------------------------------------------------------------
# Insumos de cada escenario: P(escasez), Kalman y D0/S0 de base
# ---------------------------------------------------------------------------
def insumos_BC(clave, red):
    kd = P.KALMAN_D
    esc = P.ESCENARIOS[clave]
    caso = fk.ejecutar_caso_completo(
        semilla=P.SEMILLA, solo_precio=False, D0=esc["D0"], S0=esc["S0"], parametros=P.PARAMS,
        desviacion_choque_demanda=kd["desviacion_choque_demanda"],
        desviacion_medicion_precio=kd["desviacion_medicion_precio"],
        desviacion_medicion_demanda=kd["desviacion_medicion_demanda"])
    sim, res = caso["simulacion"], caso["resultado"]
    pe = {k: comun.consultar("Escasez", ev, red)["si"] for k, ev in EVIDENCIA_ESC[clave].items()}
    en_v = np.array([P.en_ventana(k) for k in range(len(sim["t"]))])
    return {"tramos": [{
        "p_escasez": np.where(en_v, pe["ventana"], pe["fuera"]),
        "precio": res["estimaciones"][:, 0], "sd": res["desviaciones"][:, 0],
        "D0": sim["D0"].copy(), "S0": sim["S0"].copy(), "p0": P.PARAMS["p0"],
        "estres": en_v}], "p_escasez_contextos": pe}


def insumos_E(red_cal):
    df = escenario_e.cargar()
    est = pd.read_csv(os.path.join(P.TABLAS, "E_estimaciones_kalman.csv"))
    est = est[est["mediciones"] == "precio_y_solicitudes"].set_index("timestamp")
    pe_cache = {}
    tramos = []
    for _, dia in df.groupby("fecha"):
        pe = []
        for _, f in dia.iterrows():
            ev = tuple(sorted(comun.evidencia_fila(f).items()))
            if ev not in pe_cache:
                pe_cache[ev] = comun.consultar("Escasez", dict(ev), red_cal)["si"]
            pe.append(pe_cache[ev])
        e = est.loc[dia["timestamp"]]
        # Reproduccion del dia con el modelo: D0/S0 = demanda y oferta a precio
        # de referencia, suavizadas (media movil de 15 min) para quitar ruido.
        D0 = dia["D0_hat"].rolling(3, center=True, min_periods=1).mean().values
        S0 = dia["S0_hat"].rolling(3, center=True, min_periods=1).mean().values
        tramos.append({"p_escasez": np.array(pe), "precio": e["precio_estimado"].values,
                       "sd": ((e["precio_ls"] - e["precio_li"]) / (2 * P.NIVEL_CONFIANZA_Z)).values,
                       "D0": D0, "S0": S0, "p0": float(dia["precio_bs"].iloc[0]),
                       "estres": dia["tarifa_alta"].values.astype(bool)})
    return {"tramos": tramos}


# ---------------------------------------------------------------------------
# Evaluacion de una politica (X, Y) re-simulando con simular()
# ---------------------------------------------------------------------------
def _simular_tramo(tr, accion):
    d, b = P.RECARGO_SUBIR, P.BONO_INCENTIVO
    sube, inc = accion == "SUBIR", accion == "INCENTIVAR"
    D0 = tr["D0"] - P.PARAMS["beta"] * d * sube
    S0 = tr["S0"] + P.PARAMS["gamma"] * (d * sube + b * inc)
    par = dict(P.PARAMS, T=len(D0) * P.PARAMS["dt"], p0=tr["p0"])
    return me.simular(par, D0=D0, S0=S0)


def evaluar(insumos, X, Y, permanencia=P.PERMANENCIA_MIN):
    tot = {a: 0 for a in ACCIONES}
    serv = dem = insat = costo = pago = n = 0.0
    serv0 = dem0 = insat0 = 0.0
    acierto = falsa = estres_n = calma_n = cambios = 0
    for tr in insumos["tramos"]:
        acc = decidir_secuencia(tr["p_escasez"], tr["precio"], tr["sd"], X, Y,
                                permanencia=permanencia)
        cambios += int((acc[1:] != acc[:-1]).sum())
        base = _simular_tramo(tr, np.full(len(acc), "MANTENER"))
        sim = _simular_tramo(tr, acc)
        for a in ACCIONES:
            tot[a] += int((acc == a).sum())
        actua = acc != "MANTENER"
        acierto += int((actua & tr["estres"]).sum())
        falsa += int((actua & ~tr["estres"]).sum())
        estres_n += int(tr["estres"].sum())
        calma_n += int((~tr["estres"]).sum())
        serv += sim["servicios"].sum()
        dem += sim["D"].sum()
        insat += np.maximum(sim["D"] - sim["S"], 0).sum()
        costo += (P.BONO_INCENTIVO * sim["servicios"] * (acc == "INCENTIVAR")).sum()
        pago += ((sim["p"] + P.RECARGO_SUBIR * (acc == "SUBIR")) * sim["servicios"]).sum()
        serv0 += base["servicios"].sum()
        dem0 += base["D"].sum()
        insat0 += np.maximum(base["D"] - base["S"], 0).sum()
        n += len(acc)
    return {"X": X, "Y": Y, "permanencia": permanencia, "cambios_de_accion": cambios,
            "frac_MANTENER": tot["MANTENER"] / n, "frac_SUBIR": tot["SUBIR"] / n,
            "frac_INCENTIVAR": tot["INCENTIVAR"] / n,
            "tasa_deteccion": acierto / estres_n if estres_n else np.nan,
            "tasa_falsa_alarma": falsa / calma_n if calma_n else np.nan,
            "servicios": serv, "delta_servicios_pct": 100 * (serv / serv0 - 1),
            "pasajeros_expulsados": dem0 - dem,
            "demanda_insatisfecha": insat, "demanda_insatisfecha_base": insat0,
            "costo_incentivos_bs": costo,
            "precio_medio_pagado": pago / serv}


def barrido(insumos_por_esc):
    filas = []
    for esc, ins in insumos_por_esc.items():
        for X in X_GRID:
            for Y in Y_GRID:
                fila = evaluar(ins, float(X), float(Y))
                fila["escenario"] = esc
                filas.append(fila)
    return pd.DataFrame(filas)


# ---------------------------------------------------------------------------
# Eleccion de X e Y
# ---------------------------------------------------------------------------
def elegir_X(tabla):
    """X maximiza el indice de Youden (deteccion - falsa alarma) promediado en
    B, C y E. Las acciones dependen de X pero la deteccion no depende de Y."""
    t = tabla[tabla["Y"] == tabla["Y"].min()].copy()
    t["youden"] = t["tasa_deteccion"] - t["tasa_falsa_alarma"]
    prom = t.groupby("X")["youden"].mean()
    mejores = prom[prom >= prom.max() - 1e-9].index
    # Si hay meseta, se toma su punto medio (mas margen a ambos lados).
    return float(np.median(mejores)), prom


def elegir_Y(tabla, X):
    """Y: bajar Y significa incentivar en mas intervalos (y subir en menos).
    Para cada Y se mide, sumando B, C y E y contra la politica de Y maximo
    (casi nunca incentivar), cuantos pasajeros deja de expulsar la regla y
    cuanto cuesta en bonos. Se elige el Y donde el paso Y+1 -> Y tiene el
    menor costo marginal por pasajero retenido: es donde cada boliviano de
    bono rinde mas."""
    t = tabla[np.isclose(tabla["X"], X)]
    ref = t[np.isclose(t["Y"], Y_GRID.max())]
    filas = []
    for Y in Y_GRID:
        r = t[np.isclose(t["Y"], Y)]
        filas.append({"Y": Y,
                      "pasajeros_no_expulsados": ref["pasajeros_expulsados"].sum()
                      - r["pasajeros_expulsados"].sum(),
                      "servicios_adicionales": r["servicios"].sum() - ref["servicios"].sum(),
                      "costo_incentivos_bs": r["costo_incentivos_bs"].sum(),
                      "frac_INCENTIVAR": r["frac_INCENTIVAR"].mean(),
                      "frac_SUBIR": r["frac_SUBIR"].mean()})
    curva = pd.DataFrame(filas).sort_values("Y").reset_index(drop=True)
    d_costo = curva["costo_incentivos_bs"].diff(-1)          # costo(Y) - costo(Y+1)
    d_ret = curva["pasajeros_no_expulsados"].diff(-1)
    curva["costo_marginal_por_pasajero"] = np.where(d_ret > 1e-9, d_costo / d_ret, np.nan)
    Y = float(curva.loc[curva["costo_marginal_por_pasajero"].idxmin(), "Y"])
    return Y, curva


def figura_barrido(tabla, prom_youden, curva_Y, X, Y):
    fig, ejes = comun.plt.subplots(1, 3, figsize=(16, 4.5))
    ax = ejes[0]
    t = tabla[tabla["Y"] == tabla["Y"].min()]
    for esc in t["escenario"].unique():
        s = t[t["escenario"] == esc]
        ax.plot(s["X"], s["tasa_deteccion"] - s["tasa_falsa_alarma"], "o-", ms=3,
                color=comun.COLORES[esc], label=f"Escenario {esc}")
    ax.plot(prom_youden.index, prom_youden.values, "k--", label="Promedio")
    ax.axvline(X, color="k", ls=":", lw=1)
    ax.set_xlabel("X (umbral de P(escasez))")
    ax.set_ylabel("Deteccion - falsa alarma")
    ax.set_title(f"Eleccion de X = {X:.2f}")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)

    ax = ejes[1]
    t = tabla[np.isclose(tabla["X"], X)]
    for esc in t["escenario"].unique():
        s = t[t["escenario"] == esc]
        ax.plot(s["Y"], s["frac_INCENTIVAR"], "-", color=comun.COLORES[esc], label=f"{esc}: INCENTIVAR")
        ax.plot(s["Y"], s["frac_SUBIR"], "--", color=comun.COLORES[esc], label=f"{esc}: SUBIR")
    ax.axvline(Y, color="k", ls=":", lw=1)
    ax.set_xlabel("Y (Bs)")
    ax.set_ylabel("Fraccion de intervalos")
    ax.set_title(f"Activacion de cada accion (X = {X:.2f})")
    ax.legend(fontsize=7, ncol=2)
    ax.grid(alpha=0.3)

    ax = ejes[2]
    ax.plot(curva_Y["Y"], curva_Y["costo_marginal_por_pasajero"], "o-", color="k", ms=3,
            label="Costo marginal (Bs por pasajero retenido)")
    ax.axvline(Y, color="k", ls=":", lw=1)
    ax2 = ax.twinx()
    ax2.plot(curva_Y["Y"], curva_Y["pasajeros_no_expulsados"], "s-", color=comun.COLORES["E"],
             ms=3, label="Pasajeros no expulsados")
    ax2.set_ylabel("Pasajeros no expulsados (B+C+E)", color=comun.COLORES["E"])
    ax.set_xlabel("Y (Bs)")
    ax.set_ylabel("Bs de bono por pasajero retenido")
    ax.set_title(f"Eleccion de Y = {Y:.0f} Bs")
    ax.legend(fontsize=8, loc="upper right")
    ax.grid(alpha=0.3)
    fig.suptitle("Barrido de umbrales de la regla de decision (E = datos sinteticos)")
    return comun.guardar_figura(fig, "decision_barrido.png")


def insumos_todos():
    red_exp = comun.construir_red()
    red_cal = escenario_e.red_calibrada()
    ins = {"B": insumos_BC("B", red_exp), "C": insumos_BC("C", red_exp), "E": insumos_E(red_cal)}
    return ins


def main():
    ins = insumos_todos()
    for esc in "BC":
        print(f"P(escasez) escenario {esc}: {ins[esc]['p_escasez_contextos']}")
    tabla = barrido(ins)
    comun.guardar_tabla(tabla.round(4), "decision_barrido.csv", index=False)
    X, prom = elegir_X(tabla)
    Y, curva = elegir_Y(tabla, X)
    comun.guardar_tabla(prom.round(4).rename("youden_promedio").to_frame(), "decision_eleccion_X.csv")
    comun.guardar_tabla(curva.round(4), "decision_eleccion_Y.csv", index=False)
    figura_barrido(tabla, prom, curva, X, Y)

    elegido = tabla[np.isclose(tabla["X"], X) & np.isclose(tabla["Y"], Y)]
    comun.guardar_tabla(elegido.round(4), "decision_resultado_elegido.csv", index=False)

    # Efecto de la permanencia minima (anti-parpadeo) con X e Y elegidos
    perm = pd.DataFrame([dict(evaluar(ins[esc], X, Y, m), escenario=esc)
                         for m in (1, 3, 6, 12) for esc in ins])
    comun.guardar_tabla(perm.round(4), "decision_permanencia.csv", index=False)
    print("\nPermanencia minima (intervalos) vs resultados:")
    print(perm[["permanencia", "escenario", "cambios_de_accion", "delta_servicios_pct",
                "demanda_insatisfecha", "demanda_insatisfecha_base",
                "costo_incentivos_bs"]].round(2).to_string(index=False))
    print(f"\nYouden promedio por X:\n{prom.round(3).to_string()}")
    print(f"\nCurva de Y (X = {X:.2f}):\n{curva.round(3).to_string(index=False)}")
    print(f"\nX elegido = {X:.2f}   Y elegido = {Y:.1f} Bs")
    cols = ["escenario", "frac_MANTENER", "frac_SUBIR", "frac_INCENTIVAR", "tasa_deteccion",
            "tasa_falsa_alarma", "delta_servicios_pct", "pasajeros_expulsados",
            "demanda_insatisfecha", "demanda_insatisfecha_base", "costo_incentivos_bs",
            "precio_medio_pagado"]
    print(elegido[cols].round(3).to_string(index=False))
    if not (np.isclose(X, P.UMBRAL_X) and np.isclose(Y, P.UMBRAL_Y)):
        print(f"\nAVISO: params.py tiene X = {P.UMBRAL_X}, Y = {P.UMBRAL_Y}; "
              "actualizarlo con los valores elegidos.")


if __name__ == "__main__":
    main()
