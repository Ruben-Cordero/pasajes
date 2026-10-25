"""
Genera datos SINTETICOS para el Escenario E (precio dinamico de transporte, Cochabamba).

Que hace:
  1. Crea crudo/cotizaciones_indrive.csv simulando 7 dias de cotizaciones en una ruta fija.
     El precio, la demanda y la oferta salen del MISMO modelo de Euler del proyecto:
         D_k = D0 + beta (p_ref - p_k) + eps_k
         S_k = S0 + gamma (p_k - p_costo)
         p_{k+1} = max(p_costo, p_k + dt * alpha * (D_k - S_k))
     con D0 y S0 que dependen del contexto (hora punta, lluvia, evento, trafico).
     Luego se agrega ruido de medicion (lo que "se ve" en la app).
  2. Agrega a crudo/lluvia_senamhi.csv unas filas SUPUESTAS (sep/oct 2026), marcadas como tales.

Todas las filas generadas llevan fuente = "sintetico" (o "supuesto" en el clima).
NO son datos reales. Reemplazar por mediciones propias cuando existan.

Uso:  python generar_sintetico.py
"""
import csv
import os
from datetime import datetime, timedelta

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
CRUDO = os.path.join(AQUI, "crudo")

# ---------------------------------------------------------------- parametros
SEMILLA = 2026

# Parametros del modelo (los del documento del caso, Escenario A)
ALPHA, BETA, GAMMA = 0.1, 2.0, 1.5
P_REF, P_COSTO = 10.0, 5.0
DT = 5.0  # minutos

# Ruido
SIGMA_EPS = 1.0      # choque aleatorio de demanda por intervalo (proceso)
SIGMA_PRECIO = 0.4   # error al leer el precio (Bs)
SIGMA_SOLIC = 2.5    # error en el conteo de solicitudes
SIGMA_VEH = 2.0      # error en el conteo de vehiculos
REDONDEO_PRECIO = 0.5  # las apps muestran precios en pasos de 0.5 Bs

# Efectos del contexto sobre D0 y S0 (supuestos, ver README)
D0_BASE, S0_BASE = 50.0, 48.0
EF_D_PUNTA, EF_D_LLUVIA, EF_D_EVENTO, EF_D_TRAFICO = 12.0, 10.0, 10.0, 3.0
EF_S_LLUVIA, EF_S_TRAFICO = -6.0, -4.0
AJUSTE_DIA = {5: -2.0, 6: -6.0}  # sabado, domingo (lunes=0)

# Calendario de la semana simulada: lunes 26-oct-2026 a domingo 1-nov-2026
INICIO = datetime(2026, 10, 26)
N_DIAS = 7
HORA_INI, HORA_FIN = 6, 22  # 06:00 a 22:00

RUTA = "ucb_plaza_14_septiembre"

# Ventanas de lluvia y evento (minutos desde medianoche) por fecha
LLUVIA = {  # 2 de 7 dias con lluvia
    "2026-10-27": (17 * 60, 19 * 60 + 30),
    "2026-10-30": (18 * 60 + 15, 20 * 60 + 15),
}
EVENTO = {  # viernes: evento masivo en el centro, coincide con lluvia
    "2026-10-30": (18 * 60, 21 * 60 + 30),
}
PUNTA_SEMANA = [(7 * 60, 9 * 60), (12 * 60 + 30, 14 * 60), (17 * 60 + 30, 20 * 60)]
PUNTA_FINDE = [(18 * 60, 21 * 60)]


def en_ventana(minuto, ventanas):
    return any(a <= minuto <= b for a, b in ventanas)


def suavizar(x, ventana):
    """Media movil centrada: hace que los cambios de contexto sean graduales."""
    if ventana <= 1:
        return x.astype(float)
    pad = ventana // 2
    xp = np.pad(x.astype(float), pad, mode="edge")
    k = np.ones(ventana) / ventana
    return np.convolve(xp, k, mode="same")[pad:-pad or None][: len(x)]


