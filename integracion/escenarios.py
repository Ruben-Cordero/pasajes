"""
escenarios.py - Escenarios A, B, C y D
Persona 4 (escenarios, datos, decision e integracion)

Usa simular(), equilibrio(), estabilidad() y metricas() de modelo_euler.py
(Persona 1) y el filtro de filtro_kalman.py (Persona 3) sin modificarlos,
mas las extensiones de capa3_kalman/ (extensiones.py y no_lineal.py).

Salidas:
  resultados/tablas/metricas_escenarios.csv
  resultados/tablas/sensibilidad_parametros.csv        pregunta 1
  resultados/tablas/kalman_valor_informacion.csv       pregunta 5
  resultados/tablas/kalman_sensibilidad_QR.csv         pregunta 3
  resultados/tablas/kalman_atipicos.csv                Escenario D: valores atipicos
  resultados/tablas/kalman_pronostico.csv              predicciones x_{k+m|k}
  resultados/tablas/estimaciones_kalman_D.csv
  resultados/tablas/no_lineal_estabilidad.csv          pregunta 4
  resultados/tablas/no_lineal_filtros.csv              pregunta 4: KF vs EKF vs UKF
  resultados/figuras/escenarios_ABC.png
  resultados/figuras/escenario_A_convergencia.png
  resultados/figuras/sensibilidad_parametros.png
  resultados/figuras/escenario_D_kalman.png
  resultados/figuras/no_lineal_dinamica.png
  resultados/figuras/no_lineal_filtros.png

Uso (desde la raiz):  python -m integracion.escenarios
"""

import numpy as np
import pandas as pd

from integracion import comun
from integracion import params as P
from capa1_euler import modelo_euler as me
from capa3_kalman import filtro_kalman as fk
from capa3_kalman import extensiones as ext
from capa3_kalman import no_lineal as nl


def comprobar_parametros():
    """params.py y modelo_euler.PARAMS_BASE deben decir lo mismo."""
    distintos = {k: (v, me.PARAMS_BASE.get(k)) for k, v in P.PARAMS.items()
                 if me.PARAMS_BASE.get(k) != v}
    if distintos:
        raise SystemExit(f"params.py no coincide con modelo_euler.PARAMS_BASE: {distintos}")


def simular_escenario(clave, ruido=0.0, semilla=None):
    esc = P.ESCENARIOS[clave]
    return me.simular(P.PARAMS, D0=esc["D0"], S0=esc["S0"], ruido=ruido, semilla=semilla)


def _tramo(sim, desde, hasta):
    """Sub-simulacion entre dos instantes (para medir el tramo de la ventana)."""
    idx = (sim["t"] >= desde) & (sim["t"] < hasta)
    sub = {k: (v[idx] if isinstance(v, np.ndarray) and len(v) == len(sim["t"]) else v)
           for k, v in sim.items()}
    sub["t"] = sub["t"] - desde
    return sub


def metricas_ABC():
    filas = []
    sims = {}
    for clave in "ABC":
        esc = P.ESCENARIOS[clave]
        sim = simular_escenario(clave)
        sims[clave] = sim
        eq_base = me.equilibrio(P.PARAMS, P.D0_BASE, P.S0_BASE)["p_eq"]
        eq_vent = me.equilibrio(P.PARAMS, esc["D0_ventana"], esc["S0_ventana"])["p_eq"]
        m = me.metricas(sim, eq_base)
        fila = {"escenario": clave, "nombre": esc["nombre"],
                "p_eq_teorico_base": eq_base,
                "p_eq_teorico_ventana": eq_vent}
        fila.update(m)
        if clave != "A":
            # Tiempo para alcanzar el equilibrio de la ventana, contado desde
            # el minuto 60 (cuando empieza la hora punta o la lluvia).
            tramo = _tramo(sim, *P.VENTANA)
            fila["tiempo_equilibrio_ventana_min"] = me.metricas(tramo, eq_vent)[
                "tiempo_hasta_equilibrio_min"]
            fila["precio_medio_ventana"] = tramo["p"].mean()
        else:
            fila["tiempo_equilibrio_ventana_min"] = np.nan
            fila["precio_medio_ventana"] = np.nan
        filas.append(fila)
    df = pd.DataFrame(filas)
    df = df.rename(columns={"servicios_totales": "servicios_realizados"})
    return df, sims


