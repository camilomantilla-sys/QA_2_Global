"""
Arranca QA2 dejando escrito su numero de proceso.

El PID lo tiene que anotar el proceso que de verdad sirve la
aplicacion, y tiene que estar escrito desde que el servidor levanta --
no desde que alguien abre el navegador.

Ponerlo dentro de app_v2.py no servia: ese codigo corre en la primera
sesion, es decir cuando alguien abre la pagina. Hasta entonces el
servidor esta arriba y "Stop QA2.bat" no encontraba a quien parar.

Asi que se anota aqui, antes de ceder el control a Streamlit, y en el
MISMO proceso: `cli.main()` no lanza otro, de modo que el PID escrito
es exactamente el que hay que matar.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.pidfile import clear_pid, write_pid  # noqa: E402

DEFAULT_PORT = "8501"


def main() -> int:
    write_pid(ROOT)
    try:
        from streamlit.web import cli
    except ImportError:
        print(
            "Streamlit is not installed in this Python.\n"
            "If this is the package handed to the team, the download "
            "may be incomplete -- extract the .zip again."
        )
        return 1

    port = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PORT
    sys.argv = [
        "streamlit", "run", str(ROOT / "ui" / "app_v2.py"),
        "--server.port", port,
    ]
    try:
        return cli.main(standalone_mode=False) or 0
    finally:
        # Que no quede un PID apuntando a un proceso que ya murio: el
        # siguiente arranque lo leeria y creeria que QA2 sigue abierto.
        clear_pid(ROOT)


if __name__ == "__main__":
    sys.exit(main())
