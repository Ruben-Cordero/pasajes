"""
main.py - Pipeline completo: Bayes -> Euler -> Kalman -> decision de tarifa
Persona 4 (escenarios, datos, decision e integracion)

Modo contexto (por defecto):
  contexto (hora, clima, evento, trafico)
    -> traduccion.contexto_a_parametros()  D0, S0, P(escasez)   [Persona 2]
    -> modelo_euler.simular()              precio, demanda      [Persona 1]
    -> filtro_kalman (mediciones ruidosas) precio estimado +- 2 desv. [Persona 3]
    -> decision.decidir()                  MANTENER / SUBIR / INCENTIVAR

Modo --escenario E: corre lo mismo sobre un dia de datos/procesado/escenario_e.csv
(DATOS SINTETICOS): P(escasez) por intervalo con la red calibrada, Kalman sobre
precio_bs y solicitudes, decision intervalo a intervalo.

Ejemplos:
  python main.py --hora punta --clima lluvia --evento si
  python main.py --hora valle --clima seco --red calibrada
  python main.py --escenario E --fecha 2026-10-30 --hora-consulta 19:00
"""

import argparse

import numpy as np
import pandas as pd

from integracion import comun
from integracion import params as P
from capa1_euler import modelo_euler as me
from capa3_kalman import filtro_kalman as fk
from integracion import decision
from integracion import escenario_e


def red_elegida(nombre):
    return comun.construir_red() if nombre == "experta" else escenario_e.red_calibrada()


# ---------------------------------------------------------------------------
# Modo contexto
# ---------------------------------------------------------------------------
def pipeline_contexto(args):
    ev = comun.evidencia(args.hora, args.clima, args.evento, args.trafico)
    red = red_elegida(args.red)

    # 1. Bayes -> D0, S0, P(escasez)
    trad = comun.traduccion.contexto_a_parametros(ev, red=red)
    p_esc = trad["p_escasez"]
    H_esc = comun.entropia(comun.consultar("Escasez", ev, red))
    p_eq = me.equilibrio(P.PARAMS, trad["D0"], trad["S0"])["p_eq"]

    # 2-3. Euler + Kalman (mediciones ruidosas)
    kd = P.KALMAN_D
    caso = fk.ejecutar_caso_completo(
        semilla=args.semilla, solo_precio=args.mediciones == "precio",
        D0=trad["D0"], S0=trad["S0"], parametros=P.PARAMS,
        desviacion_choque_demanda=kd["desviacion_choque_demanda"],
        desviacion_medicion_precio=kd["desviacion_medicion_precio"],
        desviacion_medicion_demanda=kd["desviacion_medicion_demanda"])
    sim, res = caso["simulacion"], caso["resultado"]
    precio, sd = res["estimaciones"][:, 0], res["desviaciones"][:, 0]

    # 4. Decision (intervalo a intervalo y al final del horizonte)
    acciones = decision.decidir_secuencia(np.full(len(precio), p_esc), precio, sd, args.X, args.Y)
    final = decision.explicar(p_esc, precio[-1], sd[-1], args.X, args.Y)

    print("=" * 72)
    print(f"Contexto: {ev}   (red {args.red})")
    print("=" * 72)
    print(f"[Bayes]  D0 = {trad['D0']:.1f}   S0 = {trad['S0']:.1f}   "
          f"P(escasez) = {p_esc:.3f}  (entropia {H_esc:.2f} bits)")
    print(f"[Euler]  p* teorico = {p_eq:.2f} Bs   precio medio simulado = {sim['p'].mean():.2f} Bs")
    print(f"[Kalman] mediciones: {args.mediciones}.  Precio estimado al final = {precio[-1]:.2f} Bs "
          f"(95 %: {final['precio_li']:.2f} - {final['precio_ls']:.2f});  "
          f"error RMS vs verdadero = {fk.resumir_desempeno(sim, res)['error_precio']:.2f} Bs")
    print(f"[Decision] X = {args.X:.2f}, Y = {args.Y:.1f} Bs  ->  {final['accion']}")
    print(f"           {final['motivo']}")
    frac = {a: float((acciones == a).mean()) for a in decision.ACCIONES}
    print("           En el horizonte de 300 min: " +
          ", ".join(f"{a} {100 * f:.0f} %" for a, f in frac.items()))

    fig, ax = comun.plt.subplots(figsize=(10, 4.5))
    ax.plot(sim["t"], sim["p"], "k-", lw=1, label="Precio verdadero (simulado)")
    if caso["mediciones"].shape[1] >= 1:
        ax.plot(sim["t"], caso["mediciones"][:, 0], ".", color="0.5", ms=4, label="Medicion")
    ax.plot(sim["t"], precio, color=comun.COLORES["D"], label="Kalman")
    ax.fill_between(sim["t"], precio - 2 * sd, precio + 2 * sd, color=comun.COLORES["D"],
                    alpha=0.2, label="+-2 desv.")
    ax.axhline(args.Y, color="k", ls=":", lw=1, label=f"Y = {args.Y:.0f} Bs")
    _marcar_acciones(ax, sim["t"], acciones)
    ax.set_xlabel("Tiempo (min)")
    ax.set_ylabel("Precio (Bs)")
    ax.set_title(f"Pipeline: {ev} -> P(escasez) = {p_esc:.2f}, decision final: {final['accion']}")
    ax.legend(fontsize=8, loc="upper right")
    ax.grid(alpha=0.3)
    nombre = "pipeline_" + "_".join(ev.values()) + ".png"
    ruta = comun.guardar_figura(fig, nombre)
    print(f"Figura: {ruta}")


