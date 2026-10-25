"""
red.py - Capa 2: Red bayesiana de factores contextuales
Persona 2 (Analista bayesiano/a)

Que modela
----------
Como el contexto (hora, clima, eventos, trafico, costos) cambia la
demanda, la oferta y la probabilidad de escasez.

    Contexto (nodos raiz):  Hora   Clima   Evento   Costos
    Intermedio:             Trafico   <- Hora, Clima
    Mercado:                Demanda   <- Hora, Clima, Evento
                            Oferta    <- Clima, Trafico, Costos
    Resultado:              Escasez   <- Demanda, Oferta

Aristas: Hora->Trafico, Clima->Trafico, Hora->Demanda, Clima->Demanda,
Evento->Demanda, Clima->Oferta, Trafico->Oferta, Costos->Oferta,
Demanda->Escasez, Oferta->Escasez.

Precio y Servicios realizados (Figura 2 del documento) NO estan en la red:
los calcula el modelo de Euler (Persona 1) con la demanda y la oferta que
entrega esta red. Asi cada capa hace una sola cosa.

Como se representa (igual que en clase, sin librerias)
------------------------------------------------------
Cada variable tiene una lista de estados y una lista de padres.
TABLAS[var] es un diccionario:
    clave  = tupla con los estados de los padres (en el orden de PADRES[var])
    valor  = lista de probabilidades, una por estado de la variable
Ejemplo: TABLAS["Trafico"][("punta", "lluvia")] = [0.15, 0.85]
         -> P(Trafico=bajo | punta, lluvia) = 0.15
         -> P(Trafico=alto | punta, lluvia) = 0.85
Cada lista debe sumar 1 (lo revisa validar_red()).

Todas las probabilidades son SUPUESTOS EXPERTOS iniciales, cada uno con su
justificacion. Las marcadas "PENDIENTE (Persona 4)" se reemplazan cuando
haya datos reales, usando estimar_desde_datos() (al final del archivo).
"""

import math
from itertools import product

# ---------------------------------------------------------------------------
# 1. Variables, estados y padres
# ---------------------------------------------------------------------------
ESTADOS = {
    "Hora":    ["valle", "punta"],
    "Clima":   ["seco", "lluvia"],
    "Evento":  ["no", "si"],
    "Costos":  ["normal", "alto"],
    "Trafico": ["bajo", "alto"],
    "Demanda": ["baja", "media", "alta"],
    "Oferta":  ["baja", "media", "alta"],
    "Escasez": ["no", "si"],
}

PADRES = {
    "Hora":    [],
    "Clima":   [],
    "Evento":  [],
    "Costos":  [],
    "Trafico": ["Hora", "Clima"],
    "Demanda": ["Hora", "Clima", "Evento"],
    "Oferta":  ["Clima", "Trafico", "Costos"],
    "Escasez": ["Demanda", "Oferta"],
}

# Orden topologico: cada variable aparece despues de sus padres.
# Lo usan la probabilidad conjunta y el muestreo Monte Carlo.
ORDEN = ["Hora", "Clima", "Evento", "Costos", "Trafico", "Demanda", "Oferta", "Escasez"]

# Justificacion de cada arista (para el informe y la defensa oral).
JUSTIFICACION_ARISTAS = {
    ("Hora", "Trafico"):    "En hora punta hay mas vehiculos en la calle.",
    ("Clima", "Trafico"):   "La lluvia reduce la velocidad y congestiona las vias.",
    ("Hora", "Demanda"):    "Entrada y salida de trabajo y colegios concentra los viajes.",
    ("Clima", "Demanda"):   "Con lluvia la gente evita caminar o esperar el micro.",
    ("Evento", "Demanda"):  "Un evento masivo genera muchos viajes al mismo lugar y hora.",
    ("Clima", "Oferta"):    "Algunos conductores no salen a trabajar con lluvia (escenario C).",
    ("Trafico", "Oferta"):  "Con trafico cada vehiculo completa menos viajes por hora.",
    ("Costos", "Oferta"):   "Si sube el combustible, a menos conductores les conviene salir.",
    ("Demanda", "Escasez"): "Mas pasajeros aumenta el riesgo de que falten vehiculos.",
    ("Oferta", "Escasez"):  "Menos vehiculos aumenta el riesgo de que falten vehiculos.",
}