def simular_dia(fecha, rng):
    """Devuelve una lista de filas (dict) para un dia."""
    clave = fecha.strftime("%Y-%m-%d")
    n = (HORA_FIN - HORA_INI) * 60 // int(DT) + 1
    minutos = HORA_INI * 60 + np.arange(n) * int(DT)
    dia_sem = fecha.weekday()
    finde = dia_sem >= 5

    punta = np.array([en_ventana(m, PUNTA_FINDE if finde else PUNTA_SEMANA) for m in minutos])
    lluvia = np.array([en_ventana(m, [LLUVIA[clave]]) if clave in LLUVIA else False for m in minutos])
    evento = np.array([en_ventana(m, [EVENTO[clave]]) if clave in EVENTO else False for m in minutos])

    # Trafico: se decide por bloques de 30 min (6 pasos), con mas probabilidad en punta/lluvia/evento
    trafico = np.zeros(n, dtype=bool)
    for ini in range(0, n, 6):
        sl = slice(ini, min(ini + 6, n))
        p = 0.15
        if punta[sl].mean() > 0.5:
            p = 0.75
        if lluvia[sl].mean() > 0.5:
            p = min(0.95, p + 0.20)
        if evento[sl].mean() > 0.5:
            p = min(0.95, p + 0.15)
        trafico[sl] = rng.random() < p

    # Suavizado (cambios graduales de contexto)
    s_punta = suavizar(punta, 6)
    s_lluvia = suavizar(lluvia, 3)
    s_evento = suavizar(evento, 6)
    s_trafico = suavizar(trafico, 6)

    D0 = (D0_BASE + AJUSTE_DIA.get(dia_sem, 0.0)
          + EF_D_PUNTA * s_punta + EF_D_LLUVIA * s_lluvia
          + EF_D_EVENTO * s_evento + EF_D_TRAFICO * s_trafico)
    S0 = S0_BASE + EF_S_LLUVIA * s_lluvia + EF_S_TRAFICO * s_trafico

    # Euler con choque de demanda
    p = np.zeros(n)
    D = np.zeros(n)
    S = np.zeros(n)
    p[0] = P_REF
    eps = rng.normal(0.0, SIGMA_EPS, n)
    for k in range(n):
        D[k] = max(0.0, D0[k] + BETA * (P_REF - p[k]) + eps[k])
        S[k] = max(0.0, S0[k] + GAMMA * (p[k] - P_COSTO))
        if k + 1 < n:
            p[k + 1] = max(P_COSTO, p[k] + DT * ALPHA * (D[k] - S[k]))

    # Observaciones con ruido
    precio_obs = p + rng.normal(0.0, SIGMA_PRECIO, n)
    precio_obs = np.maximum(P_COSTO, np.round(precio_obs / REDONDEO_PRECIO) * REDONDEO_PRECIO)
    solic_obs = np.maximum(0, np.round(D + rng.normal(0.0, SIGMA_SOLIC, n))).astype(int)
    veh_obs = np.maximum(0, np.round(S + rng.normal(0.0, SIGMA_VEH, n))).astype(int)

    filas = []
    for k in range(n):
        ts = fecha + timedelta(minutes=int(minutos[k]))
        filas.append({
            "timestamp": ts.strftime("%Y-%m-%d %H:%M"),
            "precio_bs": f"{precio_obs[k]:.1f}",
            "solicitudes": int(solic_obs[k]),
            "vehiculos": int(veh_obs[k]),
            "lluvia": "lluvia" if lluvia[k] else "seco",
            "trafico": "alto" if trafico[k] else "bajo",
            "evento": int(evento[k]),
            "ruta": RUTA,
            "fuente": "sintetico",
        })
    return filas


def escribir_cotizaciones():
    rng = np.random.default_rng(SEMILLA)
    filas = []
    for i in range(N_DIAS):
        filas += simular_dia(INICIO + timedelta(days=i), rng)
    ruta = os.path.join(CRUDO, "cotizaciones_indrive.csv")
    campos = ["timestamp", "precio_bs", "solicitudes", "vehiculos",
              "lluvia", "trafico", "evento", "ruta", "fuente"]
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(filas)
    print(f"cotizaciones_indrive.csv: {len(filas)} filas")


# Filas SUPUESTAS de clima (no vienen de ningun PDF). Mismas 12 columnas que el archivo real.
SUPUESTAS = [
    # periodo_inicio, periodo_fin, estacion, variable, valor, unidad, normal, record, pagina
    ("2026-09-01", "2026-09-30", "cochabamba_aeropuerto", "precipitacion_acumulada", "18", "mm", "20", ""),
    ("2026-09-01", "2026-09-30", "cochabamba_aeropuerto", "dias_con_lluvia", "4", "dias", "", ""),
    ("2026-10-01", "2026-10-31", "cochabamba_aeropuerto", "precipitacion_acumulada", "38", "mm", "35", ""),
    ("2026-10-01", "2026-10-31", "cochabamba_aeropuerto", "dias_con_lluvia", "9", "dias", "", ""),
    ("2026-10-01", "2026-10-31", "cochabamba_aeropuerto", "precipitacion_max_24h", "14.0", "mm", "", ""),
]


def completar_lluvia():
    ruta = os.path.join(CRUDO, "lluvia_senamhi.csv")
    with open(ruta, encoding="utf-8") as f:
        lineas = [l.rstrip("\n") for l in f if l.strip()]
    # idempotente: quitar filas supuestas previas
    lineas = [l for l in lineas if ",supuesto," not in l]
    for (ini, fin, est, var, val, uni, normal, rec) in SUPUESTAS:
        lineas.append(",".join([ini, fin, est, var, val, uni, normal, rec,
                                "supuesto", "supuesto_sintetico", "SIN_DOCUMENTO", ""]))
    with open(ruta, "w", encoding="utf-8", newline="") as f:
        f.write("\n".join(lineas) + "\n")
    print(f"lluvia_senamhi.csv: {len(lineas) - 1} filas ({len(SUPUESTAS)} supuestas)")


if __name__ == "__main__":
    os.makedirs(CRUDO, exist_ok=True)
    escribir_cotizaciones()
    completar_lluvia()
