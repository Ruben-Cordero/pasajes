"""
dibujar.py - Figuras de la red bayesiana para el informe
Persona 2 (Analista bayesiano/a)

Genera en la carpeta figuras/:
  dag.png               la red (DAG) con sus 10 aristas
  escasez_contexto.png  P(escasez) en los 8 contextos, con la entropia
  pregunta6.png         P(demanda alta) separando lluvia y hora punta

Solo necesita matplotlib (pip install matplotlib).
"""

import os
from itertools import product

import matplotlib  # type: ignore[reportMissingModuleSource]
matplotlib.use("Agg")  # guarda imagenes sin abrir ventanas
import matplotlib.pyplot as plt  # type: ignore[reportMissingModuleSource]
from matplotlib.patches import FancyArrowPatch  # type: ignore[reportMissingModuleSource]

try:
    from .red import construir_red, PADRES, ORDEN, ESTADOS
    from .consultas import escasez_por_contexto, pregunta6
except ImportError:
    from red import construir_red, PADRES, ORDEN, ESTADOS
    from consultas import escasez_por_contexto, pregunta6

CARPETA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figuras")

# Posiciones fijas (x, y) de cada nodo: contexto arriba, resultado abajo.
POS = {
    "Hora": (1, 3), "Clima": (3, 3), "Evento": (0, 1.8), "Costos": (5, 3),
    "Trafico": (3, 1.8), "Demanda": (1, 0.6), "Oferta": (4, 0.6),
    "Escasez": (2.5, -0.6),
}
COLOR = {"contexto": "#dbe7f5", "intermedio": "#efe6f7",
         "mercado": "#fbe3d6", "resultado": "#f7d4d4"}
TIPO = {"Hora": "contexto", "Clima": "contexto", "Evento": "contexto",
        "Costos": "contexto", "Trafico": "intermedio", "Demanda": "mercado",
        "Oferta": "mercado", "Escasez": "resultado"}


def dibujar_dag(ruta):
    fig, ax = plt.subplots(figsize=(9, 6))
    for hijo in ORDEN:
        for padre in PADRES[hijo]:
            ax.add_patch(FancyArrowPatch(
                POS[padre], POS[hijo], arrowstyle="-|>", mutation_scale=18,
                shrinkA=32, shrinkB=32, color="#555", lw=1.4))
    for n, (x, y) in POS.items():
        ax.text(x, y, f"{n}\n{' / '.join(ESTADOS[n])}", ha="center", va="center",
                fontsize=10, bbox=dict(boxstyle="round,pad=0.6",
                                       fc=COLOR[TIPO[n]], ec="#333"))
    ax.set_xlim(-0.8, 5.8); ax.set_ylim(-1.2, 3.6); ax.axis("off")
    ax.set_title("Red bayesiana de factores contextuales", fontsize=13)
    fig.tight_layout(); fig.savefig(ruta, dpi=150); plt.close(fig)


def dibujar_escasez(ruta, red):
    filas = escasez_por_contexto(red)
    etiquetas = [f"{e['Hora']}\n{e['Clima']}\nev:{e['Evento']}" for e, _, _ in filas]
    p = [x for _, x, _ in filas]
    h = [x for _, _, x in filas]
    fig, ax = plt.subplots(figsize=(10, 4.5))
    barras = ax.bar(range(len(p)), p, color="#c0504d")
    for b, pi, hi in zip(barras, p, h):
        ax.text(b.get_x() + b.get_width() / 2, pi + 0.02,
                f"{pi:.2f}\nH={hi:.2f}", ha="center", fontsize=8)
    ax.set_xticks(range(len(p))); ax.set_xticklabels(etiquetas, fontsize=8)
    ax.set_ylim(0, 1); ax.set_ylabel("P(Escasez = si)")
    ax.set_title("Probabilidad de escasez segun el contexto (H = entropia en bits)")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout(); fig.savefig(ruta, dpi=150); plt.close(fig)


def dibujar_pregunta6(ruta, red):
    p, _ = pregunta6(red)
    fig, ax = plt.subplots(figsize=(6, 4))
    for clima, color in [("seco", "#4f81bd"), ("lluvia", "#1f3b63")]:
        ys = [p[(h, clima)] for h in ESTADOS["Hora"]]
        ax.plot(ESTADOS["Hora"], ys, "o-", color=color, label=f"clima: {clima}", lw=2)
        for x, y in zip(ESTADOS["Hora"], ys):
            ax.annotate(f"{y:.2f}", (x, y), textcoords="offset points",
                        xytext=(8, -4), fontsize=9)
    ax.set_ylabel("P(Demanda = alta)"); ax.set_ylim(0, 0.7)
    ax.set_title("Pregunta 6: lluvia y hora punta por separado\n"
                 "(lineas casi paralelas = efectos casi aditivos)", fontsize=10)
    ax.legend(); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(ruta, dpi=150); plt.close(fig)


if __name__ == "__main__":
    os.makedirs(CARPETA, exist_ok=True)
    red = construir_red()
    dibujar_dag(os.path.join(CARPETA, "dag.png"))
    dibujar_escasez(os.path.join(CARPETA, "escasez_contexto.png"), red)
    dibujar_pregunta6(os.path.join(CARPETA, "pregunta6.png"), red)
    print("Figuras guardadas en", CARPETA)
