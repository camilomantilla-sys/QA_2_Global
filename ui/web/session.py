"""
La solicitud que se esta revisando en la interfaz nueva.

QA2 lo usa una persona en su propio PC, asi que hay una sola sesion: los
archivos de la solicitud en curso, en memoria. Nada de esto se escribe
en disco (cada lectura usa una carpeta temporal que se borra al
terminar) y todo se pierde al pulsar Start over o al cerrar la ventana
de QA2.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any

from core import pipeline

#: Lo que se puede subir en el paso 2. Los de varios archivos son listas.
SLOTS = {
    "pc": {"label": "Placement-Creative View", "many": False},
    "pl": {"label": "Placement View", "many": False},
    "tags": {"label": "Tag files", "many": True},
    "dv": {"label": "DV Pinnacle tags", "many": True},
}
WORKBOOK_SUFFIXES = (".xlsx", ".xlsm", ".xls")
#: Como dice el parser que tipo de export es, en palabras de la pantalla.
_TYPE_LABELS = {"placement_creative": "Placement-Creative View",
                "placement": "Placement View"}


@dataclass
class Upload:
    name: str
    data: bytes
    result: Any = None


@dataclass
class Session:
    ts: Upload | None = None
    files: dict[str, list[Upload]] = field(default_factory=lambda: {k: [] for k in SLOTS})
    account: str = ""
    check_innovid: bool = False
    last_run: dict | None = None
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    # ------------------------------------------------------------ cambios
    def reset(self) -> None:
        with self.lock:
            self.ts = None
            self.files = {k: [] for k in SLOTS}
            self.last_run = None

    def set_traffic_sheet(self, name: str, data: bytes, result) -> None:
        with self.lock:
            self.ts = Upload(name, data, result)
            self.last_run = None

    def add_file(self, slot: str, name: str, data: bytes) -> None:
        """Lee el archivo antes de guardarlo: si no se puede leer, no entra."""
        if slot == "tags":
            result = pipeline.parse_tags(data, name)
        elif slot == "dv":
            result = pipeline.parse_dv([(name, data)])
        else:
            result = pipeline.parse_export(data, name)
        with self.lock:
            upload = Upload(name, data, result)
            if SLOTS[slot]["many"]:
                self.files[slot] = [u for u in self.files[slot] if u.name != name] + [upload]
            else:
                self.files[slot] = [upload]
            self.last_run = None

    def remove_file(self, slot: str, name: str) -> None:
        with self.lock:
            self.files[slot] = [u for u in self.files[slot] if u.name != name]
            self.last_run = None

    # ------------------------------------------------------------ lectura
    def _one(self, slot: str) -> Upload | None:
        return self.files[slot][0] if self.files[slot] else None

    def dv_result(self):
        uploads = self.files["dv"]
        if not uploads:
            return None
        return pipeline.parse_dv([(u.name, u.data) for u in uploads])

    def overview(self) -> dict[str, Any]:
        """Lo que muestra el paso 2: que es cada archivo y si se puede correr."""
        ts = self.ts
        pc, pl = self._one("pc"), self._one("pl")
        tags = [(u.name, u.result) for u in self.files["tags"]]
        dv = self.dv_result()

        files: list[dict] = []
        issues: list[dict] = []
        if ts is not None:
            files, issues = pipeline.understand_files(
                ts.name, ts.result,
                pc.name if pc else "", pc.result if pc else None,
                pl.name if pl else "", pl.result if pl else None,
                tags, dv,
            )
        # Lo de la TS ya se vio en el paso 1.
        files = [f for f in files if f["Expected Type"] != "Traffic Sheet"]
        issues = [i for i in issues if i["Source"] != "Traffic Sheet"]
        fatal = [i for i in issues if i["Severity"] == "FATAL"]

        coverage = None
        if ts is not None and pc is not None and not pipeline.is_fatal(pc.result):
            worked = [str(p.placement_id) for p in getattr(ts.result, "worked", [])]
            in_export = {str(r.values.get("placement_id")) for r in pc.result.rows
                         if r.values.get("placement_id")}
            missing = [pid for pid in worked if pid not in in_export]
            coverage = {"worked": len(worked), "found": len(worked) - len(missing),
                        "missing": missing[:25], "missing_total": len(missing)}

        for f in files:
            f["Detected Type"] = _TYPE_LABELS.get(f.get("Detected Type"), f.get("Detected Type"))
        slots = {}
        for key, spec in SLOTS.items():
            slots[key] = [
                next((dict(f) for f in files if f["File"] == u.name
                      and _matches_slot(f["Expected Type"], key)), {"File": u.name})
                for u in self.files[key]
            ]
        return {
            "has_ts": ts is not None,
            "ts_name": ts.name if ts else "",
            "slots": slots,
            "issues": [i for i in issues if i["Severity"] in ("FATAL", "WARNING")][:40],
            "coverage": coverage,
            "ready": ts is not None and pc is not None and not fatal and not ts.result.fatal,
            "blocked_by": [i["Message"] for i in fatal][:5],
        }

    # ------------------------------------------------------------ correr
    def run(self, account: str = "", fetch_innovid=None) -> dict[str, Any]:
        """
        El QA completo, con la misma cadena que la app de Streamlit.

        ``fetch_innovid(campaign_id, placement_ids)`` lo pasa el
        servidor cuando la persona pidio revisar contra Innovid.
        """
        from core.matching import match
        from ui.web.results import build_results

        ts, pc, pl = self.ts, self._one("pc"), self._one("pl")
        if ts is None or pc is None:
            raise ValueError("Load the Traffic Sheet and the Placement-Creative View first.")
        tags = [(u.name, u.result) for u in self.files["tags"]]
        dv = self.dv_result()

        match_result = match(ts.result, pc.result, pl.result if pl else None)

        innovid = {"used": False}
        innovid_reconciliation = None
        if fetch_innovid is not None:
            from core.innovid_reconciliation import reconcile as reconcile_innovid
            campaign_id = str(getattr(match_result, "ts_campaign_id", "") or "").strip()
            if not campaign_id:
                innovid = {"used": False, "message": (
                    "The Traffic Sheet doesn't declare a Campaign ID in Campaign "
                    "Information, so there was nothing to look up in Innovid. "
                    "The rest of the QA ran normally.")}
            else:
                worked = tuple(sorted(str(pm.placement_id) for pm in match_result.matched))
                answer = fetch_innovid(campaign_id, worked)
                innovid_reconciliation = reconcile_innovid(match_result, answer)
                innovid = {"used": True, "campaign_id": campaign_id,
                           "placements": len(answer.placements or []),
                           "errors": list(answer.errors or [])[:5]}

        checks = pipeline.run_checks(
            match_result, ts.result, pc.result, pl.result if pl else None,
            tags, dv, account=account, innovid_reconciliation=innovid_reconciliation,
        )
        names = {str(r.values.get("placement_id")): str(r.values.get("placement_name") or "")
                 for r in (ts.result.placements.rows if ts.result.placements else [])}
        payload = build_results(checks.findings, names, innovid)
        payload["account"] = account
        with self.lock:
            self.account = account
            self.last_run = payload
        return payload


def _matches_slot(expected_type: str, slot: str) -> bool:
    return {
        "pc": "Placement-Creative View",
        "pl": "Placement View",
        "tags": "Tags",
        "dv": "DV Pinnacle Tags",
    }[slot] == expected_type


def account_options() -> list[str]:
    """Las mismas cuentas que ofrece la app de Streamlit."""
    names: set[str] = set()
    try:
        from core.pixel_reconciliation import load_vendor_rows
        names |= {r.get("account", "").strip() for r in load_vendor_rows()}
    except Exception:  # noqa: BLE001 - una tabla rota no tumba la pagina
        pass
    try:
        from core.adobe_pixel_reconciliation import load_adobe_vendor_rows
        names |= {r.get("campaign", "").strip() for r in load_adobe_vendor_rows()}
    except Exception:  # noqa: BLE001
        pass
    try:
        from core.team_roster import ACCOUNTS
        names |= {a for a in ACCOUNTS if a != "Support"}
    except Exception:  # noqa: BLE001
        pass
    return sorted(n for n in names if n)


#: La sesion de este PC.
SESSION = Session()
