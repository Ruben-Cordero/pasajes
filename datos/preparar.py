"""
Une cotizaciones + clima y deja la tabla lista para las tres capas del proyecto.

Entrada : crudo/cotizaciones_indrive.csv, crudo/lluvia_senamhi.csv
Salida  : procesado/escenario_e.csv
Imprime : estadisticas utiles para calibrar la red bayesiana (terciles, P(escasez | contexto))
          y para fijar parametros del modelo.

Columnas de escenario_e.csv:
  timestamp       fecha y hora ISO (cada 5 min, igual que dt del modelo)
  t_min           minutos desde el inicio de cada dia de medicion (0 = 06:00)
  dia_semana      0 = lunes ... 6 = domingo
  precio_bs       precio observado (p_k con ruido)           -> medicion de Kalman
  solicitudes     solicitudes observadas (D_k con ruido)     -> medicion de Kalman
  vehiculos       vehiculos disponibles observados (S_k)
  escasez         1 si solicitudes - vehiculos >= UMBRAL_ESCASEZ, si no 0 (definicion D > S del documento)
  tarifa_alta     1 si precio_bs >= FACTOR_TARIFA_ALTA * P_REF (surge observable en la app)
  lluvia          1 = lluvia, 0 = seco
  trafico_alto    1 = alto, 0 = bajo
  evento          1 = evento masivo, 0 = no
  hora_punta      1 si cae en una ventana de hora punta (ver HORAS_PUNTA)
  ruta, fuente    se conservan del crudo
"""
import os

import pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
CRUDO = os.path.join(AQUI, "crudo")
PROCESADO = os.path.join(AQUI, "procesado")

UMBRAL_ESCASEZ = 5  # faltan al menos 5 vehiculos para cubrir las solicitudes (~10 %)
P_REF = 10.0              # precio de referencia (Bs), el mismo del modelo
FACTOR_TARIFA_ALTA = 1.3  # tarifa alta = precio >= 1.3 * P_REF
HORAS_PUNTA_SEMANA = [(7 * 60, 9 * 60), (12 * 60 + 30, 14 * 60), (17 * 60 + 30, 20 * 60)]
HORAS_PUNTA_FINDE = [(18 * 60, 21 * 60)]


def es_punta(ts):
    m = ts.hour * 60 + ts.minute
    ventanas = HORAS_PUNTA_FINDE if ts.weekday() >= 5 else HORAS_PUNTA_SEMANA
    return int(any(a <= m <= b for a, b in ventanas))


def main():
    os.makedirs(PROCESADO, exist_ok=True)
    cot = pd.read_csv(os.path.join(CRUDO, "cotizaciones_indrive.csv"), parse_dates=["timestamp"])
    if cot.empty:
        raise SystemExit("cotizaciones_indrive.csv no tiene filas")

    # Limpieza basica
    cot = cot.sort_values("timestamp").drop_duplicates("timestamp").reset_index(drop=True)
    for c in ["precio_bs", "solicitudes", "vehiculos"]:
        cot[c] = pd.to_numeric(cot[c], errors="coerce")
    cot = cot.dropna(subset=["precio_bs"])

    out = pd.DataFrame({
        "timestamp": cot["timestamp"].dt.strftime("%Y-%m-%d %H:%M"),
        "t_min": ((cot["timestamp"] - cot["timestamp"].dt.normalize()).dt.total_seconds() / 60
                  - 6 * 60).astype(int),
        "dia_semana": cot["timestamp"].dt.weekday,
        "precio_bs": cot["precio_bs"],
        "solicitudes": cot["solicitudes"],
        "vehiculos": cot["vehiculos"],
    })
    out["escasez"] = ((out["solicitudes"] - out["vehiculos"]) >= UMBRAL_ESCASEZ).astype(int)
    # Tarifa alta (surge): precio >= 130 % del precio de referencia. Es observable en la app y,
    # a diferencia de D > S, SI depende del contexto (el mercado equilibra D y S via el precio).
    out["tarifa_alta"] = (out["precio_bs"] >= FACTOR_TARIFA_ALTA * P_REF).astype(int)
    out["lluvia"] = (cot["lluvia"].str.strip().str.lower() == "lluvia").astype(int)
    out["trafico_alto"] = (cot["trafico"].str.strip().str.lower() == "alto").astype(int)
    out["evento"] = pd.to_numeric(cot["evento"], errors="coerce").fillna(0).astype(int)
    out["hora_punta"] = cot["timestamp"].apply(es_punta)
    out["ruta"] = cot["ruta"]
    out["fuente"] = cot["fuente"]
    out.to_csv(os.path.join(PROCESADO, "escenario_e.csv"), index=False)
    print(f"escenario_e.csv: {len(out)} filas, {out['timestamp'].nunique()} marcas de tiempo")

    # ---------------- estadisticas para el equipo ----------------
    print("\nTerciles (para los cortes de discretizar() y VALORES_D0/S0):")
    for c in ["solicitudes", "vehiculos", "precio_bs"]:
        q = out[c].quantile([1 / 3, 2 / 3]).round(1).tolist()
        print(f"  {c:12s} min={out[c].min():.1f}  T1={q[0]}  T2={q[1]}  max={out[c].max():.1f}  media={out[c].mean():.2f}")

    print("\nPrecio medio y P(escasez) por contexto:")
    grp = out.groupby(["hora_punta", "lluvia", "evento"]).agg(
        n=("precio_bs", "size"), precio_medio=("precio_bs", "mean"),
        solic_media=("solicitudes", "mean"), veh_medio=("vehiculos", "mean"),
        p_escasez=("escasez", "mean"), p_tarifa_alta=("tarifa_alta", "mean")).round(2)
    print(grp.to_string())

    for var in ["escasez", "tarifa_alta"]:
        print(f"\nP({var} | contexto marginal):")
        for col in ["hora_punta", "lluvia", "evento", "trafico_alto"]:
            r = out.groupby(col)[var].mean().round(3).to_dict()
            print(f"  {col:12s} {r}")
        print(f"  global       {out[var].mean():.3f}")

    viernes = out[(out["timestamp"].str.startswith("2026-10-30 19:"))]
    print(f"\nViernes 30-oct 19:00-19:55 (lluvia + evento): n={len(viernes)}, "
          f"P(escasez)={viernes['escasez'].mean():.2f}, P(tarifa_alta)={viernes['tarifa_alta'].mean():.2f}, "
          f"precio medio={viernes['precio_bs'].mean():.1f} Bs")

    # Clima: prior de lluvia por mes (desde dias_con_lluvia)
    llu = pd.read_csv(os.path.join(CRUDO, "lluvia_senamhi.csv"))
    d = llu[llu["variable"] == "dias_con_lluvia"].copy()
    d["dias_mes"] = (pd.to_datetime(d["periodo_fin"]) - pd.to_datetime(d["periodo_inicio"])).dt.days + 1
    d["p_dia_lluvioso"] = (d["valor"] / d["dias_mes"]).round(2)
    print("\nP(dia lluvioso) por mes (prior del nodo Clima):")
    print(d[["periodo_inicio", "estacion", "valor", "p_dia_lluvioso", "origen_valor"]].to_string(index=False))


if __name__ == "__main__":
    main()