def _marcar_acciones(ax, t, acciones):
    colores = {"SUBIR": "#d62728", "INCENTIVAR": "#2ca02c"}
    dt = t[1] - t[0] if len(t) > 1 else 1
    for a, c in colores.items():
        marcado = False
        for ti, ai in zip(t, acciones):
            if ai == a:
                ax.axvspan(ti, ti + dt, color=c, alpha=0.12, lw=0,
                           label=None if marcado else f"Accion: {a}")
                marcado = True


# ---------------------------------------------------------------------------
# Modo escenario E (datos sinteticos)
# ---------------------------------------------------------------------------
def pipeline_E(args):
    df = escenario_e.cargar()
    escenario_e.calibracion(df)
    red = escenario_e.red_calibrada(df)
    dia = df[df["fecha"] == args.fecha]
    if dia.empty:
        raise SystemExit(f"No hay datos para {args.fecha}. Fechas: {sorted(df['fecha'].unique())}")

    pe = np.array([comun.consultar("Escasez", comun.evidencia_fila(f), red)["si"]
                   for _, f in dia.iterrows()])
    D0, S0 = escenario_e.entradas_contexto(dia, red)
    k = escenario_e.kalman_dia(dia, args.mediciones == "precio", D0, S0, args.factor_q)
    precio, sd = k["res"]["estimaciones"][:, 0], k["res"]["desviaciones"][:, 0]
    acciones = decision.decidir_secuencia(pe, precio, sd, args.X, args.Y)

    print("=" * 72)
    print(f"Escenario E - DATOS SINTETICOS (datos/README.md) - dia {args.fecha}")
    print("=" * 72)
    print(f"Kalman ({args.mediciones}, Q x {args.factor_q:g}): error RMS de prediccion a un paso "
          f"= {np.sqrt(np.mean(k['innov'][:, 0] ** 2)):.2f} Bs, NIS medio = {k['nis'].mean():.2f} "
          f"(esperado {k['dim']})")
    print("Acciones del dia: " + ", ".join(
        f"{a} {100 * (acciones == a).mean():.0f} %" for a in decision.ACCIONES))

    sel = dia["timestamp"].str.endswith(args.hora_consulta)
    if sel.any():
        i = int(np.where(sel.values)[0][0])
        f = dia.iloc[i]
        exp = decision.explicar(pe[i], precio[i], sd[i], args.X, args.Y)
        print(f"\nA las {args.hora_consulta}: contexto {comun.evidencia_fila(f)}")
        print(f"  P(escasez) = {pe[i]:.3f}; precio observado = {f['precio_bs']:.1f} Bs; "
              f"estimado = {precio[i]:.2f} Bs (95 %: {exp['precio_li']:.2f} - {exp['precio_ls']:.2f})")
        print(f"  Decision (con permanencia de {P.PERMANENCIA_MIN * 5} min): {acciones[i]}")
        print(f"  Regla instantanea: {exp['accion']} - {exp['motivo']}")

    horas = pd.to_datetime(dia["timestamp"])
    horas = (horas.dt.hour + horas.dt.minute / 60).values
    fig, ejes = comun.plt.subplots(2, 1, figsize=(11, 6.5), sharex=True,
                                   gridspec_kw={"height_ratios": [3, 1]})
    ax = ejes[0]
    ax.plot(horas, dia["precio_bs"], ".", color="0.4", ms=4, label="precio_bs observado")
    ax.plot(horas, precio, color=comun.COLORES["E"], label="Kalman")
    ax.fill_between(horas, precio - 2 * sd, precio + 2 * sd, color=comun.COLORES["E"], alpha=0.25,
                    label="+-2 desv.")
    ax.axhline(args.Y, color="k", ls=":", lw=1, label=f"Y = {args.Y:.0f} Bs")
    _marcar_acciones(ax, horas, acciones)
    ax.set_ylabel("Precio (Bs)")
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(alpha=0.3)
    ejes[1].step(horas, pe, where="post", color="k")
    ejes[1].axhline(args.X, color="r", ls="--", lw=1, label=f"X = {args.X:.2f}")
    ejes[1].set_ylabel("P(escasez)")
    ejes[1].set_xlabel("Hora del dia")
    ejes[1].legend(fontsize=8)
    ejes[1].grid(alpha=0.3)
    fig.suptitle(f"Pipeline sobre el Escenario E (datos sinteticos), {args.fecha}")
    ruta = comun.guardar_figura(fig, f"pipeline_E_{args.fecha}.png")
    print(f"\nFigura: {ruta}")


