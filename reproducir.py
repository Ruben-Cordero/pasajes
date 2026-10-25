"""
reproducir.py - Regenera todos los resultados, el informe y la presentacion.

Corre cada paso en orden (el orden importa: decision.py lee las estimaciones
que guarda escenario_e.py y el informe lee todas las tablas de resultados/).
Se detiene en el primer paso que falle.

Uso (desde la raiz):  python reproducir.py
"""

import os
import subprocess
import sys
import time

RAIZ = os.path.dirname(os.path.abspath(__file__))

PASOS = [
    ("Red bayesiana: figuras", ["-m", "capa2_bayes.dibujar"]),
    ("Escenarios A-D y preguntas 1, 3, 4 y 5", ["-m", "integracion.escenarios"]),
    ("Escenario E (datos sinteticos) y pregunta 6", ["-m", "integracion.escenario_e"]),
    ("Monte Carlo Bayes -> Euler", ["-m", "integracion.montecarlo"]),
    ("Regla de decision (pregunta 7)", ["-m", "integracion.decision"]),
    ("Pipeline: viernes 19:00, lluvia y evento", ["main.py"]),
    ("Pipeline: valle seco, red calibrada, solo precio",
     ["main.py", "--hora", "valle", "--clima", "seco", "--evento", "no", "--red", "calibrada",
      "--mediciones", "precio"]),
    ("Pipeline sobre un dia del Escenario E", ["main.py", "--escenario", "E"]),
    ("Informe y presentacion", ["informe/generar_informe.py"]),
]


def main():
    entorno = dict(os.environ, MPLBACKEND="Agg", PYTHONIOENCODING="utf-8")
    inicio = time.time()
    for i, (nombre, args) in enumerate(PASOS, 1):
        print(f"[{i}/{len(PASOS)}] {nombre} ...", flush=True)
        t0 = time.time()
        r = subprocess.run([sys.executable] + args, cwd=RAIZ, env=entorno,
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
                           encoding="utf-8", errors="replace")
        if r.returncode != 0:
            print(r.stderr)
            raise SystemExit(f"Fallo el paso: python {' '.join(args)}")
        print(f"      listo en {time.time() - t0:.0f} s")
    print(f"\nTodo regenerado en {time.time() - inicio:.0f} s. Ver resultados/ e informe/.")


if __name__ == "__main__":
    main()
