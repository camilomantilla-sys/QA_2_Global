"""
Que lee QA de cada Traffic Sheet, formato por formato.

Van a seguir llegando TS viejas y nuevas, y el formato volvera a
cambiar el ano que viene. Este test deja fijado lo que la app entiende
hoy de cada una, para que un arreglo pensado para un formato nuevo no
rompa en silencio uno que ya funcionaba.

COMO SE USA
-----------
1. Deja la TS en `tests/fixtures/ts/`. Las hojas de calculo NO se
   suben a git (llevan datos de cliente): la carpeta esta ignorada.
2. Corre este archivo. La primera vez escribe el resumen de esa TS
   en `<nombre>.expected.json` y no falla.
3. Mira ese JSON: es lo que QA entendio. Si algo esta mal -- una
   columna sin mapear que deberia estarlo, filas de menos, fechas sin
   parsear -- ahi se ve, y es lo que hay que arreglar en el parser.
4. Cuando este bien, sube el JSON. Es estructura, no contenido: no
   lleva ni un valor de celda.

A partir de ahi, cualquier cambio en el parser que altere la lectura
de esa TS sale por pantalla, campo a campo.

Run with pytest, or directly:
    python tests/test_ts_reading.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.ts_snapshot import differences, summarise_ts  # noqa: E402
from parsers.ts_parser import parse_ts  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "ts"
SPREADSHEETS = ("*.xlsx", "*.xlsm", "*.xls")


def traffic_sheets() -> list[Path]:
    if not FIXTURES.exists():
        return []
    found: list[Path] = []
    for pattern in SPREADSHEETS:
        found += [p for p in FIXTURES.glob(pattern)
                  if not p.name.startswith("~$")]
    return sorted(found)


def snapshots_without_a_sheet() -> list[Path]:
    """
    Resumenes guardados cuya hoja de calculo no esta aqui.

    Es lo normal en una maquina recien clonada: los resumenes viajan
    por git y las hojas no. No es un fallo, pero decirlo evita la
    duda de "y esto por que no comprueba nada".
    """
    if not FIXTURES.exists():
        return []
    orphans = []
    for snapshot in sorted(FIXTURES.glob("*.expected.json")):
        if not FIXTURES.joinpath(snapshot.name[:-len(".expected.json")]).exists():
            orphans.append(snapshot)
    return orphans


def check_one(path: Path) -> tuple[str, list[str]]:
    """
    Devuelve (veredicto, diferencias) para una TS.

    Veredicto: "nuevo" la primera vez, "ok" si lee igual que el
    resumen guardado, "cambio" si lee distinto.
    """
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        actual = summarise_ts(parse_ts(path))

    expected_path = path.with_suffix(path.suffix + ".expected.json")
    if not expected_path.exists():
        expected_path.write_text(
            json.dumps(actual, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return "nuevo", []

    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    diff = differences(expected, actual)
    return ("ok" if not diff else "cambio"), diff


def test_every_traffic_sheet_reads_the_same_as_before():
    changed: list[str] = []
    for path in traffic_sheets():
        verdict, diff = check_one(path)
        if verdict == "cambio":
            changed.append(path.name)
            for line in diff:
                print(f"    {path.name}: {line}")
    assert not changed, (
        "QA lee estas Traffic Sheets distinto que antes: "
        + ", ".join(changed)
        + ". Si el cambio es correcto, borra su .expected.json y "
        "vuelve a correr para fijar la lectura nueva."
    )


def test_the_snapshot_carries_no_client_data():
    # Esto acaba en git. Nombres de campana, de placement y de sitio
    # no entran: solo estructura y conteos.
    from core.ts_snapshot import summarise_ts as _s

    source = Path(__file__).resolve().parents[1] / "core" / "ts_snapshot.py"
    body = source.read_text(encoding="utf-8")
    assert "campaign_info_fields" in body
    assert "result.campaign_info.values" not in body
    assert '"campaign_info":' not in body
    # los contactos entran como numero, no como lista
    assert "len(result.site_contacts)" in body
    assert _s is not None


def test_a_missing_fixtures_folder_is_not_a_failure():
    # El repo no lleva hojas de calculo, asi que en una maquina
    # recien clonada esto no tiene nada que mirar y no debe fallar.
    assert isinstance(traffic_sheets(), list)


if __name__ == "__main__":
    orphans = snapshots_without_a_sheet()
    sheets = traffic_sheets()

    if not sheets:
        print(f"No hay Traffic Sheets en {FIXTURES}")
        if orphans:
            print()
            print("Hay resumenes guardados cuya hoja no esta aqui. Las "
                  "hojas no se suben a git, asi que para comprobar una "
                  "tienes que dejarla en esa carpeta con ese mismo "
                  "nombre:")
            for snapshot in orphans:
                print(f"    {snapshot.name[:-len('.expected.json')]}")
        print()
        print("O deja cualquier otra TS ahi y vuelve a correr para "
              "fijar su lectura.")
        sys.exit(0)

    print(f"{len(sheets)} Traffic Sheet(s) en {FIXTURES}\n")
    failed = 0
    for sheet in sheets:
        verdict, diff = check_one(sheet)
        if verdict == "nuevo":
            print(f"nuevo   {sheet.name}")
            print("        resumen escrito -- revisalo y subelo")
        elif verdict == "ok":
            print(f"ok      {sheet.name}")
        else:
            failed += 1
            print(f"CAMBIO  {sheet.name}")
            for line in diff:
                print(f"          {line}")

    for snapshot in orphans:
        print(f"falta   {snapshot.name[:-len('.expected.json')]}")
        print("        hay resumen pero no la hoja -- nada que comprobar")

    print()
    if failed:
        print(f"{failed} Traffic Sheet(s) se leen distinto que antes.")
        print("Si el cambio es correcto, borra su .expected.json y "
              "vuelve a correr.")
        sys.exit(1)
    print("Todas se leen igual que antes.")
