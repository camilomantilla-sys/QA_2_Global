"""
core/findings.py — Esquema canónico de hallazgos del motor QA2.

Reglas de diseño:
  - Sin I/O, sin presentación, sin color. Importable desde cualquier front.
  - Schema estable: un dataset vacío conserva todas las columnas (masterprompt #17).
  - PASS, REVIEW y NOT_VERIFIED son ciudadanos de primera clase (#16, #63).
  - Las reglas NO deciden severidad final. Declaran intención; el buffer
    aplica los gates de capacidad (#capabilities) y de confianza (#39, #40).
  - Finding_ID determinista -> dedup y regresión estables (#49).
"""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterable, Iterator, Mapping, Sequence

__all__ = [
    "Status", "Severity", "Domain", "Phase", "Confidence", "EntityType",
    "Capability", "CapabilityRegistry", "CapabilityState",
    "SourceRef", "Evidence", "Finding", "FindingsBuffer", "Scorecard",
    "FINDING_COLUMNS",
]

ENGINE_VERSION = "0.4.0"

# ───────────────────────────────────────────────────── enums

class Status(str, Enum):
    """Veredicto del check. Qué pasó."""
    PASS = "PASS"
    FAIL = "FAIL"
    REVIEW = "REVIEW"
    NOT_VERIFIED = "NOT_VERIFIED"
    INFO = "INFO"

class Severity(str, Enum):
    """Impacto operativo. Cuánto duele."""
    BLOCKER = "BLOCKER"
    ERROR = "ERROR"
    WARN = "WARN"
    INFO = "INFO"
    NONE = "NONE"

    @property
    def rank(self) -> int:
        return _SEVERITY_RANK[self]

_SEVERITY_RANK: dict[Severity, int] = {
    Severity.BLOCKER: 5,
    Severity.ERROR: 4,
    Severity.WARN: 3,
    Severity.INFO: 2,
    Severity.NONE: 1,
}

class Domain(str, Enum):
    INGESTION = "Ingestion"
    STRUCTURE = "Structure"
    CARDINALITY = "Cardinality"
    SCOPE = "Scope"
    IDENTITY = "Identity"
    DATES = "Dates"
    DIMENSIONS = "Dimensions"
    CREATIVE = "Creative"
    ROTATION = "Rotation"
    URL = "URL"
    ATTRIBUTION = "Attribution"
    PIXEL = "Pixel"
    TAG = "Tag"
    TAXONOMY = "Taxonomy"

class Phase(str, Enum):
    """Pre-QA valida la fuente; QA2 valida la implementación (#7)."""
    PRE_QA = "PRE_QA"
    QA2 = "QA2"

class Confidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    NONE = "NONE"

    @property
    def rank(self) -> int:
        return {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "NONE": 0}[self.value]

class EntityType(str, Enum):
    CAMPAIGN = "Campaign"
    PLACEMENT = "Placement"
    CREATIVE = "Creative"
    ROTATION = "Rotation"
    DECISION_TREE = "DecisionTree"
    LANDING_PAGE = "LandingPage"
    PIXEL = "Pixel"
    TAG = "Tag"
    FILE = "File"

# ───────────────────────────────────────────────────── capacidades

class Capability(str, Enum):
    """
    Qué puede verificar el motor con los insumos recibidos.
    Si una capacidad falta, la regla emite NOT_VERIFIED — nunca FAIL,
    nunca se omite en silencio.
    """
    PLACEMENT_EXPORT = "placement_export"
    CREATIVE_EXPORT = "creative_export"
    TAG_EXPORT = "tag_export"
    WRAPPER_EXPORT = "wrapper_export"
    DECISION_TREE_ID = "decision_tree_id"
    THIRD_PARTY_ID = "third_party_id"
    CLICKTAG_URL = "clicktag_url"
    PLACEMENT_URL = "placement_url"
    PIXEL_DATA = "pixel_data"
    NETWORK_ACCESS = "network_access"
    TS_COLOR_STATE = "ts_color_state"

@dataclass(frozen=True, slots=True)
class CapabilityState:
    capability: Capability
    available: bool
    reason: str = ""

