"""
Builds the zip that goes to the team.

    python scripts/package_release.py

Leaves QA2-<version>.zip next to the project, prints what went in, what
stayed out and why, and a SHA-256 so the person receiving it can check
they got the same file that was built.

What stays out is the point of this script. Three things must never
travel in a file that gets shared:

  * the Innovid sign-in -- the password and the session cookies;
  * Traffic Sheets and exports, which carry client data;
  * the virtual environment and the Git history, which are big, machine
    specific, and not the product.

Everything else -- the code, the launchers, the editable tables, the
docs -- is what the team needs, so it all goes in.
"""
from __future__ import annotations

import hashlib
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Folders never packaged, matched on any path segment.
SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".vscode",
    ".idea",
    "data",
    "logs",
    "backups",
    "node_modules",
    # Donde build_bundle.py deja lo que arma. Sin esta linea el paquete
    # se copia a si mismo: 157 archivos pasaron a 12.630 y el zip a
    # 1,3 GB.
    "dist",
    # El Python y el navegador que trae un paquete ya armado, por si
    # alguien empaqueta desde una carpeta que ya los tiene.
    "browsers",
}

# Individual files never packaged, matched on the file name.
SKIP_FILES = {
    "innovid_credentials.env",   # the Innovid password
    "innovid_session.json",      # session cookies, as good as the password
    "secrets.toml",              # Streamlit local secrets
    ".DS_Store",
    "Thumbs.db",
}

# Suffixes never packaged. Spreadsheets are client data by default: the
# only ones in the tree are test fixtures and whatever someone left
# lying around, and neither belongs in a file that gets shared.
SKIP_SUFFIXES = {".xlsx", ".xlsm", ".xls", ".pyc", ".pyo", ".log", ".bak"}


def _version() -> str:
    path = ROOT / "VERSION"
    if path.exists():
        text = path.read_text(encoding="utf-8").strip()
        if text:
            return text
    return "dev"


def _reason(path: Path) -> str:
    """Why this file is not going in, or "" if it is."""
    parts = set(path.relative_to(ROOT).parts)
    skipped = parts & SKIP_DIRS
    if skipped:
        return f"{sorted(skipped)[0]}/"
    if path.name in SKIP_FILES:
        return "sign-in or local secret"
    if path.suffix.lower() in SKIP_SUFFIXES:
        return f"*{path.suffix.lower()}"
    if path.name.startswith("~$"):
        return "Excel lock file"
    return ""


def app_files(root: Path = ROOT, skip: Path | None = None) -> list[Path]:
    """
    Los archivos del proyecto que si viajan, y por que se quedan los
    demas. Lo usa tanto el zip de codigo como el paquete autocontenido,
    que no puede tener reglas propias sobre que es un secreto.
    """
    included: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if skip is not None and path.resolve() == skip.resolve():
            continue
        if _reason(path):
            continue
        included.append(path)
    return included


def build(destination: Path | None = None) -> Path:
    version = _version()
    target = destination or (ROOT.parent / f"QA2-{version}.zip")

    included: list[Path] = []
    excluded: dict[str, int] = {}

    for path in sorted(ROOT.rglob("*")):
        if not path.is_file():
            continue
        if path.resolve() == target.resolve():
            continue
        reason = _reason(path)
        if reason:
            excluded[reason] = excluded.get(reason, 0) + 1
            continue
        included.append(path)

    stem = f"QA2-{version}"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in included:
            zf.write(path, Path(stem) / path.relative_to(ROOT))

    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    size_mb = target.stat().st_size / 1_048_576

    print(f"QA2 {version}")
    print(f"  {target}")
    print(f"  {len(included)} files, {size_mb:.1f} MB")
    print(f"  sha256 {digest}")
    print()
    print("  left out:")
    for reason, count in sorted(excluded.items(), key=lambda kv: -kv[1]):
        print(f"    {count:>5}  {reason}")
    print()

    # A packaged sign-in would be the one mistake worth failing over.
    with zipfile.ZipFile(target) as zf:
        names = zf.namelist()
    leaked = [n for n in names if Path(n).name in SKIP_FILES]
    if leaked:
        print(f"  REFUSING: the sign-in is in the zip: {leaked}", file=sys.stderr)
        target.unlink()
        return sys.exit(1)

    print("  checked: no credentials, no session, no spreadsheets.")
    print()
    print("  To share it: upload to the team's SharePoint library and send")
    print("  the link. Whoever receives it unzips the folder and")
    print("  double-clicks run_qa2.bat -- the first run installs what it")
    print("  needs and takes a minute.")
    return target


if __name__ == "__main__":
    build()