def figura_ABC(sims):
    fig, ejes = comun.plt.subplots(3, 1, figsize=(10, 9), sharex=True)
    etiquetas = {"A": "A: base", "B": "B: hora punta (D0=100)", "C": "C: lluvia (S0=30)"}
    for clave, sim in sims.items():
        c = comun.COLORES[clave]
        ejes[0].plot(sim["t"], sim["p"], color=c, label=etiquetas[clave])
        ejes[1].plot(sim["t"], sim["D"], color=c, label=etiquetas[clave])
        ejes[2].plot(sim["t"], sim["S"], color=c, label=etiquetas[clave])
    for ax in ejes:
        ax.axvspan(*P.VENTANA, color="0.85", alpha=0.5, lw=0)
        ax.grid(alpha=0.3)
    ejes[0].axhline(me.equilibrio(P.PARAMS)["p_eq"], color="k", ls=":", lw=1,
                    label="p* base = 7.86")
    ejes[0].set_ylabel("Precio (Bs)")
    ejes[1].set_ylabel("Demanda (solicitudes)")
    ejes[2].set_ylabel("Oferta (vehiculos)")
    ejes[2].set_xlabel("Tiempo (min)  - zona gris: minutos 60 a 180")
    ejes[0].legend(loc="upper right", fontsize=8)
    ejes[0].set_title("Escenarios A, B y C: precio, demanda y oferta")
    return comun.guardar_figura(fig, "escenarios_ABC.png")


def figura_convergencia_A(sim):
    est = me.estabilidad(P.PARAMS)
    p_eq = me.equilibrio(P.PARAMS)["p_eq"]
    fig, ax = comun.plt.subplots(figsize=(10, 4))
    ax.plot(sim["t"], sim["p"], "o-", color=comun.COLORES["A"], ms=3, label="Precio p_k")
    ax.axhline(p_eq, color="k", ls=":", label=f"p* = {p_eq:.2f}")
    ax.fill_between(sim["t"], p_eq * 0.99, p_eq * 1.01, color="0.8", label="Banda 1 %")
    ax.set_xlim(0, 120)
    ax.set_xlabel("Tiempo (min)")
    ax.set_ylabel("Precio (Bs)")
    ax.set_title(f"Escenario A: arranca en p0 = 10 y converge oscilando "
                 f"(dt*a*(b+g) = {est['producto']:.2f}, r = {est['r']:.2f})")
    ax.grid(alpha=0.3)
    ax.legend()
    return comun.guardar_figura(fig, "escenario_A_convergencia.png")


# ---------------------------------------------------------------------------
# Pregunta 1: sensibilidad a alpha, beta y gamma
# ---------------------------------------------------------------------------
FACTORES_SENSIBILIDAD = (0.5, 0.75, 1.0, 1.1, 1.25)