# ---------------------------------------------------------------------------
# 2. Tablas de probabilidad condicional (supuestos expertos)
# ---------------------------------------------------------------------------
TABLAS = {
    # --- Nodos raiz: probabilidad "a priori" de cada contexto -------------
    # PENDIENTE (Persona 4): reemplazar por frecuencias observadas.
    # Hora: ~6 de 24 horas son punta (7-9, 12-14, 18-20) -> 6/24 = 0.25
    "Hora":   {(): [0.75, 0.25]},
    # Clima: Cochabamba tiene lluvias concentradas en dic-mar y el resto del
    # ano es mayormente seco. Supuesto: 15 % de los intervalos con lluvia.
    "Clima":  {(): [0.85, 0.15]},
    # Evento masivo (partido, concierto, feria) en un intervalo dado: 10 %.
    "Evento": {(): [0.90, 0.10]},
    # Costos altos (alza o escasez de combustible): 30 % del tiempo.
    "Costos": {(): [0.70, 0.30]},

    # --- Trafico | Hora, Clima   estados: [bajo, alto] --------------------
    # La hora punta pesa mas que la lluvia; las dos juntas casi garantizan
    # trafico alto.
    "Trafico": {
        ("valle", "seco"):   [0.80, 0.20],
        ("valle", "lluvia"): [0.55, 0.45],
        ("punta", "seco"):   [0.35, 0.65],
        ("punta", "lluvia"): [0.15, 0.85],
    },

    # --- Demanda | Hora, Clima, Evento   estados: [baja, media, alta] -----
    # Cada factor (punta, lluvia, evento) mueve probabilidad hacia "alta".
    # Caso base (valle, seco, sin evento) = dia normal: casi nunca alta.
    # Peor caso (punta, lluvia, evento) = "viernes 19:00 con lluvia y
    # evento" del documento: 75 % alta.
    "Demanda": {
        ("valle", "seco",   "no"): [0.50, 0.40, 0.10],
        ("valle", "seco",   "si"): [0.20, 0.45, 0.35],
        ("valle", "lluvia", "no"): [0.30, 0.45, 0.25],
        ("valle", "lluvia", "si"): [0.10, 0.35, 0.55],
        ("punta", "seco",   "no"): [0.15, 0.50, 0.35],
        ("punta", "seco",   "si"): [0.05, 0.35, 0.60],
        ("punta", "lluvia", "no"): [0.07, 0.38, 0.55],
        ("punta", "lluvia", "si"): [0.03, 0.22, 0.75],
    },

    # --- Oferta | Clima, Trafico, Costos   estados: [baja, media, alta] ---
    # Cada factor adverso mueve probabilidad hacia oferta "baja". La lluvia
    # es el factor mas fuerte (conductores que no salen).
    "Oferta": {
        ("seco",   "bajo", "normal"): [0.10, 0.40, 0.50],
        ("seco",   "bajo", "alto"):   [0.20, 0.45, 0.35],
        ("seco",   "alto", "normal"): [0.25, 0.45, 0.30],
        ("seco",   "alto", "alto"):   [0.35, 0.45, 0.20],
        ("lluvia", "bajo", "normal"): [0.30, 0.45, 0.25],
        ("lluvia", "bajo", "alto"):   [0.40, 0.42, 0.18],
        ("lluvia", "alto", "normal"): [0.50, 0.35, 0.15],
        ("lluvia", "alto", "alto"):   [0.60, 0.30, 0.10],
    },

    # --- Escasez | Demanda, Oferta   estados: [no, si] --------------------
    # Regla: depende de cuantos niveles supera la demanda a la oferta,
    # d = nivel(Demanda) - nivel(Oferta):
    #   d=+2 -> 0.95   d=+1 -> 0.75   d=0 -> 0.25   d=-1 -> 0.08   d=-2 -> 0.02
    # (con d=0 queda 25 % por los choques aleatorios de demanda).
    # Se completa abajo con _tabla_escasez().
}


def _tabla_escasez():
    p_si_por_diferencia = {2: 0.95, 1: 0.75, 0: 0.25, -1: 0.08, -2: 0.02}
    niveles = {"baja": 0, "media": 1, "alta": 2}
    tabla = {}
    for d, s in product(ESTADOS["Demanda"], ESTADOS["Oferta"]):
        p_si = p_si_por_diferencia[niveles[d] - niveles[s]]
        tabla[(d, s)] = [round(1 - p_si, 2), p_si]
    return tabla


