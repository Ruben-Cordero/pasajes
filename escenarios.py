"""
escenarios.py - Escenarios A, B, C y D
Persona 4 (escenarios, datos, decision e integracion)

Usa simular(), equilibrio(), estabilidad() y metricas() de modelo_euler.py
(Persona 1) y el filtro de filtro_kalman.py (Persona 3) sin modificarlos.

Salidas:
  resultados/tablas/metricas_escenarios.csv
  resultados/tablas/kalman_valor_informacion.csv
  resultados/tablas/estimaciones_kalman_D.csv
  resultados/figuras/escenarios_ABC.png
  resultados/figuras/escenario_A_convergencia.png
  resultados/figuras/escenario_D_kalman.png

Uso:  python escenarios.py
"""

import numpy as np
import pandas as pd

import comun
import params as P
import modelo_euler as me
import filtro_kalman as fk


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

    tabla, _ = escenario_D()
    print("\nEscenario D - valor de la informacion (promedio de "
          f"{P.KALMAN_D['realizaciones']} realizaciones):")
    print(tabla.round(3).to_string())
    print(f"\nResultados en {P.RESULTADOS}")


if __name__ == "__main__":
    main()