def sensibilidad():
    """Cada parametro se multiplica por un factor dejando los demas en su valor
    nominal. La oscilacion del precio tiene periodo 2*dt cuando r < 0 y su
    amplitud se reduce en |r| por intervalo; el sobreimpulso es cuanto supera
    el precio al equilibrio de la ventana en el Escenario B."""
    eq_nom = me.equilibrio(P.PARAMS)["p_eq"]
    filas = []
    for nombre in ("alpha", "beta", "gamma"):
        # Elasticidad local de p*: % de cambio de p* por 1 % del parametro
        h = 1e-4
        p_h = me.equilibrio(dict(P.PARAMS, **{nombre: P.PARAMS[nombre] * (1 + h)}))["p_eq"]
        elasticidad = (p_h - eq_nom) / eq_nom / h
        for f in FACTORES_SENSIBILIDAD:
            par = dict(P.PARAMS, **{nombre: P.PARAMS[nombre] * f})
            est = me.estabilidad(par)
            eq_A = me.equilibrio(par)["p_eq"]
            eq_B = me.equilibrio(par, 100.0, P.S0_BASE)["p_eq"]
            m_A = me.metricas(me.simular(par), eq_A)
            sim_B = me.simular(par, D0=P.ESCENARIOS["B"]["D0"], S0=P.S0_BASE)
            en_v = (sim_B["t"] >= P.VENTANA[0]) & (sim_B["t"] < P.VENTANA[1])
            filas.append({
                "parametro": nombre, "factor": f, "valor": par[nombre],
                "dt*a*(b+g)": est["producto"], "r": est["r"], "estable": est["estable"],
                "periodo_oscilacion_min": 2 * par["dt"] if est["r"] < 0 else np.nan,
                "p_eq": eq_A, "elasticidad_p_eq": elasticidad,
                "t_equilibrio_A_min": m_A["tiempo_hasta_equilibrio_min"] if est["estable"] else np.nan,
                "sobreimpulso_B_bs": sim_B["p"][en_v].max() - eq_B if est["estable"] else np.nan,
            })
    return pd.DataFrame(filas)


def figura_sensibilidad(tabla):
    fig, ejes = comun.plt.subplots(1, 3, figsize=(15, 4))
    for nombre, marcador in (("alpha", "o"), ("beta", "s"), ("gamma", "^")):
        t = tabla[tabla["parametro"] == nombre]
        ejes[0].plot(t["factor"], t["r"], marcador + "-", label=nombre)
        ejes[1].plot(t["factor"], t["t_equilibrio_A_min"], marcador + "-", label=nombre)
        ejes[2].plot(t["factor"], t["sobreimpulso_B_bs"], marcador + "-", label=nombre)
    ejes[0].axhline(-1, color="r", ls=":", label="limite de estabilidad")
    ejes[0].set_ylabel("r = 1 - dt*a*(b+g)")
    ejes[1].set_ylabel("Tiempo hasta equilibrio, A (min)")
    ejes[2].set_ylabel("Sobreimpulso del precio en B (Bs)")
    for ax in ejes:
        ax.set_xlabel("Factor sobre el valor nominal")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8)
    fig.suptitle("Pregunta 1: sensibilidad a alpha, beta y gamma (sin punto = inestable)")
    return comun.guardar_figura(fig, "sensibilidad_parametros.png")


