"""
Pegar capturas con Ctrl+V en la seccion de evidencia (FB-04).

Antes habia que guardar cada captura, buscarla en la carpeta y subirla.
Ahora se pega. Las pegadas se suman a las subidas y siguen el mismo
camino: PDF, Excel y session bundle.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path

import streamlit.components.v1 as components

_COMPONENT = components.declare_component(
    "qa2_paste_image",
    path=str(Path(__file__).resolve().parent / "components" / "paste_image"),
)

#: Lo mismo que acepta el cargador de evidencia.
ALLOWED_TYPES = {"image/png", "image/jpeg"}


@dataclass(frozen=True)
class PastedImage:
    """Se comporta como un archivo subido: .name, .size y .getvalue()."""

    name: str
    data: bytes

    @property
    def size(self) -> int:
        return len(self.data)

    def getvalue(self) -> bytes:
        return self.data

    def getbuffer(self):
        return memoryview(self.data)


def decode(value) -> list[PastedImage]:
    """Lo que manda el componente, a archivos. Lo que no es imagen se ignora."""
    images: list[PastedImage] = []
    for item in value or []:
        if not isinstance(item, dict) or item.get("type") not in ALLOWED_TYPES:
            continue
        try:
            data = base64.b64decode(item.get("data", ""), validate=True)
        except (ValueError, TypeError):
            continue
        name = Path(str(item.get("name") or "pasted_screenshot.png")).name
        if data:
            images.append(PastedImage(name=name, data=data))
    return images


def paste_images(key: str, reset_token: int) -> list[PastedImage]:
    """La zona para pegar. Cambiar `reset_token` la vacia (Start over)."""
    return decode(_COMPONENT(key=key, reset_token=reset_token, default=[]))
