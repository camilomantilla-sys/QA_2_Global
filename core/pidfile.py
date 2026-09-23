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
import subprocess
import sys
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


def is_running(root: Path | None = None) -> bool:
    """
    ¿El QA2 de ESTA carpeta sigue vivo?

    Hace falta para no confundirlo con el de otra. Quien tiene el
    puerto 8501 puede ser cualquiera: si alguien conserva la carpeta
    de una version vieja --y la gente las conserva-- arrancar una
    abria el navegador sobre la OTRA, sin decir nada, y la version que
    se veia no era la que se habia abierto.
    """
    pid = read_pid(root)
    return pid is not None and _alive(pid)


def _alive(pid: int) -> bool:
    """
    Si ese PID sigue siendo un python.

    En Windows se pregunta con `tasklist`, como los .bat: es parte del
    sistema desde siempre y la directiva de IT no lo bloquea. NUNCA
    con os.kill(pid, 0), que en Windows no pregunta -- termina el
    proceso.
    """
    if sys.platform == "win32":
        try:
            done = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True, text=True, timeout=5,
                # Sin esto, el lanzador silencioso parpadea una
                # consola negra al arrancar.
                creationflags=0x08000000,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return "python" in (done.stdout or "").lower()

    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True