# ---------------------------------------------------------------------------
# Escenario D: Kalman (Persona 3) sobre mediciones ruidosas simuladas
# ---------------------------------------------------------------------------
def escenario_D():
    kd = P.KALMAN_D
    args = dict(desviacion_choque_demanda=kd["desviacion_choque_demanda"],
                desviacion_medicion_precio=kd["desviacion_medicion_precio"],
                desviacion_medicion_demanda=kd["desviacion_medicion_demanda"],
                parametros=P.PARAMS)
    casos = {nombre: fk.ejecutar_caso_completo(semilla=P.SEMILLA, solo_precio=sp, **args)
             for nombre, sp in [("solo_precio", True), ("precio_y_solicitudes", False)]}

    # Valor de la informacion promediado en varias realizaciones (pregunta 5)
    tabla = fk.experimento_valor_informacion(kd["realizaciones"], **args)
    tabla = tabla.rename(columns={"precio_y_demanda": "precio_y_solicitudes"})
    tabla.index.name = "metrica"
    comun.guardar_tabla(tabla, "kalman_valor_informacion.csv")

    # Estimaciones con intervalo (lo que se entrega a la decision)
    fk.exportar_estimaciones_csv(casos["precio_y_solicitudes"],
                                 ruta_archivo=f"{P.TABLAS}/estimaciones_kalman_D.csv")

    fig, ejes = comun.plt.subplots(2, 2, figsize=(12, 7), sharex=True)
    for j, (nombre, caso) in enumerate(casos.items()):
        sim, res, med = caso["simulacion"], caso["resultado"], caso["mediciones"]
        for i, (var, etiqueta) in enumerate([("p", "Precio (Bs)"), ("D", "Demanda")]):
            ax = ejes[i, j]
            est = res["estimaciones"][:, i]
            banda = P.NIVEL_CONFIANZA_Z * res["desviaciones"][:, i]
            ax.plot(sim["t"], sim[var], "k-", lw=1.2, label="Verdadero")
            if i < med.shape[1]:
                ax.plot(sim["t"], med[:, i], ".", color="0.5", ms=4, label="Medicion")
            ax.plot(sim["t"], est, color=comun.COLORES["D"], label="Kalman")
            ax.fill_between(sim["t"], est - banda, est + banda,
                            color=comun.COLORES["D"], alpha=0.2, label="+-2 desv.")
            ax.set_ylabel(etiqueta)
            ax.grid(alpha=0.3)
        ejes[0, j].set_title("Solo precio (H = [1, 0])" if nombre == "solo_precio"
                             else "Precio + solicitudes (H = I2)")
    ejes[0, 0].legend(fontsize=8)
    ejes[1, 0].set_xlabel("Tiempo (min)")
    ejes[1, 1].set_xlabel("Tiempo (min)")
    fig.suptitle("Escenario D: estimacion con filtro de Kalman")
    comun.guardar_figura(fig, "escenario_D_kalman.png")
    return tabla, casos


def _args_D():
    kd = P.KALMAN_D
    return dict(desviacion_choque_demanda=kd["desviacion_choque_demanda"],
                desviacion_medicion_precio=kd["desviacion_medicion_precio"],
                desviacion_medicion_demanda=kd["desviacion_medicion_demanda"],
                parametros=P.PARAMS)


def escenario_D_calibracion():
    """Pregunta 3 (Q y R), valores atipicos y predicciones x_{k+m|k}."""
    args, n = _args_D(), P.KALMAN_D["realizaciones"]

    # Q y R escalados por 0,01 / 1 / 100, promedio de n realizaciones
    qr = pd.concat([fk.experimento_calibracion_q_r(fk.ejecutar_caso_completo(semilla=s, **args))
                    for s in range(n)])
    qr = qr.groupby(["factor_escala_q", "factor_escala_r"]).mean().reset_index()
    comun.guardar_tabla(qr.round(4), "kalman_sensibilidad_QR.csv", index=False)

    atip = ext.experimento_atipicos_robusto(n, P.ATIPICOS_D, **args)
    comun.guardar_tabla(atip.round(4), "kalman_atipicos.csv")

    pron = ext.experimento_pronostico(n, **args)
    comun.guardar_tabla(pron.round(4), "kalman_pronostico.csv", index=False)
    return qr, atip, pron


