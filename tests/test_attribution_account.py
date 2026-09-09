"""
Quien elige la cuenta manda sobre si hay atribucion que revisar.

El triangulo de atribucion (TS.CGEN == Innovid.Third_Party_ID == sdid
de la URL) solo existe en Adobe. Antes QA2 lo adivinaba mirando si
algun CGEN venia con valor, y bastaba un ejemplo de la plantilla para
que concluyera "esta cuenta si maneja CGEN" y despues reclamara el
dato en cada placement real de Unilever, donde nunca va a existir.

Run with pytest, or directly:
    python tests/test_attribution_account.py
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.findings import FindingsBuffer, Status  # noqa: E402
from core.urls import check_triangle  # noqa: E402
from rules import attribution  # noqa: E402


@dataclass
class _Creative:
    cgen: str = ""


@dataclass
class _Expected:
    cgen: str = ""
    creatives: list = field(default_factory=list)


@dataclass
class _Link:
    triangle: object = None


@dataclass
class _Matched:
    placement_id: str = "PL-1"
    expected: _Expected = field(default_factory=_Expected)
    creative_links: list = field(default_factory=list)


@dataclass
class _MatchResult:
    matched: list = field(default_factory=list)


def _result(cgen: str = "", export: str = "", url: str = ""):
    """Un placement con un solo creative link y su triangulo."""
    return _MatchResult(matched=[_Matched(
        expected=_Expected(cgen=cgen, creatives=[_Creative(cgen=cgen)]),
        creative_links=[_Link(triangle=check_triangle(cgen, export, url))],
    )])


def _run(match_result, account: str = ""):
    buffer = FindingsBuffer()
    attribution.evaluate(match_result, buffer, account=account)
    return buffer.findings


def _statuses(findings):
    return {f.status for f in findings}


def test_unilever_is_never_asked_for_a_cgen():
    findings = _run(_result(), account="Unilever")
    assert _statuses(findings) == {Status.INFO}
    assert "Unilever" in findings[0].message


def test_blackrock_and_wendys_are_exempt_too():
    for account in ("BlackRock", "Wendy's"):
        findings = _run(_result(), account=account)
        assert _statuses(findings) == {Status.INFO}, account


def test_the_account_name_is_matched_loosely():
    # El selector lo alimentan varias fuentes; no puede depender de
    # que alguien escriba la mayuscula igual.
    for spelling in ("unilever", "UNILEVER", "  Unilever  "):
        findings = _run(_result(), account=spelling)
        assert _statuses(findings) == {Status.INFO}, spelling


def test_a_stray_cgen_does_not_switch_the_check_back_on():
    # Este es el bug. Una fila de plantilla con CGEN encendia la
    # validacion para toda la cuenta.
    findings = _run(_result(cgen="C-999"), account="Unilever")
    assert _statuses(findings) == {Status.INFO}
    assert not [f for f in findings if f.status == Status.NOT_VERIFIED]


def test_a_stray_cgen_is_still_reported():
    # Saltar la revision no puede tapar que hay un dato donde no
    # deberia: o la cuenta esta mal elegida, o alguien se equivoco.
    findings = _run(_result(cgen="C-999"), account="Unilever")
    assert "CGEN value(s)" in findings[0].message


def test_a_clean_unilever_sheet_says_nothing_about_stray_cgens():
    findings = _run(_result(), account="Unilever")
    assert "CGEN value(s)" not in findings[0].message


def test_adobe_still_gets_its_triangle_checked():
    findings = _run(
        _result(cgen="C-1", export="C-1", url="https://x.com/?sdid=C-1"),
        account="Adobe",
    )
    assert _statuses(findings) == {Status.PASS}


def test_adobe_still_fails_when_the_vertices_disagree():
    findings = _run(
        _result(cgen="C-1", export="C-2", url="https://x.com/?sdid=C-1"),
        account="Adobe",
    )
    assert _statuses(findings) == {Status.FAIL}


def test_an_adobe_campaign_falls_back_to_the_sheet():
    # El selector ofrece campanas de Adobe (Acrobat, Firefly, STE...)
    # que no estan en la tabla. Ahi decide el contenido, no el nombre.
    findings = _run(
        _result(cgen="C-1", export="C-1", url="https://x.com/?sdid=C-1"),
        account="Acrobat",
    )
    assert _statuses(findings) == {Status.PASS}


def test_without_an_account_a_sheet_with_no_cgen_is_still_exempt():
    # El comportamiento viejo sigue de respaldo para quien no elija.
    findings = _run(_result(), account="")
    assert _statuses(findings) == {Status.INFO}


def test_without_an_account_the_message_points_at_the_selector():
    findings = _run(_result(), account="")
    assert "Account / Campaign" in findings[0].message


def test_an_empty_run_says_nothing():
    assert _run(_MatchResult(matched=[]), account="Unilever") == []


if __name__ == "__main__":
    passed = failed = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        try:
            fn()
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {name}: {exc}")
        else:
            passed += 1
            print(f"ok   {name}")

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
