"""
escenario_e.py - Escenario E: datos de Cochabamba (SINTETICOS) y calibracion
Persona 4 (escenarios, datos, decision e integracion)

IMPORTANTE: datos/procesado/escenario_e.csv contiene datos SINTETICOS,
generados con el propio modelo de Euler (ver datos/README.md). Todo lo que
sale de este script valida el funcionamiento del sistema, no su capacidad
predictiva en el mercado real.

Que hace:
  1. Frecuencias de tarifa_alta y escasez por contexto.
  2. Identificabilidad: una regresion ingenua NO recupera alpha, beta,
     gamma (pendientes atenuadas). Se usan los valores nominales.
  2b. Pregunta 6: efecto de la lluvia vs la hora punta sobre la demanda,
     diferencia ingenua frente a regresion multiple (E_efectos_contexto.csv).
  3. Calibracion de la red bayesiana: cortes de discretizar(), valores de
     VALORES_D0 / VALORES_S0 y una red re-estimada con estimar_desde_datos()
     usando tarifa_alta como proxy de Escasez.
  4. Filtro de Kalman (Persona 3) sobre precio_bs y solicitudes: solo
     precio vs precio + solicitudes, con error de prediccion a un paso e
     innovaciones (no hay estado verdadero).

Uso (desde la raiz):  python -m integracion.escenario_e
"""

import numpy as np
import pandas as pd

from integracion import comun
from integracion import params as P
from capa1_euler import modelo_euler as me
from capa3_kalman import filtro_kalman as fk

AVISO = "datos sinteticos"
CONTEXTO = ["hora_punta", "lluvia", "evento", "trafico_alto"]


def cargar():
    df = pd.read_csv(P.DATOS_E)
    df["fecha"] = df["timestamp"].str[:10]
    b, g = P.PARAMS["beta"], P.PARAMS["gamma"]
    # Demanda y oferta "a precio de referencia": quitan el efecto del precio
    # con los beta y gamma nominales. Son estimaciones ruidosas de D0 y S0.
    df["D0_hat"] = df["solicitudes"] - b * (P.PARAMS["p_ref"] - df["precio_bs"])
    df["S0_hat"] = df["vehiculos"] - g * (df["precio_bs"] - P.PARAMS["p_costo"])
    return df


# ---------------------------------------------------------------------------
# 1. Frecuencias por contexto
# ---------------------------------------------------------------------------
def frecuencias(df):
    marg = []
    for col in CONTEXTO:
        for valor, g in df.groupby(col):
            marg.append({"variable": col, "valor": int(valor), "n": len(g),
                         "p_tarifa_alta": g["tarifa_alta"].mean(),
                         "p_escasez": g["escasez"].mean(),
                         "precio_medio": g["precio_bs"].mean()})
    marg = pd.DataFrame(marg)
    conj = (df.groupby(["hora_punta", "lluvia", "evento"])
              .agg(n=("precio_bs", "size"), precio_medio=("precio_bs", "mean"),
                   solicitudes_media=("solicitudes", "mean"),
                   vehiculos_media=("vehiculos", "mean"),
                   p_tarifa_alta=("tarifa_alta", "mean"),
                   p_escasez=("escasez", "mean"))
              .reset_index())
    comun.guardar_tabla(marg.round(4), "E_frecuencias_marginales.csv", index=False)
    comun.guardar_tabla(conj.round(4), "E_frecuencias_contexto.csv", index=False)
    return marg, conj