class CapabilityRegistry:
    """Declara una sola vez qué se puede verificar; las reglas consultan."""

    def __init__(self, states: Iterable[CapabilityState] = ()) -> None:
        self._states: dict[Capability, CapabilityState] = {
            s.capability: s for s in states
        }

    def declare(self, capability: Capability, available: bool, reason: str = "") -> None:
        self._states[capability] = CapabilityState(capability, available, reason)

    def available(self, capability: Capability) -> bool:
        state = self._states.get(capability)
        return bool(state and state.available)

    def reason(self, capability: Capability) -> str:
        state = self._states.get(capability)
        if state is None:
            return f"capacidad '{capability.value}' no declarada"
        return state.reason or f"capacidad '{capability.value}' no disponible"

    def missing(self, required: Sequence[Capability]) -> list[Capability]:
        return [c for c in required if not self.available(c)]

    def as_dict(self) -> dict[str, dict[str, Any]]:
        return {
            c.value: {"available": s.available, "reason": s.reason}
            for c, s in sorted(self._states.items(), key=lambda kv: kv[0].value)
        }

# ───────────────────────────────────────────────────── trazabilidad

@dataclass(frozen=True, slots=True)
class SourceRef:
    """De dónde salió el dato. Debe permitir reproducir a mano (#41)."""
    file: str = ""
    sheet: str = ""
    row: int | None = None
    column: str = ""

    def __str__(self) -> str:
        parts = [p for p in (self.file, self.sheet) if p]
        loc = ""
        if self.row is not None:
            loc = f"r{self.row}"
        if self.column:
            loc = f"{loc}:{self.column}" if loc else self.column
        if loc:
            parts.append(loc)
        return " | ".join(parts)

@dataclass(frozen=True, slots=True)
class Evidence:
    """
    RAW y NORMALIZED de ambos lados (#10). Nunca se pierde el valor original.
    """
    expected_raw: Any = None
    expected_norm: Any = None
    actual_raw: Any = None
    actual_norm: Any = None
    match_key: str = ""
    expected_source: SourceRef | None = None
    actual_source: SourceRef | None = None
    extra: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "expected_raw": self.expected_raw,
            "expected_norm": self.expected_norm,
            "actual_raw": self.actual_raw,
            "actual_norm": self.actual_norm,
            "match_key": self.match_key,
            "expected_source": str(self.expected_source) if self.expected_source else "",
            "actual_source": str(self.actual_source) if self.actual_source else "",
        }
        payload.update(self.extra)
        return {k: v for k, v in payload.items() if v not in (None, "", {})}

# ───────────────────────────────────────────────────── finding

FINDING_COLUMNS: tuple[str, ...] = (
    # 22 canónicos
    "Finding_ID", "Status", "Severity", "Domain", "Rule_ID",
    "Account", "Platform", "Campaign",
    "Placement_ID", "Placement_Name", "Creative_ID", "Creative_Name",
    "Entity_Type", "Expected", "Actual",
    "Message", "Reason", "Recommended_Action",
    "Source", "Confidence", "Evidence", "Timestamp",
    # extras del motor
    "Phase", "Count", "Match_Key", "Degraded_From", "Degrade_Reason",
)

@dataclass(frozen=True, slots=True)
class Finding:
    rule_id: str
    domain: Domain
    status: Status
    severity: Severity
    message: str
    phase: Phase = Phase.QA2
    entity_type: EntityType = EntityType.PLACEMENT
    account: str = ""
    platform: str = ""
    campaign: str = ""
    placement_id: str = ""
    placement_name: str = ""
    creative_id: str = ""
    creative_name: str = ""
    expected: str = ""
    actual: str = ""
    reason: str = ""
    recommended_action: str = ""
    confidence: Confidence = Confidence.HIGH
    evidence: Evidence = field(default_factory=Evidence)
    source: SourceRef | None = None
    count: int = 1
    degraded_from: Severity | None = None
    degrade_reason: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )

    # ── identidad determinista: mismo hallazgo -> mismo ID entre corridas
    @property
    def finding_id(self) -> str:
        seed = "|".join(
            str(x) for x in (
                self.rule_id, self.domain.value, self.entity_type.value,
                self.placement_id, self.creative_id,
                self.expected, self.actual,
            )
        )
        return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]

    @property
    def dedup_key(self) -> str:
        return self.finding_id

    def to_row(self) -> dict[str, Any]:
        return {
            "Finding_ID": self.finding_id,
            "Status": self.status.value,
            "Severity": self.severity.value,
            "Domain": self.domain.value,
            "Rule_ID": self.rule_id,
            "Account": self.account,
            "Platform": self.platform,
            "Campaign": self.campaign,
            "Placement_ID": self.placement_id,
            "Placement_Name": self.placement_name,
            "Creative_ID": self.creative_id,
            "Creative_Name": self.creative_name,
            "Entity_Type": self.entity_type.value,
            "Expected": self.expected,
            "Actual": self.actual,
            "Message": self.message,
            "Reason": self.reason,
            "Recommended_Action": self.recommended_action,
            "Source": str(self.source) if self.source else "",
            "Confidence": self.confidence.value,
            "Evidence": self.evidence.as_dict(),
            "Timestamp": self.timestamp,
            "Phase": self.phase.value,
            "Count": self.count,
            "Match_Key": self.evidence.match_key,
            "Degraded_From": self.degraded_from.value if self.degraded_from else "",
            "Degrade_Reason": self.degrade_reason,
        }