# ---------------------------------------------------------------------------
# Pregunta 4: umbral de tolerancia al precio, EKF y UKF
# ---------------------------------------------------------------------------
def no_lineal():
    D0_B = P.ESCENARIOS["B"]["D0"]
    filas = []
    for alpha in (P.PARAMS["alpha"], P.ALPHA_NO_LINEAL):
        par = dict(P.PARAMS, alpha=alpha)
        for contexto, D0 in (("base (D0 = 50)", P.D0_BASE), ("hora punta (D0 = 100)", 100.0)):
            lin_eq, lin_est = me.equilibrio(par, D0, P.S0_BASE), me.estabilidad(par)
            nl_eq = nl.equilibrio_no_lineal(par, D0, P.S0_BASE)
            filas.append({"alpha": alpha, "contexto": contexto,
                          "p_eq_lineal": lin_eq["p_eq"], "r_lineal": lin_est["r"],
                          "p_eq_con_umbral": nl_eq["p_eq"],
                          "pendiente_demanda_con_umbral": -nl_eq["beta_local"],
                          "r_con_umbral": nl_eq["r"], "estable_con_umbral": nl_eq["estable"],
                          "alpha_max_con_umbral": nl_eq["alpha_max"]})
    estab = pd.DataFrame(filas)
    comun.guardar_tabla(estab.round(4), "no_lineal_estabilidad.csv", index=False)

    kd = P.KALMAN_D
    par_nl = dict(P.PARAMS, alpha=P.ALPHA_NO_LINEAL)
    filtros = nl.experimento_filtros(
        par_nl, D0_B, P.S0_BASE, kd["realizaciones"], kd["desviacion_choque_demanda"],
        desviacion_medicion_precio=kd["desviacion_medicion_precio"],
        desviacion_medicion_demanda=kd["desviacion_medicion_demanda"])
    comun.guardar_tabla(filtros.round(4), "no_lineal_filtros.csv", index=False)

    # Figura 1: curva de demanda y trayectorias del precio en el Escenario B
    fig, ejes = comun.plt.subplots(1, 2, figsize=(13, 4.5))
    precios = np.linspace(P.PARAMS["p_costo"], 30, 200)
    par0 = dict(P.PARAMS)
    ejes[0].plot(precios, [max(0, 100 + par0["beta"] * (par0["p_ref"] - p)) for p in precios],
                 "k--", label="Lineal (documento)")
    ejes[0].plot(precios, [nl.demanda(p, 100.0, par0) for p in precios], color=comun.COLORES["B"],
                 label=f"Con umbral (p_tol = {nl.P_TOLERANCIA:.0f} Bs)")
    ejes[0].plot(precios, P.S0_BASE + par0["gamma"] * (precios - par0["p_costo"]),
                 color=comun.COLORES["C"], label="Oferta S(p)")
    ejes[0].set_xlabel("Precio (Bs)")
    ejes[0].set_ylabel("Solicitudes / vehiculos")
    ejes[0].set_title("Demanda en hora punta (D0 = 100)")
    trayectorias = [
        ("Lineal, alpha = 0,1", me.simular(P.PARAMS, D0=D0_B), "k--"),
        ("Con umbral, alpha = 0,1", nl.simular_no_lineal(P.PARAMS, D0=D0_B), "-"),
        (f"Con umbral, alpha = {P.ALPHA_NO_LINEAL:g}".replace(".", ","),
         nl.simular_no_lineal(par_nl, D0=D0_B), "-"),
    ]
    for etiqueta, sim, estilo in trayectorias:
        ejes[1].plot(sim["t"], sim["p"], estilo, lw=1.2, label=etiqueta)
    ejes[1].axvspan(*P.VENTANA, color="0.85", alpha=0.5, lw=0)
    ejes[1].set_xlabel("Tiempo (min)  - zona gris: hora punta")
    ejes[1].set_ylabel("Precio (Bs)")
    ejes[1].set_title("Escenario B con y sin umbral de tolerancia")
    for ax in ejes:
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8)
    fig.suptitle("Pregunta 4: el umbral de tolerancia vuelve inestable el ajuste con alpha nominal")
    comun.guardar_figura(fig, "no_lineal_dinamica.png")

    # Figura 2: una realizacion midiendo solo el precio
    sim = nl.simular_no_lineal(par_nl, D0=D0_B, ruido=kd["desviacion_choque_demanda"],
                               semilla=P.SEMILLA)
    med, res = nl.correr_filtros(sim, True, P.SEMILLA, kd["desviacion_choque_demanda"],
                                 kd["desviacion_medicion_precio"], kd["desviacion_medicion_demanda"])
    colores = {"KF lineal": "0.45", "EKF": comun.COLORES["B"], "UKF": comun.COLORES["D"]}
    fig, ejes = comun.plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    for i, (var, etiqueta) in enumerate([("p", "Precio (Bs)"), ("D", "Demanda (latente)")]):
        ax = ejes[i]
        ax.plot(sim["t"], sim[var], "k-", lw=1.4, label="Verdadero")
        if i == 0:
            ax.plot(sim["t"], med[:, 0], ".", color="0.6", ms=4, label="Medicion")
        for nombre, r in res.items():
            est = r["estimaciones"][:, i]
            ax.plot(sim["t"], est, color=colores[nombre], ls="--" if nombre == "UKF" else "-",
                    label=nombre)
            if nombre != "UKF":
                banda = P.NIVEL_CONFIANZA_Z * r["desviaciones"][:, i]
                ax.fill_between(sim["t"], est - banda, est + banda, color=colores[nombre],
                                alpha=0.15, lw=0)
        ax.axvspan(*P.VENTANA, color="0.9", alpha=0.5, lw=0)
        ax.set_ylabel(etiqueta)
        ax.grid(alpha=0.3)
    ejes[0].legend(fontsize=8, ncol=3)
    ejes[1].set_xlabel("Tiempo (min)")
    fig.suptitle(f"Pregunta 4: KF lineal vs EKF vs UKF midiendo solo el precio "
                 f"(Escenario B con umbral, alpha = {P.ALPHA_NO_LINEAL:g})")
    comun.guardar_figura(fig, "no_lineal_filtros.png")
    return estab, filtros


