"""
montecarlo.py - Monte Carlo Bayes -> Euler
Persona 4 (escenarios, datos, decision e integracion)

Para cada contexto se sortean pares (D0, S0) de P(Demanda, Oferta | contexto)
con traduccion.muestrear_parametros() (Persona 2) y se corre simular()
(Persona 1) con cada par. Asi la incertidumbre del contexto se convierte en
una banda de precios.

Se hace con la red experta de la Persona 2 y con la red re-estimada con los
datos sinteticos del Escenario E (escenario_e.red_calibrada()).

Salidas:
  resultados/tablas/montecarlo_bandas.csv    mediana y percentiles 5-95 por minuto
  resultados/tablas/montecarlo_resumen.csv   P(escasez), precio medio, etc.
  resultados/figuras/montecarlo_bandas.png

Uso:  python montecarlo.py [--n 500]
"""

import argparse

import numpy as np
import pandas as pd

import comun
import params as P
import modelo_euler as me
import escenario_e

CONTEXTOS = {
    "valle_seco": comun.evidencia("valle", "seco", "no"),
    "punta_seca": comun.evidencia("punta", "seco", "no"),
    "punta_lluvia": comun.evidencia("punta", "lluvia", "no"),
    "viernes_19h_lluvia_evento": comun.evidencia("punta", "lluvia", "si"),
}
NOMBRES = {"valle_seco": "Valle, seco", "punta_seca": "Punta, seco",
           "punta_lluvia": "Punta + lluvia",
           "viernes_19h_lluvia_evento": "Viernes 19:00, lluvia + evento"}


def correr(red, nombre_red, n, semilla):
    bandas, resumen = [], []
    for clave, ev in CONTEXTOS.items():
        pares = comun.traduccion.muestrear_parametros(ev, n=n, semilla=semilla, red=red)
        sims = [me.simular(P.PARAMS, D0=d0, S0=s0) for d0, s0 in pares]
        precios = np.array([s["p"] for s in sims])
        t = sims[0]["t"]
        q5, q50, q95 = np.percentile(precios, [5, 50, 95], axis=0)
        bandas.append(pd.DataFrame({"red": nombre_red, "contexto": clave, "t_min": t,
                                    "p5": q5, "mediana": q50, "p95": q95,
                                    "media": precios.mean(axis=0)}))
        escasez_sim = np.array([((s["D"] - s["S"]) >= 1.0).mean() for s in sims])
        p_eq = np.array([me.equilibrio(P.PARAMS, d0, s0)["p_eq"] for d0, s0 in pares])
        trad = comun.traduccion.contexto_a_parametros(ev, red=red)
        resumen.append({
            "red": nombre_red, "contexto": clave, "n_muestras": n,
            "P_escasez_red": trad["p_escasez"],
            "frac_intervalos_escasez_sim": escasez_sim.mean(),
            "D0_esperado": trad["D0"], "S0_esperado": trad["S0"],
            "precio_medio": precios.mean(),
            "p_eq_mediana": np.median(p_eq),
            "p_eq_p5": np.percentile(p_eq, 5), "p_eq_p95": np.percentile(p_eq, 95),
            "precio_final_p5": q5[-1], "precio_final_mediana": q50[-1],
            "precio_final_p95": q95[-1],
            "P_precio_final_mayor_tarifa_alta": float((precios[:, -1] >= P.TARIFA_ALTA).mean()),
        })
    return pd.concat(bandas, ignore_index=True), pd.DataFrame(resumen)


def figura(bandas, resumen):
    redes = list(dict.fromkeys(bandas["red"]))
    fig, ejes = comun.plt.subplots(len(redes), len(CONTEXTOS), figsize=(15, 4 * len(redes)),
                                   sharex=True, sharey=True, squeeze=False)
    for i, red in enumerate(redes):
        for j, clave in enumerate(CONTEXTOS):
            ax = ejes[i, j]
            b = bandas[(bandas["red"] == red) & (bandas["contexto"] == clave)]
            r = resumen[(resumen["red"] == red) & (resumen["contexto"] == clave)].iloc[0]
            ax.fill_between(b["t_min"], b["p5"], b["p95"], color=comun.COLORES["E"], alpha=0.3,
                            label="Percentiles 5-95")
            ax.plot(b["t_min"], b["mediana"], color=comun.COLORES["E"], label="Mediana")
            ax.axhline(P.TARIFA_ALTA, color="k", ls=":", lw=1, label="13 Bs")
            ax.set_title(f"{NOMBRES[clave]}\nP(escasez) = {r['P_escasez_red']:.2f}", fontsize=10)
            ax.grid(alpha=0.3)
            if j == 0:
                ax.set_ylabel(f"Red {red}\nPrecio (Bs)")
            if i == len(redes) - 1:
                ax.set_xlabel("Tiempo (min)")
    ejes[0, 0].legend(fontsize=8)
    fig.suptitle("Monte Carlo Bayes -> Euler: banda de precio por contexto "
                 f"({int(resumen['n_muestras'].iloc[0])} muestras por contexto). Arriba: red experta "
                 "(Persona 2); abajo: red calibrada con datos sinteticos")
    return comun.guardar_figura(fig, "montecarlo_bandas.png")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--n", type=int, default=500, help="muestras por contexto (>= 500)")
    args = ap.parse_args()

    redes = {"experta": comun.construir_red(), "calibrada": escenario_e.red_calibrada()}
    todas_b, todos_r = [], []
    for nombre, red in redes.items():
        b, r = correr(red, nombre, args.n, P.SEMILLA)
        todas_b.append(b)
        todos_r.append(r)
    bandas, resumen = pd.concat(todas_b), pd.concat(todos_r)
    comun.guardar_tabla(bandas.round(4), "montecarlo_bandas.csv", index=False)
    comun.guardar_tabla(resumen.round(4), "montecarlo_resumen.csv", index=False)
    figura(bandas, resumen)
    cols = ["red", "contexto", "P_escasez_red", "D0_esperado", "S0_esperado", "precio_medio",
            "p_eq_mediana", "p_eq_p5", "p_eq_p95", "P_precio_final_mayor_tarifa_alta"]
    print(resumen[cols].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
