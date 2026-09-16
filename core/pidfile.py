"""
QA2 deja escrito su numero de proceso, para que se le pueda encontrar.

Encontrar QA2 en Windows resulto ser el problema. Buscarlo por puerto
fallaba en cuanto arrancaba en otro; buscarlo por linea de comandos
necesitaba `wmic`, que Microsoft ya quito de Windows 11; y hacerlo
desde un .vbs se topa con la directiva de IT que bloquea Windows Script
Host -- "This script is blocked by IT policy", que es donde se quedo la
companera de Camilo.

Un archivo con el PID no necesita ninguna de esas tres cosas. Lo
escribe la app al arrancar y lo leen los .bat con `tasklist` y
`taskkill`, que son parte de Windows desde siempre y no los bloquea
nadie.

El riesgo conocido es un PID viejo: el proceso murio y Windows reuso el
numero para otra cosa. Por eso quien lo lee comprueba SIEMPRE que ese
PID sea todavia un python antes de matarlo.
"""
from __future__ import annotations

import os
from pathlib import Path


def pid_path(root: Path | None = None) -> Path:
    """
    Siempre junto a la app, nunca en QA2_OUTPUT_DIR.

    Los .bat tienen que encontrarlo sin saber nada del entorno, y si
    esto siguiera a la carpeta compartida, dos personas escribirian su
    PID en el mismo archivo.
    """
    root = root or Path(__file__).resolve().parents[1]
    return root / "logs" / "qa2.pid"


def write_pid(root: Path | None = None) -> Path | None:
    """
    Anota el proceso actual. No falla nunca: QA2 tiene que arrancar
    aunque no se pueda escribir aqui.
    """
    path = pid_path(root)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(os.getpid()), encoding="utf-8")
        return path
    except OSError:
        return None


def read_pid(root: Path | None = None) -> int | None:
    """El PID anotado, o None si no hay o no se entiende."""
    try:
        text = pid_path(root).read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return int(text) if text.isdigit() else None


def clear_pid(root: Path | None = None) -> None:
    try:
        pid_path(root).unlink()
    except OSError:
        pass