def main():
    comprobar_parametros()
    comun.carpetas()
    est = me.estabilidad(P.PARAMS)
    print(f"Estabilidad: dt*alpha*(beta+gamma) = {est['producto']:.2f} < 2 -> "
          f"estable; r = {est['r']:.2f} < 0 -> oscila")

    df, sims = metricas_ABC()
    comun.guardar_tabla(df.round(4), "metricas_escenarios.csv", index=False)
    figura_ABC(sims)
    figura_convergencia_A(sims["A"])
    print("\nMetricas de los escenarios A, B y C:")
    cols = ["escenario", "p_eq_teorico_base", "p_eq_teorico_ventana", "precio_medio",
            "precio_max", "tiempo_hasta_equilibrio_min", "tiempo_equilibrio_ventana_min",
            "intervalos_con_escasez", "servicios_realizados"]
    print(df[cols].round(2).to_string(index=False))

    sens = sensibilidad()
    comun.guardar_tabla(sens.round(4), "sensibilidad_parametros.csv", index=False)
    figura_sensibilidad(sens)
    print("\nPregunta 1 - sensibilidad:")
    print(sens[["parametro", "factor", "r", "estable", "p_eq", "elasticidad_p_eq",
                "t_equilibrio_A_min", "sobreimpulso_B_bs"]].round(3).to_string(index=False))

    n = P.KALMAN_D["realizaciones"]
    tabla, _ = escenario_D()
    print(f"\nEscenario D - valor de la informacion (promedio de {n} realizaciones):")
    print(tabla.round(3).to_string())

    qr, atip, pron = escenario_D_calibracion()
    print("\nPregunta 3 - Q y R escalados:")
    print(qr.round(3).to_string(index=False))
    print("\nValores atipicos: filtro estandar vs robusto (prueba chi-cuadrado):")
    print(atip.round(3).to_string())
    print("\nPrediccion x_{k+m|k}:")
    print(pron.round(3).to_string(index=False))

    estab, filtros = no_lineal()
    print("\nPregunta 4 - estabilidad con umbral de tolerancia:")
    print(estab.round(3).to_string(index=False))
    print("\nPregunta 4 - KF lineal vs EKF vs UKF:")
    print(filtros.round(3).to_string(index=False))
    print(f"\nResultados en {P.RESULTADOS}")


if __name__ == "__main__":
    main()