# ───────────────────────────────────────────────────── buffer + gates

# Severidad por defecto según veredicto. Una regla puede pedir BLOCKER en un FAIL.
_DEFAULT_SEVERITY: dict[Status, Severity] = {
    Status.PASS: Severity.NONE,
    Status.FAIL: Severity.ERROR,
    Status.REVIEW: Severity.WARN,
    Status.NOT_VERIFIED: Severity.INFO,
    Status.INFO: Severity.INFO,
}

class FindingsBuffer:
    """
    Punto único de emisión. Aplica, en este orden:
      1. Gate de capacidad  -> si falta un insumo, NOT_VERIFIED (no FAIL, no silencio)
      2. Gate de confianza  -> FAIL con confianza < HIGH degrada a REVIEW
      3. Coherencia Status/Severity
      4. Dedup por Finding_ID
    """

    def __init__(
        self,
        capabilities: CapabilityRegistry | None = None,
        *,
        account: str = "",
        platform: str = "",
        campaign: str = "",
        dedup: bool = True,
    ) -> None:
        self.capabilities = capabilities or CapabilityRegistry()
        self._defaults = {"account": account, "platform": platform, "campaign": campaign}
        self._dedup = dedup
        self._items: list[Finding] = []
        self._seen: set[str] = set()

    # ── API que usan las reglas

    def emit(
        self,
        rule_id: str,
        domain: Domain,
        status: Status,
        message: str,
        *,
        severity: Severity | None = None,
        requires: Sequence[Capability] = (),
        allow_fail_below_high: bool = False,
        **kwargs: Any,
    ) -> Finding:
        finding = Finding(
            rule_id=rule_id,
            domain=domain,
            status=status,
            severity=severity or _DEFAULT_SEVERITY[status],
            message=message,
            **{**self._defaults, **kwargs},
        )
        finding = self._gate_capability(finding, requires)
        finding = self._gate_confidence(finding, allow_fail_below_high)
        finding = self._enforce_coherence(finding)
        return self._append(finding)

    def pass_(self, rule_id: str, domain: Domain, message: str, **kw: Any) -> Finding:
        return self.emit(rule_id, domain, Status.PASS, message, **kw)

    def fail(self, rule_id: str, domain: Domain, message: str, **kw: Any) -> Finding:
        return self.emit(rule_id, domain, Status.FAIL, message, **kw)

    def blocker(self, rule_id: str, domain: Domain, message: str, **kw: Any) -> Finding:
        kw.setdefault("severity", Severity.BLOCKER)
        return self.emit(rule_id, domain, Status.FAIL, message, **kw)

    def review(self, rule_id: str, domain: Domain, message: str, **kw: Any) -> Finding:
        return self.emit(rule_id, domain, Status.REVIEW, message, **kw)

    def info(self, rule_id: str, domain: Domain, message: str, **kw: Any) -> Finding:
        return self.emit(rule_id, domain, Status.INFO, message, **kw)

    def not_verified(self, rule_id: str, domain: Domain, message: str, **kw: Any) -> Finding:
        return self.emit(rule_id, domain, Status.NOT_VERIFIED, message, **kw)

    def aggregate(
        self,
        rule_id: str,
        domain: Domain,
        status: Status,
        message: str,
        count: int,
        **kw: Any,
    ) -> Finding:
        """Un hallazgo que representa N ocurrencias. Evita inundar el reporte."""
        kw["count"] = count
        return self.emit(rule_id, domain, status, message, **kw)

    # ── gates

    def _gate_capability(self, f: Finding, requires: Sequence[Capability]) -> Finding:
        if not requires:
            return f
        missing = self.capabilities.missing(requires)
        if not missing:
            return f
        if f.status in (Status.INFO, Status.NOT_VERIFIED):
            return f
        reasons = "; ".join(self.capabilities.reason(c) for c in missing)
        return replace(
            f,
            status=Status.NOT_VERIFIED,
            severity=Severity.INFO,
            degraded_from=f.severity,
            degrade_reason=f"insumo faltante: {reasons}",
            reason=f.reason or reasons,
            recommended_action=(
                f.recommended_action
                or "Cargar el insumo faltante y volver a correr el QA2."
            ),
        )

    def _gate_confidence(self, f: Finding, allow_fail_below_high: bool) -> Finding:
        if f.status is not Status.FAIL:
            return f
        if allow_fail_below_high or f.confidence is Confidence.HIGH:
            return f
        return replace(
            f,
            status=Status.REVIEW,
            severity=Severity.WARN,
            degraded_from=f.severity,
            degrade_reason=(
                f"confianza {f.confidence.value} en el match "
                f"(llave: {f.evidence.match_key or 'n/d'}) — requiere revisión humana"
            ),
        )

    @staticmethod
    def _enforce_coherence(f: Finding) -> Finding:
        if f.status is Status.PASS and f.severity is not Severity.NONE:
            return replace(f, severity=Severity.NONE)
        if f.status is Status.FAIL and f.severity not in (Severity.BLOCKER, Severity.ERROR):
            return replace(f, severity=Severity.ERROR)
        if f.status is Status.REVIEW and f.severity is not Severity.WARN:
            return replace(f, severity=Severity.WARN)
        return f

    def _append(self, f: Finding) -> Finding:
        if self._dedup:
            if f.dedup_key in self._seen:
                return f
            self._seen.add(f.dedup_key)
        self._items.append(f)
        return f

    # ── salida

    def extend(self, findings: Iterable[Finding]) -> None:
        for f in findings:
            self._append(self._enforce_coherence(f))

    def __iter__(self) -> Iterator[Finding]:
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    @property
    def findings(self) -> list[Finding]:
        return list(self._items)

    def to_rows(self) -> list[dict[str, Any]]:
        """Siempre devuelve el schema completo, incluso vacío (#17)."""
        if not self._items:
            return []
        return [f.to_row() for f in self._items]

    def scorecard(self) -> "Scorecard":
        return Scorecard.from_findings(self._items)

