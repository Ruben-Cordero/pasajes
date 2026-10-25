"""
comun.py - Utilidades compartidas por los scripts de la Persona 4
(carpetas de salida, estilo de graficas e importacion de la capa bayesiana).
"""

import os

import matplotlib
matplotlib.use("Agg")  # guarda figuras sin abrir ventanas
import matplotlib.pyplot as plt

from integracion import params as P
from capa2_bayes.red import construir_red, estimar_desde_datos, discretizar
from capa2_bayes.consultas import consultar, entropia
from capa2_bayes import traduccion

COLORES = {"A": "#1f77b4", "B": "#d62728", "C": "#2ca02c", "D": "#9467bd",
           "E": "#ff7f0e"}


def carpetas():
    os.makedirs(P.FIGURAS, exist_ok=True)
    os.makedirs(P.TABLAS, exist_ok=True)


def guardar_figura(fig, nombre):
    carpetas()
    ruta = os.path.join(P.FIGURAS, nombre)
    fig.tight_layout()
    fig.savefig(ruta, dpi=150)
    plt.close(fig)
    return ruta


def guardar_tabla(df, nombre, **kwargs):
    carpetas()
    ruta = os.path.join(P.TABLAS, nombre)
    df.to_csv(ruta, **kwargs)
    return ruta


def evidencia(hora=None, clima=None, evento=None, trafico=None):
    """Arma la evidencia para la red con los nombres de estados de red.py."""
    ev = {}
    if hora is not None:
        ev["Hora"] = hora
    if clima is not None:
        ev["Clima"] = clima
    if evento is not None:
        ev["Evento"] = evento
    if trafico is not None:
        ev["Trafico"] = trafico
    return ev


def evidencia_fila(fila):
    """Evidencia de la red a partir de una fila de escenario_e.csv."""
    return evidencia("punta" if fila["hora_punta"] else "valle",
                     "lluvia" if fila["lluvia"] else "seco",
                     "si" if fila["evento"] else "no",
                     "alto" if fila["trafico_alto"] else "bajo")