def figura_frecuencias(marg):
    fig, ax = comun.plt.subplots(figsize=(10, 4))
    etiquetas, x = [], np.arange(len(marg))
    for _, f in marg.iterrows():
        etiquetas.append(f"{f['variable']}={f['valor']}")
    ax.bar(x - 0.2, marg["p_tarifa_alta"], 0.4, label="P(tarifa_alta)", color=comun.COLORES["E"])
    ax.bar(x + 0.2, marg["p_escasez"], 0.4, label="P(escasez: D - S >= 5)", color="0.5")
    ax.set_xticks(x, etiquetas, rotation=30, ha="right")
    ax.set_ylabel("Frecuencia")
    ax.set_title(f"Escenario E ({AVISO}): tarifa alta y escasez por contexto")
    ax.legend()
    ax.grid(alpha=0.3, axis="y")
    return comun.guardar_figura(fig, "E_frecuencias_contexto.png")


# ---------------------------------------------------------------------------
# 2. Identificabilidad (pregunta 2 del documento)
# ---------------------------------------------------------------------------
def _pendiente(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    return float(np.polyfit(x, y, 1)[0])


def identificabilidad(df):
    dp, exceso = [], []
    for _, g in df.groupby("fecha"):
        dp.extend(np.diff(g["precio_bs"].values))
        exceso.extend((g["solicitudes"] - g["vehiculos"]).values[:-1])
    p = P.PARAMS
    tabla = pd.DataFrame([
        {"relacion": "Delta p_k vs (solicitudes - vehiculos)", "parametro": "dt*alpha",
         "valor_nominal": p["dt"] * p["alpha"], "pendiente_regresion": _pendiente(exceso, dp)},
        {"relacion": "solicitudes vs precio", "parametro": "-beta",
         "valor_nominal": -p["beta"],
         "pendiente_regresion": _pendiente(df["precio_bs"], df["solicitudes"])},
        {"relacion": "vehiculos vs precio", "parametro": "gamma",
         "valor_nominal": p["gamma"],
         "pendiente_regresion": _pendiente(df["precio_bs"], df["vehiculos"])},
    ])
    comun.guardar_tabla(tabla.round(3), "E_identificabilidad.csv", index=False)
    return tabla


# ---------------------------------------------------------------------------
# 2b. Pregunta 6: separar el efecto de la lluvia del de la hora punta
# ---------------------------------------------------------------------------
# Efectos sobre D0 con que se generaron los datos (datos/README.md, sec. 4.2).
# Solo sirven para comprobar el metodo; con datos reales no se conocen.
EFECTOS_GENERADOR = {"hora_punta": 12.0, "lluvia": 10.0, "evento": 10.0, "trafico_alto": 3.0,
                     "sabado": -2.0, "domingo": -6.0}


def _mco(y, columnas):
    """Minimos cuadrados con intercepto; devuelve coeficientes y errores estandar."""
    X = np.column_stack([np.ones(len(y))] + [np.asarray(c, float) for c in columnas])
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ b
    s2 = resid @ resid / (len(y) - X.shape[1])
    ee = np.sqrt(np.diag(s2 * np.linalg.inv(X.T @ X)))
    return b[1:], ee[1:]


def efectos_contexto(df):
    """Efecto de cada factor sobre la demanda a precio de referencia (D0_hat).
    La diferencia de medias ingenua mezcla factores que ocurren juntos (en los
    datos casi toda la lluvia cae en hora punta y el viernes coincide con el
    evento); la regresion multiple compara intervalos que solo difieren en un
    factor, que es la comparacion ceteris paribus de la red bayesiana."""
    y = df["D0_hat"].values.astype(float)
    factores = {"hora_punta": df["hora_punta"], "lluvia": df["lluvia"], "evento": df["evento"],
                "trafico_alto": df["trafico_alto"], "sabado": df["dia_semana"] == 5,
                "domingo": df["dia_semana"] == 6}
    dos, _ = _mco(y, [factores["hora_punta"], factores["lluvia"]])
    todos, ee = _mco(y, list(factores.values()))
    filas = []
    for i, (nombre, x) in enumerate(factores.items()):
        x = np.asarray(x, bool)
        filas.append({"factor": nombre, "n_intervalos": int(x.sum()),
                      "diferencia_ingenua": y[x].mean() - y[~x].mean(),
                      "regresion_hora_y_lluvia": dos[i] if i < 2 else np.nan,
                      "regresion_completa": todos[i], "error_estandar": ee[i],
                      "valor_generador": EFECTOS_GENERADOR[nombre]})
    tabla = pd.DataFrame(filas)
    comun.guardar_tabla(tabla.round(3), "E_efectos_contexto.csv", index=False)
    return tabla


# ---------------------------------------------------------------------------
# 3. Calibracion de la red bayesiana
# ---------------------------------------------------------------------------
def terciles(serie):
    return tuple(float(v) for v in serie.quantile([1 / 3, 2 / 3]).round(1))


def calibracion(df):
    cortes_crudos = {"solicitudes": terciles(df["solicitudes"]),
                     "vehiculos": terciles(df["vehiculos"])}
    cortes = {"D0_hat": terciles(df["D0_hat"]), "S0_hat": terciles(df["S0_hat"])}
    df["Demanda"] = [comun.discretizar(v, cortes["D0_hat"]) for v in df["D0_hat"]]
    df["Oferta"] = [comun.discretizar(v, cortes["S0_hat"]) for v in df["S0_hat"]]
    valores_D0 = df.groupby("Demanda")["D0_hat"].mean().round(0).to_dict()
    valores_S0 = df.groupby("Oferta")["S0_hat"].mean().round(0).to_dict()

    # Comparacion: discretizar las cuentas crudas casi no separa contextos
    df["Demanda_cruda"] = [comun.discretizar(v, cortes_crudos["solicitudes"])
                           for v in df["solicitudes"]]
    separacion = pd.DataFrame({
        "P(Demanda=alta) con D0_hat": df.groupby("hora_punta")["Demanda"].apply(
            lambda s: (s == "alta").mean()),
        "P(Demanda=alta) con solicitudes crudas": df.groupby("hora_punta")[
            "Demanda_cruda"].apply(lambda s: (s == "alta").mean()),
    })
    separacion.index = ["valle", "punta"]
    separacion.index.name = "Hora"

    filas = []
    for tipo, var, corte in [("crudo", "solicitudes", cortes_crudos["solicitudes"]),
                             ("crudo", "vehiculos", cortes_crudos["vehiculos"]),
                             ("propuesto", "D0_hat", cortes["D0_hat"]),
                             ("propuesto", "S0_hat", cortes["S0_hat"])]:
        filas.append({"tipo": tipo, "variable": var, "corte_1": corte[0], "corte_2": corte[1]})
    for estado in ["baja", "media", "alta"]:
        filas.append({"tipo": "VALORES_D0", "variable": estado,
                      "valor_calibrado": valores_D0[estado],
                      "valor_anterior": comun.traduccion.VALORES_D0[estado]})
        filas.append({"tipo": "VALORES_S0", "variable": estado,
                      "valor_calibrado": valores_S0[estado],
                      "valor_anterior": comun.traduccion.VALORES_S0[estado]})
    comun.guardar_tabla(pd.DataFrame(filas), "E_calibracion_traduccion.csv", index=False)
    comun.guardar_tabla(separacion.round(3), "E_separacion_discretizacion.csv")
    return cortes, cortes_crudos, valores_D0, valores_S0, separacion


def filas_para_red(df):
    """Filas en el formato de red.estimar_desde_datos(). Costos no se
    observa en los datos: se asume 'normal' (solo aprende esas columnas;
    las de costos altos quedan con el supuesto experto). Escasez usa
    tarifa_alta como proxy (ver datos/README.md, seccion 6)."""
    return [{"Hora": "punta" if f.hora_punta else "valle",
             "Clima": "lluvia" if f.lluvia else "seco",
             "Evento": "si" if f.evento else "no",
             "Costos": "normal",
             "Trafico": "alto" if f.trafico_alto else "bajo",
             "Demanda": f.Demanda, "Oferta": f.Oferta,
             "Escasez": "si" if f.tarifa_alta else "no"}
            for f in df.itertuples()]


def red_calibrada(df=None):
    """Red re-estimada con los datos sinteticos (la usan main.py y decision.py)."""
    if df is None:
        df = cargar()
        calibracion(df)
    return comun.estimar_desde_datos(filas_para_red(df))


def comparar_redes(df, red_cal):
    red_exp = comun.construir_red()
    filas = []
    for (h, l, e), g in df.groupby(["hora_punta", "lluvia", "evento"]):
        ev = comun.evidencia("punta" if h else "valle", "lluvia" if l else "seco",
                             "si" if e else "no")
        filas.append({"hora_punta": h, "lluvia": l, "evento": e, "n": len(g),
                      "P_escasez_red_experta": comun.consultar("Escasez", ev, red_exp)["si"],
                      "P_escasez_red_calibrada": comun.consultar("Escasez", ev, red_cal)["si"],
                      "freq_tarifa_alta": g["tarifa_alta"].mean(),
                      "freq_escasez_DS": g["escasez"].mean()})
    tabla = pd.DataFrame(filas)
    comun.guardar_tabla(tabla.round(3), "E_red_experta_vs_calibrada.csv", index=False)
    return tabla


# ---------------------------------------------------------------------------
# 4. Kalman sobre los datos (sin estado verdadero)
# ---------------------------------------------------------------------------
def entradas_contexto(dia, red=None):
    """D0_k y S0_k de cada intervalo segun su contexto (traduccion.py)."""
    D0, S0 = [], []
    for _, f in dia.iterrows():
        r = comun.traduccion.contexto_a_parametros(comun.evidencia_fila(f), red=red)
        D0.append(r["D0"])
        S0.append(r["S0"])
    return np.array(D0), np.array(S0)


def kalman_dia(dia, solo_precio, D0, S0, factor_q=1.0):
    """Corre ejecutar_filtro_kalman() (Persona 3) sobre un dia de datos y
    reconstruye la prediccion a un paso y las innovaciones."""
    ke = P.KALMAN_E
    n = len(dia)
    if solo_precio:
        H = np.array([[1.0, 0.0]])
        R = np.diag([ke["var_medicion_precio"]])
        y = dia[["precio_bs"]].values.astype(float)
    else:
        H = np.eye(2)
        R = np.diag([ke["var_medicion_precio"], ke["var_medicion_solicitudes"]])
        y = dia[["precio_bs", "solicitudes"]].values.astype(float)
    # Mismo formato que devuelve simular(); solo se usan par, p, D0 y S0.
    pseudo = {"par": dict(P.PARAMS), "p": np.zeros(n), "D0": D0, "S0": S0,
              "t": np.arange(n) * P.PARAMS["dt"]}
    x0 = [dia["precio_bs"].iloc[0], dia["solicitudes"].iloc[0]]
    res = fk.ejecutar_filtro_kalman(pseudo, y, H, R, ke["desviacion_choque_demanda"],
                                    estado_inicial=x0, incertidumbre_inicial=25.0,
                                    factor_escala_q=factor_q)
    F = me.matriz_F(P.PARAMS)
    Q = fk.construir_matriz_Q(ke["desviacion_choque_demanda"], factor_q)
    pred, innov, nis, var_pred_p = [], [], [], []
    for k in range(1, n):
        Bu = me.termino_entrada(P.PARAMS, D0=D0[k], S0=S0[k - 1])
        xp, Pp = fk.predecir_estado(res["estimaciones"][k - 1], res["covarianzas"][k - 1],
                                    F, Bu, Q)
        nu = y[k] - H @ xp
        Sk = H @ Pp @ H.T + R
        pred.append(xp)
        innov.append(nu)
        nis.append(float(nu @ np.linalg.solve(Sk, nu)))
        var_pred_p.append(Sk[0, 0])
    pred, innov = np.array(pred), np.array(innov)
    return {"res": res, "pred": pred, "innov": innov, "nis": np.array(nis),
            "sd_pred_precio": np.sqrt(var_pred_p), "y": y, "dim": H.shape[0]}


FACTORES_Q = (0.1, 1.0, 10.0, 30.0, 100.0)


def _entradas(dia, red):
    if red is None:
        return np.full(len(dia), P.D0_BASE), np.full(len(dia), P.S0_BASE)
    return entradas_contexto(dia, red)


def kalman_E(df, red_cal):
    """Barre el factor de escala de Q (calibracion con innovaciones: un
    filtro consistente tiene NIS medio = numero de mediciones). Devuelve la
    tabla, el factor elegido y las corridas de la red calibrada con ese factor."""
    redes = {"nominal (D0=S0=50)": None, "contexto red experta": comun.construir_red(),
             "contexto red calibrada": red_cal}
    entradas = {(nombre, f): _entradas(dia, red) for nombre, red in redes.items()
                for f, dia in df.groupby("fecha")}
    filas = []
    for nombre in redes:
        for solo_precio in (True, False):
            for factor_q in FACTORES_Q:
                err, nis, cubre, dim = [], [], [], None
                for fecha, dia in df.groupby("fecha"):
                    k = kalman_dia(dia, solo_precio, *entradas[(nombre, fecha)], factor_q)
                    err.extend(k["innov"][:, 0])
                    nis.extend(k["nis"])
                    cubre.extend(np.abs(k["innov"][:, 0]) <= P.NIVEL_CONFIANZA_Z * k["sd_pred_precio"])
                    dim = k["dim"]
                err = np.array(err)
                filas.append({"entradas_D0_S0": nombre,
                              "mediciones": "solo precio" if solo_precio else "precio + solicitudes",
                              "factor_q": factor_q,
                              "rmse_prediccion_1paso_precio": float(np.sqrt(np.mean(err ** 2))),
                              "sesgo_innovacion_precio": float(err.mean()),
                              "NIS_medio": float(np.mean(nis)), "NIS_esperado": dim,
                              "cobertura_prediccion_precio_2sd": float(np.mean(cubre))})
    tabla = pd.DataFrame(filas)
    comun.guardar_tabla(tabla.round(4), "E_kalman_innovaciones.csv", index=False)

    elegida = tabla[(tabla["entradas_D0_S0"] == "contexto red calibrada")
                    & (tabla["mediciones"] == "precio + solicitudes")]
    factor_q = float(elegida.loc[(elegida["NIS_medio"] - elegida["NIS_esperado"]).abs().idxmin(),
                                 "factor_q"])
    guardar = {}
    for solo_precio in (True, False):
        for fecha, dia in df.groupby("fecha"):
            guardar[(solo_precio, fecha)] = (dia, kalman_dia(
                dia, solo_precio, *entradas[("contexto red calibrada", fecha)], factor_q))
    return tabla, factor_q, guardar


def exportar_estimaciones_E(guardar):
    filas = []
    for (solo_precio, fecha), (dia, k) in sorted(guardar.items()):
        est, sd = k["res"]["estimaciones"], k["res"]["desviaciones"]
        z = P.NIVEL_CONFIANZA_Z
        filas.append(pd.DataFrame({
            "timestamp": dia["timestamp"].values,
            "mediciones": "solo_precio" if solo_precio else "precio_y_solicitudes",
            "precio_obs": dia["precio_bs"].values,
            "precio_estimado": est[:, 0], "precio_li": est[:, 0] - z * sd[:, 0],
            "precio_ls": est[:, 0] + z * sd[:, 0],
            "demanda_estimada": est[:, 1], "demanda_li": est[:, 1] - z * sd[:, 1],
            "demanda_ls": est[:, 1] + z * sd[:, 1]}))
    tabla = pd.concat(filas, ignore_index=True)
    comun.guardar_tabla(tabla.round(4), "E_estimaciones_kalman.csv", index=False)
    return tabla


def figura_kalman_E(guardar, factor_q, fecha="2026-10-30"):
    fig, ejes = comun.plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    for ax, solo_precio in zip(ejes, (True, False)):
        dia, k = guardar[(solo_precio, fecha)]
        horas = pd.to_datetime(dia["timestamp"]).dt.hour + pd.to_datetime(dia["timestamp"]).dt.minute / 60
        est, sd = k["res"]["estimaciones"][:, 0], k["res"]["desviaciones"][:, 0]
        ax.plot(horas, dia["precio_bs"], ".", color="0.4", ms=4, label="precio_bs observado")
        ax.plot(horas, est, color=comun.COLORES["E"], label="Estimacion Kalman")
        ax.fill_between(horas, est - 2 * sd, est + 2 * sd, color=comun.COLORES["E"], alpha=0.25,
                        label="+-2 desv.")
        ax.axhline(P.TARIFA_ALTA, color="k", ls=":", lw=1, label="Tarifa alta (13 Bs)")
        ax.set_ylabel("Precio (Bs)")
        ax.set_title(("Solo precio" if solo_precio else "Precio + solicitudes")
                     + f" - D0, S0 de la red calibrada, Q x {factor_q:g}")
        ax.grid(alpha=0.3)
    ejes[0].legend(fontsize=8, loc="upper left")
    ejes[1].set_xlabel("Hora del dia")
    fig.suptitle(f"Escenario E ({AVISO}): viernes {fecha}, lluvia y evento 18:00-21:30")
    return comun.guardar_figura(fig, "E_kalman_viernes.png")


def main():
    df = cargar()
    print(f"Escenario E - {AVISO.upper()} ({len(df)} filas, {df['fecha'].nunique()} dias). "
          "Ver datos/README.md.\n")

    marg, conj = frecuencias(df)
    figura_frecuencias(marg)
    print("Frecuencias por contexto (hora_punta, lluvia, evento):")
    print(conj.round(3).to_string(index=False))

    ident = identificabilidad(df)
    print("\nIdentificabilidad: pendiente de una regresion ingenua vs valor nominal")
    print(ident.round(3).to_string(index=False))

    efectos = efectos_contexto(df)
    print("\nPregunta 6: efecto de cada factor sobre D0 (ingenuo vs regresion vs generador)")
    print(efectos.round(2).to_string(index=False))

    cortes, crudos, vD0, vS0, sep = calibracion(df)
    print(f"\nTerciles crudos (datos/README.md): solicitudes {crudos['solicitudes']}, "
          f"vehiculos {crudos['vehiculos']}")
    print(f"Cortes propuestos para discretizar(): D0_hat {cortes['D0_hat']}, "
          f"S0_hat {cortes['S0_hat']}")
    print("Separacion de contextos segun la variable discretizada:")
    print(sep.round(3).to_string())
    print(f"VALORES_D0 calibrados: {vD0}   (actuales en traduccion.py: "
          f"{comun.traduccion.VALORES_D0})")
    print(f"VALORES_S0 calibrados: {vS0}   (actuales en traduccion.py: "
          f"{comun.traduccion.VALORES_S0})")

    red_cal = red_calibrada(df)
    comp = comparar_redes(df, red_cal)
    print("\nP(escasez) red experta vs red calibrada (proxy tarifa_alta) vs datos:")
    print(comp.round(3).to_string(index=False))

    tabla, factor_q, guardar = kalman_E(df, red_cal)
    exportar_estimaciones_E(guardar)
    figura_kalman_E(guardar, factor_q)
    print("\nKalman sobre los datos: error de prediccion a un paso e innovaciones")
    print(tabla.round(3).to_string(index=False))
    print(f"\nFactor de Q elegido (NIS medio mas cercano a 2, red calibrada, "
          f"precio + solicitudes): {factor_q:g}")


if __name__ == "__main__":
    main()
