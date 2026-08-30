"""
Provenance: cada valor extraido conserva su origen exacto.

Principio P-3: no hay finding sin evidencia reproducible.
Principio P-4: el valor raw nunca se sobrescribe.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Valores que significan "no hay dato" aunque la celda tenga contenido.
PLACEHOLDERS = {"n/a", "na", "-", "--", "tbd", "tbc", "pending", "pendiente", "none", "null"}

# Errores de formula de Excel.
EXCEL_ERRORS = {"#VALUE!", "#REF!", "#NAME?", "#DIV/0!", "#N/A", "#NULL!", "#NUM!"}

@dataclass(frozen=True)
class CellRef:
    """Coordenada absoluta de una celda."""
    doc: str
    sheet: str
    row: int
    col: int
    col_letter: str

    def __str__(self) -> str:
        return f"{self.doc}!{self.sheet}!{self.col_letter}{self.row}"

@dataclass
class Cell:
    """Una celda leida, con todo lo necesario para auditarla."""
    ref: CellRef
    raw: Any = None
    text: str = ""
    excel_type: str = "empty"      # n | s | d | b | f | e | empty
    fill_rgb: str | None = None    # 'AARRGGBB' | 'IDX:n' | 'THEME:n:tint'
    hyperlink: str | None = None
    inherited_from_row: int | None = None   # heredado por celda combinada
    is_error: bool = False

    @property
    def is_empty(self) -> bool:
        return self.text == ""

    @property
    def is_placeholder(self) -> bool:
        """'N/A' no es un dato: es la ausencia de dato escrita a mano."""
        return self.text.strip().lower() in PLACEHOLDERS

    @property
    def has_value(self) -> bool:
        """True solo si hay dato real y utilizable."""
        return not self.is_empty and not self.is_placeholder and not self.is_error

@dataclass
class Anomaly:
    """
    Problema de EXTRACCION, no de QA.
    Nunca se mezcla con findings de negocio (evita el bug B19/FP-20).
    """
    code: str
    severity: str          # FATAL | WARNING | INFO
    message: str
    ref: CellRef | None = None
    detail: dict[str, Any] = field(default_factory=dict)