def main():
    ap = argparse.ArgumentParser(description="Pipeline Bayes -> Euler -> Kalman -> decision")
    ap.add_argument("--escenario", choices=["contexto", "E"], default="contexto")
    ap.add_argument("--hora", choices=["valle", "punta"], default="punta")
    ap.add_argument("--clima", choices=["seco", "lluvia"], default="lluvia")
    ap.add_argument("--evento", choices=["no", "si"], default="si")
    ap.add_argument("--trafico", choices=["bajo", "alto"], default=None,
                    help="opcional; si se omite la red lo infiere")
    ap.add_argument("--red", choices=["experta", "calibrada"], default="experta",
                    help="experta = Persona 2; calibrada = re-estimada con datos sinteticos")
    ap.add_argument("--mediciones", choices=["precio", "ambas"], default="ambas",
                    help="solo precio o precio + solicitudes")
    ap.add_argument("--X", type=float, default=P.UMBRAL_X, help="umbral de P(escasez)")
    ap.add_argument("--Y", type=float, default=P.UMBRAL_Y, help="umbral de precio (Bs)")
    ap.add_argument("--semilla", type=int, default=P.SEMILLA)
    ap.add_argument("--fecha", default="2026-10-30", help="solo --escenario E")
    ap.add_argument("--hora-consulta", default="19:00", help="solo --escenario E (HH:MM)")
    ap.add_argument("--factor-q", type=float, default=30.0,
                    help="solo --escenario E; 30 = calibrado con innovaciones (integracion/escenario_e.py)")
    args = ap.parse_args()
    if args.escenario == "E":
        pipeline_E(args)
    else:
        pipeline_contexto(args)


if __name__ == "__main__":
    main()