TABLAS["Escasez"] = _tabla_escasez()


# ---------------------------------------------------------------------------
# 3. Funciones basicas
# ---------------------------------------------------------------------------
def validar_red(tablas=None):
    """Revisa que cada tabla tenga todas las combinaciones de padres y que
    cada lista de probabilidades sea no negativa y sume 1."""
    tablas = tablas or TABLAS
    for var in ORDEN:
        combinaciones = list(product(*[ESTADOS[p] for p in PADRES[var]]))
        for combo in combinaciones:
            if combo not in tablas[var]:
                raise ValueError(f"Falta la columna {combo} en la tabla de {var}")
            probs = tablas[var][combo]
            if len(probs) != len(ESTADOS[var]):
                raise ValueError(f"{var}{combo}: se esperaban {len(ESTADOS[var])} valores")
            if min(probs) < 0 or not math.isclose(sum(probs), 1, abs_tol=1e-9):
                raise ValueError(f"{var}{combo} no suma 1: {probs}")
    return True


def construir_red(tablas=None):
    """Devuelve la red como diccionario (estados, padres, orden, tablas),
    ya validada. Es lo que reciben consultas.py y traduccion.py."""
    tablas = tablas or TABLAS
    validar_red(tablas)
    return {"estados": ESTADOS, "padres": PADRES, "orden": ORDEN, "tablas": tablas}


def prob_condicional(red, var, valor, asignacion):
    """P(var = valor | padres), leyendo los padres desde `asignacion`."""
    combo = tuple(asignacion[p] for p in red["padres"][var])
    i = red["estados"][var].index(valor)
    return red["tablas"][var][combo][i]


def prob_conjunta(red, asignacion):
    """Regla de la cadena de una red bayesiana:
    P(x1, ..., xn) = producto de P(xi | padres(xi))."""
    p = 1.0
    for var in red["orden"]:
        p *= prob_condicional(red, var, asignacion[var], asignacion)
    return p


# ---------------------------------------------------------------------------
# 4. PENDIENTE (Persona 4): estimar las tablas con datos reales
# ---------------------------------------------------------------------------
# Formato esperado: una lista de diccionarios (o un DataFrame de pandas
# convertido con df.to_dict("records")), una fila por intervalo de tiempo,
# con las 8 columnas de ESTADOS ya discretizadas. Ejemplo de una fila:
#   {"Hora": "punta", "Clima": "lluvia", "Evento": "no", "Costos": "normal",
#    "Trafico": "alto", "Demanda": "alta", "Oferta": "baja", "Escasez": "si"}
# Si la Persona 4 trae numeros (solicitudes, vehiculos), usar
# discretizar() con los cortes que se acuerden.

def discretizar(valor, cortes, etiquetas=("baja", "media", "alta")):
    """Convierte un numero en una etiqueta.
    Ej.: discretizar(85, cortes=(40, 70)) -> "alta"
    PENDIENTE (Persona 4): definir los cortes con los datos reales."""
    for corte, etiqueta in zip(cortes, etiquetas):
        if valor <= corte:
            return etiqueta
    return etiquetas[-1]


def estimar_desde_datos(filas, peso_previo=20):
    """Re-estima todas las tablas contando frecuencias en los datos.

    Mezcla el supuesto experto con los datos (estimador bayesiano con
    previa de Dirichlet): el supuesto vale como `peso_previo` observaciones
    ficticias por columna. Con pocos datos manda el supuesto; con muchos,
    mandan los datos. Asi ninguna columna queda en 0/0 si faltan casos.
    """
    nuevas = {}
    for var in ORDEN:
        nuevas[var] = {}
        for combo, previo in TABLAS[var].items():
            conteos = [peso_previo * p for p in previo]
            for fila in filas:
                if tuple(fila[p] for p in PADRES[var]) == combo:
                    conteos[ESTADOS[var].index(fila[var])] += 1
            total = sum(conteos)
            nuevas[var][combo] = [c / total for c in conteos]
    return construir_red(nuevas)


if __name__ == "__main__":
    red = construir_red()
    print("Red valida. Variables y numero de columnas de cada tabla:")
    for v in ORDEN:
        print(f"  {v:<8} padres={PADRES[v]}  columnas={len(TABLAS[v])}")