# ───────────────────────────────────────────────────── scorecard

@dataclass(frozen=True, slots=True)
class Scorecard:
    """
    NOT_VERIFIED es categoría propia: 100% PASS con 40 checks no verificados
    NO es un QA aprobado.
    """
    by_status: Mapping[str, int]
    by_severity: Mapping[str, int]
    by_domain: Mapping[str, int]
    total_findings: int
    occurrences: int

    @classmethod
    def from_findings(cls, findings: Sequence[Finding]) -> "Scorecard":
        status = Counter({s.value: 0 for s in Status})
        severity = Counter({s.value: 0 for s in Severity})
        domain: Counter[str] = Counter()
        occurrences = 0
        for f in findings:
            status[f.status.value] += 1
            severity[f.severity.value] += 1
            if f.status not in (Status.PASS, Status.INFO):
                domain[f.domain.value] += 1
            occurrences += max(f.count, 1)
        return cls(
            by_status=dict(status),
            by_severity=dict(severity),
            by_domain=dict(domain),
            total_findings=len(findings),
            occurrences=occurrences,
        )

    @property
    def blockers(self) -> int:
        return self.by_severity.get(Severity.BLOCKER.value, 0)

    @property
    def errors(self) -> int:
        return self.by_severity.get(Severity.ERROR.value, 0)

    @property
    def reviews(self) -> int:
        return self.by_status.get(Status.REVIEW.value, 0)

    @property
    def not_verified(self) -> int:
        return self.by_status.get(Status.NOT_VERIFIED.value, 0)

    @property
    def passed(self) -> int:
        return self.by_status.get(Status.PASS.value, 0)

    @property
    def blocked(self) -> bool:
        return self.blockers > 0

    @property
    def verdict(self) -> str:
        """Un solo BLOCKER manda, sin importar el porcentaje (#36)."""
        if self.blockers:
            return "BLOCKED"
        if self.errors:
            return "FAILED"
        if self.reviews or self.not_verified:
            return "NEEDS_REVIEW"
        if self.passed:
            return "PASSED"
        return "NO_CHECKS"

    def as_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "blocked": self.blocked,
            "by_status": self.by_status,
            "by_severity": self.by_severity,
            "by_domain": self.by_domain,
            "total_findings": self.total_findings,
            "occurrences": self.occurrences,
        }