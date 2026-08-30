"""
Motor de fechas. Ataca los bugs B3 y B23.

Estrategia de 4 prioridades:
  1. Celda tipo fecha nativo  -> se toma .date(). Cero ambiguedad.
  2. Texto con componente >12 -> se deduce el orden de la columna.
  3. Texto ambiguo            -> se aplica el orden deducido en (2).
  4. Sin evidencia            -> None + NOT_VERIFIED. Nunca se asume.

Solo fecha calendario. La hora se descarta siempre.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime

from core.normalize import norm_text

_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")
_SEP = re.compile(r"^(\d{1,4})[/\-.](\d{1,4})[/\-.](\d{1,4})")

MDY = "MDY"
DMY = "DMY"
YMD = "YMD"
AMBIGUOUS = "AMBIGUOUS"
ISO = "ISO"
NATIVE = "NATIVE"

@dataclass
class DateColumnResult:
    """Resultado de resolver una columna completa de fechas."""
    values: list[date | None] = field(default_factory=list)
    order: str = AMBIGUOUS
    order_evidence: str = ""
    unparsed: list[tuple[int, str]] = field(default_factory=list)
    native_count: int = 0
    text_count: int = 0
    iso_count: int = 0

def _from_native(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None

def _parts(text: str) -> tuple[int, int, int] | None:
    m = _SEP.match(text)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3))

def _fix_year(y: int) -> int:
    return 2000 + y if y < 100 else y

def _build(a: int, b: int, c: int, order: str) -> date | None:
    try:
        if order == MDY:
            return date(_fix_year(c), a, b)
        if order == DMY:
            return date(_fix_year(c), b, a)
        if order == YMD:
            return date(_fix_year(a), b, c)
    except ValueError:
        return None
    return None

def resolve_date_column(raw_values: list[object], hint: str | None = None) -> DateColumnResult:
    """
    Resuelve una columna de fechas completa.
    Se procesa por columna (no celda a celda) para poder deducir el orden
    a partir de la evidencia de toda la columna.
    """
    res = DateColumnResult()
    res.values = [None] * len(raw_values)

    pending: list[tuple[int, str, tuple[int, int, int]]] = []

    for i, raw in enumerate(raw_values):
        # Prioridad 1: tipo nativo
        native = _from_native(raw)
        if native is not None:
            res.values[i] = native
            res.native_count += 1
            continue

        text = norm_text(str(raw) if raw is not None else "")
        if not text:
            continue
        res.text_count += 1

        # ISO explicito (incluye '2025-11-29T00:00:00.000Z')
        m_iso = _ISO.match(text)
        if m_iso:
            try:
                res.values[i] = date(int(m_iso.group(1)), int(m_iso.group(2)),
                                     int(m_iso.group(3)))
                res.iso_count += 1
            except ValueError:
                res.unparsed.append((i, text))
            continue

        p = _parts(text)
        if p is None:
            res.unparsed.append((i, text))
            continue

        # Serial de Excel guardado como texto
        if len(text) <= 6 and text.isdigit():
            res.unparsed.append((i, text))
            continue

        pending.append((i, text, p))

    # Prioridad 2: deducir el orden con la evidencia de la columna
    order = hint or AMBIGUOUS
    evidence = f"hint={hint}" if hint else ""

    if order == AMBIGUOUS:
        for _, text, (a, b, c) in pending:
            if a > 31:
                order, evidence = YMD, f"'{text}': 1er componente {a} > 31"
                break
            if a > 12 and b <= 12:
                order, evidence = DMY, f"'{text}': 1er componente {a} > 12"
                break
            if b > 12 and a <= 12:
                order, evidence = MDY, f"'{text}': 2do componente {b} > 12"
                break

    res.order = order
    res.order_evidence = evidence

    # Prioridad 3 y 4
    for i, text, (a, b, c) in pending:
        if order == AMBIGUOUS:
            res.unparsed.append((i, text))   # -> NOT_VERIFIED
            continue
        built = _build(a, b, c, order)
        if built is None:
            res.unparsed.append((i, text))
        else:
            res.values[i] = built

    # Etiqueta honesta: si no hubo formatos ambiguos que resolver,
    # el orden no es AMBIGUOUS, es que nunca se necesito deducirlo.
    if not pending:
        if res.iso_count and not res.native_count:
            res.order = ISO
            res.order_evidence = (f"{res.iso_count} valores en formato ISO "
                                  f"(YYYY-MM-DD), inequivoco")
        elif res.native_count and not res.iso_count:
            res.order = NATIVE
            res.order_evidence = f"{res.native_count} celdas con tipo fecha nativo de Excel"
        elif res.native_count or res.iso_count:
            res.order = "MIXED"
            res.order_evidence = f"{res.native_count} nativas + {res.iso_count} ISO"

    return res

def excel_serial_to_date(serial: float) -> date | None:
    """Serial de Excel (base 1900, con el bug historico del 29-feb-1900)."""
    try:
        n = int(serial)
        if n <= 0:
            return None
        if n > 59:
            n -= 1
        return date.fromordinal(date(1899, 12, 31).toordinal() + n)
    except (ValueError, OverflowError):
        return None