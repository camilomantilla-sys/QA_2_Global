"""
Leer un session bundle (.zip) sin interfaz.

El bundle lo arma la app de Streamlit con "Save session bundle": la TS,
los exports, los tags, los archivos de DV y las capturas de una
solicitud, mas un manifest.json con la cuenta, el perfil y el registro
de implementacion (QA1). Quien hace el QA2 lo carga y no vuelve a subir
nada.

Formato (el mismo desde 1.0.x):

    manifest.json
    files/ts/<nombre>          files/pc/<nombre>          files/pl/<nombre>
    files/tags/<n>_<nombre>    files/dv/<n>_<nombre>      files/evidence/<n>_<nombre>

En el manifest, ts/pc/pl son un nombre; tags, dv y evidence son listas
de {"name", "stored_as"}. Un bundle viejo guardaba DV como un nombre
suelto, y se sigue leyendo.
"""
from __future__ import annotations

import io
import json
import zipfile
from dataclasses import dataclass, field

#: Un bundle real ronda unos MB; esto deja margen sin abrir un zip bomba.
MAX_UNPACKED = 200 * 1024 * 1024


class BundleError(ValueError):
    """El archivo no es un session bundle que QA2 pueda abrir."""


@dataclass
class Bundle:
    manifest: dict = field(default_factory=dict)
    #: slot -> lista de (nombre original, bytes). ts/pc/pl llevan uno.
    files: dict[str, list[tuple[str, bytes]]] = field(default_factory=dict)

    def one(self, slot: str) -> tuple[str, bytes] | None:
        items = self.files.get(slot) or []
        return items[0] if items else None


def read_bundle(data: bytes) -> Bundle:
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise BundleError("This is not a session bundle (.zip).") from exc

    with archive:
        if sum(info.file_size for info in archive.infolist()) > MAX_UNPACKED:
            raise BundleError("This bundle is too large to open.")
        try:
            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        except KeyError as exc:
            raise BundleError("This .zip has no manifest.json, so it is not a QA2 session bundle.") from exc
        except (ValueError, UnicodeDecodeError) as exc:
            raise BundleError("The bundle's manifest.json can't be read.") from exc
        if not isinstance(manifest, dict):
            raise BundleError("The bundle's manifest.json can't be read.")

        listed = manifest.get("files") or {}

        def read(path: str) -> bytes | None:
            try:
                return archive.read(path)
            except KeyError:
                return None

        bundle = Bundle(manifest=manifest)
        for slot in ("ts", "pc", "pl"):
            name = listed.get(slot)
            if isinstance(name, str) and name:
                content = read(f"files/{slot}/{name}")
                if content is not None:
                    bundle.files[slot] = [(name, content)]

        for slot in ("tags", "dv", "evidence"):
            entries = listed.get(slot) or []
            if isinstance(entries, str):
                entries = [{"name": entries, "stored_as": entries}]
            got = []
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                name, stored = entry.get("name"), entry.get("stored_as")
                if not name or not stored:
                    continue
                content = read(f"files/{slot}/{stored}")
                if content is not None:
                    got.append((str(name), content))
            if got:
                bundle.files[slot] = got
    return bundle
