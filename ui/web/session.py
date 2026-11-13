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
from datetime import date
from types import SimpleNamespace
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
#: Lo que se escribe en el Implementation Record. Las fechas van como
#: 'AAAA-MM-DD'.
RECORD_FIELDS = (
    "campaign", "request_type", "wrike_id", "implemented_by",
    "implementation_date", "qa2_by", "qa2_date", "qa3_by", "qa3_date", "notes",
)
_RECORD_DATES = ("implementation_date", "qa2_date", "qa3_date")
#: Capturas de evidencia: lo que el PDF y el Excel saben pegar.
IMAGE_TYPES = {b"\x89PNG": "png", b"\xff\xd8\xff": "jpg", b"GIF8": "gif"}
MAX_IMAGE = 15 * 1024 * 1024
MAX_IMAGES = 30
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
    #: Implementation Record, lo que trajo el bundle y lo que firma QA2.
    record: dict = field(default_factory=lambda: {k: "" for k in RECORD_FIELDS})
    qa1_result: dict | None = None
    evidence: list[Upload] = field(default_factory=list)
    #: finding_id -> {"approved": True, "note": "..."}
    reviews: dict = field(default_factory=dict)
    #: Lo crudo de la ultima corrida: para firmar y armar informes sin
    #: volver a correr el QA.
    run_state: Any = None
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    # ------------------------------------------------------------ cambios
    def reset(self) -> None:
        with self.lock:
            self.ts = None
            self.files = {k: [] for k in SLOTS}
            self.last_run = None
            self.record = {k: "" for k in RECORD_FIELDS}
            self.qa1_result = None
            self.evidence = []
            self.reviews = {}
            self.run_state = None

    def set_traffic_sheet(self, name: str, data: bytes, result) -> None:
        with self.lock:
            self.ts = Upload(name, data, result)
            self.last_run = None
            self.run_state = None
            campaign = str((getattr(result, "campaign_info", {}) or {}).get("campaignname") or "")
            if campaign and not self.record.get("campaign"):
                self.record["campaign"] = campaign

    # ------------------------------------------------------------ registro
    def update_record(self, values: dict) -> dict:
        """Solo los campos conocidos, como texto corto; fechas validas o vacias."""
        with self.lock:
            for key in RECORD_FIELDS:
                if key not in values:
                    continue
                text = str(values.get(key) or "").strip()[:2000 if key == "notes" else 200]
                if key in _RECORD_DATES and text:
                    try:
                        text = date.fromisoformat(text[:10]).isoformat()
                    except ValueError:
                        text = ""
                self.record[key] = text
            return dict(self.record)

    def _record_date(self, key: str) -> date | None:
        text = self.record.get(key) or ""
        try:
            return date.fromisoformat(text) if text else None
        except ValueError:
            return None

    # ------------------------------------------------------------ evidencia
    def add_evidence(self, name: str, data: bytes) -> list[str]:
        kind = next((ext for magic, ext in IMAGE_TYPES.items() if data.startswith(magic)), "")
        if not kind:
            raise ValueError("Screenshots go in as PNG, JPG or GIF.")
        if len(data) > MAX_IMAGE:
            raise ValueError("That screenshot is over 15 MB.")
        with self.lock:
            if len(self.evidence) >= MAX_IMAGES:
                raise ValueError(f"A report takes up to {MAX_IMAGES} screenshots.")
            base = name.rsplit(".", 1)[0][:80] or "screenshot"
            taken = {u.name for u in self.evidence}
            final, n = f"{base}.{kind}", 2
            while final in taken:
                final, n = f"{base}_{n}.{kind}", n + 1
            self.evidence.append(Upload(final, data))
            return [u.name for u in self.evidence]

    def remove_evidence(self, name: str) -> list[str]:
        with self.lock:
            self.evidence = [u for u in self.evidence if u.name != name]
            return [u.name for u in self.evidence]

    def evidence_image(self, name: str) -> bytes | None:
        return next((u.data for u in self.evidence if u.name == name), None)

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
            self.run_state = None

    def remove_file(self, slot: str, name: str) -> None:
        with self.lock:
            self.files[slot] = [u for u in self.files[slot] if u.name != name]
            self.last_run = None
            self.run_state = None

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
        state = SimpleNamespace(
            match_result=match_result, checks=checks, names=names, innovid=innovid,
            innovid_reconciliation=innovid_reconciliation, tags=tags, dv=dv,
            dates=pipeline.compare_dates(ts.result, pc.result, pl.result if pl else None,
                                         match_result),
        )
        with self.lock:
            self.account = account
            self.run_state = state
            # Quien corre el QA2 lo hace hoy, salvo que diga otra cosa.
            if not self.record.get("qa2_date"):
                self.record["qa2_date"] = date.today().isoformat()
        return self.results()

    # ------------------------------------------------------------ firmar
    def signed_findings(self) -> list:
        """Los hallazgos de la ultima corrida con las firmas de QA2 aplicadas."""
        from core.reports import apply_review_overrides
        state = self.run_state
        if state is None:
            return []
        live = {f.finding_id for f in state.checks.findings.findings}
        with self.lock:
            # Una firma cuyo hallazgo ya no existe (otra corrida) no vale.
            for key in [k for k in self.reviews if k not in live]:
                self.reviews.pop(key, None)
            reviews = dict(self.reviews)
        return apply_review_overrides(
            state.checks.findings.findings, reviews,
            approved_by=self.record.get("qa2_by", ""))

    def sign(self, finding_ids: list[str], approved: bool, note: str = "") -> dict[str, Any]:
        from core.reports import REVIEWABLE
        state = self.run_state
        if state is None:
            raise ValueError("Run the QA first.")
        reviewable = {f.finding_id for f in state.checks.findings.findings
                      if f.status.value in REVIEWABLE}
        note = str(note or "").strip()[:500]
        with self.lock:
            for fid in finding_ids:
                if fid not in reviewable:
                    continue
                if approved:
                    self.reviews[fid] = {"approved": True, "note": note}
                else:
                    self.reviews.pop(fid, None)
        return self.results()

    def results(self) -> dict[str, Any]:
        """Lo que pinta el paso 5, con lo firmado ya contado en el veredicto."""
        from core.reports import REVIEWABLE
        from ui.web.results import build_results
        state = self.run_state
        if state is None:
            return self.last_run or {}
        signed = self.signed_findings()
        payload = build_results(SimpleNamespace(findings=signed), state.names, state.innovid)
        original = {f.finding_id: f.status.value for f in state.checks.findings.findings}
        with self.lock:
            reviews = dict(self.reviews)
        for row in payload["findings"]:
            before = original.get(row["id"], row["status"])
            row["reviewable"] = before in REVIEWABLE
            row["signed"] = row["id"] in reviews
            row["note"] = reviews.get(row["id"], {}).get("note", "")
            row["original_status"] = before
        payload["review"] = {
            "total": sum(1 for s in original.values() if s in REVIEWABLE),
            "signed": len(reviews),
        }
        payload["account"] = self.account
        payload["dates"] = state.dates
        payload["record"] = dict(self.record)
        payload["evidence"] = [u.name for u in self.evidence]
        with self.lock:
            self.last_run = payload
        return payload

    # ------------------------------------------------------------ informes
    def report_inputs(self):
        from core.reports import ReportInputs
        from core.tag_analysis import analyse_tags
        from core.qa1_trail import describe_result
        state = self.run_state
        ts, pc, pl = self.ts, self._one("pc"), self._one("pl")
        if state is None or ts is None or pc is None:
            raise ValueError("Run the QA first.")
        file_rows, _issues = pipeline.understand_files(
            ts.name, ts.result,
            pc.name, pc.result,
            pl.name if pl else "", pl.result if pl else None,
            state.tags, state.dv,
        )
        profile = pipeline.profile_label(ts.result.profile)
        return ReportInputs(
            ts_result=ts.result,
            match_result=state.match_result,
            findings=self.signed_findings(),
            profile_used=profile,
            detected_profile=profile,
            detection_evidence=str(getattr(ts.result, "profile_evidence", "") or ""),
            file_rows=file_rows,
            tags_results=state.tags,
            tag_matches=state.checks.tag_matches,
            tag_analysis=analyse_tags(state.tags, ts.result),
            dv_result=state.dv,
            innovid_reconciliation=state.innovid_reconciliation,
            evidence_images=[(u.name, u.data) for u in self.evidence],
            campaign=self.record.get("campaign", ""),
            request_type=self.record.get("request_type", ""),
            wrike_id=self.record.get("wrike_id", ""),
            implemented_by=self.record.get("implemented_by", ""),
            qa1_result=describe_result(self.qa1_result),
            implementation_date=self._record_date("implementation_date"),
            qa2_by=self.record.get("qa2_by", ""),
            qa2_date=self._record_date("qa2_date"),
            qa3_by=self.record.get("qa3_by", ""),
            qa3_date=self._record_date("qa3_date"),
            notes=self.record.get("notes", ""),
        )

    def report(self, kind: str) -> tuple[str, bytes, str]:
        """(nombre del archivo, bytes, tipo) del PDF o del Excel."""
        from core.report_name import report_filename
        from core.reports import build_excel, build_pdf
        inputs = self.report_inputs()
        campaign = self.record.get("campaign", "")
        if kind == "pdf":
            return report_filename("pdf", campaign), build_pdf(inputs), "application/pdf"
        return (report_filename("xlsx", campaign), build_excel(inputs),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    def bundle(self) -> bytes:
        """El session bundle de esta solicitud, el mismo que guarda Streamlit."""
        from core.qa1_trail import result_snapshot
        from core.session_bundle import write_bundle
        if self.ts is None:
            raise ValueError("Load the Traffic Sheet first.")
        files = {"ts": [(self.ts.name, self.ts.data)],
                 "evidence": [(u.name, u.data) for u in self.evidence]}
        for slot in SLOTS:
            files[slot] = [(u.name, u.data) for u in self.files[slot]]
        result = None
        if self.run_state is not None:
            from core.findings import Scorecard
            card = Scorecard.from_findings(self.signed_findings())
            from datetime import datetime
            result = result_snapshot(card.verdict, card.errors, card.reviews,
                                     card.not_verified,
                                     datetime.now().isoformat(timespec="seconds"))
        fields = {k: self.record.get(k, "") for k in (
            "campaign", "request_type", "wrike_id", "implemented_by",
            "implementation_date", "notes")}
        fields.update({"profile": "AUTO", "account": self.account,
                       # Lo que vio el QA1 se conserva; si este bundle lo
                       # arma el QA1, va su propia corrida.
                       "qa1_result": self.qa1_result or result})
        return write_bundle(files, fields)


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
