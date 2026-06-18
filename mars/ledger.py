"""The evidence ledger (build spec v2 §6) — the single source of truth.

Agents do not pass prose to each other; every assertion becomes a structured
**claim record** that accumulates across the run. Candidate research
**directions** reference the claims that support them. **Analysis records**
capture every specification the data agent executed (anti-p-hacking trail).

Confidence is COMPUTED here, never asserted by an agent. The mapping from a
record's state to a tier is deterministic and lives in `compute_claim_confidence`
/ `compute_direction_confidence`; thresholds come from config.yaml.

The whole ledger serialises to runs/<...>/ledger.json — the audit trail and the
evidence behind every line of the report.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional

# Confidence tiers
HIGH, MEDIUM, LOW = "high", "medium", "low"
_SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3}


def _sev(severity: str) -> int:
    return _SEVERITY_RANK.get((severity or "low").lower(), 1)


def _dup(objections, new) -> bool:
    """True if an objection with the same author + text already exists (dedupe
    across editorial passes)."""
    return any(o.by == new.by and o.text == new.text for o in objections)


# --------------------------------------------------------------------------- #
# Records
# --------------------------------------------------------------------------- #
@dataclass
class Grounding:
    type: str            # "paper" | "data" | "external"
    ref: str             # paper id / analysis id / external identifier
    loc: str = ""        # page / column / location


@dataclass
class Objection:
    by: str              # raising agent ("critique" | "red_team")
    text: str
    severity: str = "medium"     # "low" | "medium" | "high"
    resolved: bool = False
    resolution: str = ""         # how/why it was resolved (or overridden)
    target: str = ""             # claim id or direction id (set on attach)

    def is_blocking(self, blocking_severity: str) -> bool:
        return (not self.resolved) and _sev(self.severity) >= _sev(blocking_severity)


@dataclass
class Claim:
    id: str
    text: str
    raised_by: str
    grounded_in: List[Grounding] = field(default_factory=list)
    corroborated_by: List[str] = field(default_factory=list)   # independent agents
    contradicted_by: List[str] = field(default_factory=list)
    critique_objections: List[Objection] = field(default_factory=list)
    confidence_tier: str = LOW       # computed
    labels: List[str] = field(default_factory=list)            # exploratory|gap|null|signal...


@dataclass
class Direction:
    id: str
    title: str
    statement: str
    raised_by: str
    supporting_claims: List[str] = field(default_factory=list)
    objections: List[Objection] = field(default_factory=list)
    factors: Dict[str, float] = field(default_factory=dict)    # filled by scoring.py
    score: float = 0.0
    confidence_tier: str = LOW       # computed
    flags: List[str] = field(default_factory=list)             # null_uninteresting|no_so_what|blocked|dead_end
    status: str = "candidate"        # candidate|endorsed|contested|dead_end
    notes: Dict[str, str] = field(default_factory=dict)        # feasibility/redteam/scout notes


@dataclass
class AnalysisRecord:
    id: str              # e.g. "exploratory_ols_03"
    kind: str            # ols|logit|ttest|anova|chisq|describe|corr|vif|power...
    description: str
    code_path: str = ""  # runs/<...>/analyses/<id>.py (re-runnable)
    n: Optional[int] = None
    result_summary: str = ""
    numbers: List[float] = field(default_factory=list)   # numeric outputs (for the provenance gate)
    significant: Optional[bool] = None
    error: str = ""
    labels: List[str] = field(default_factory=lambda: ["exploratory"])


# --------------------------------------------------------------------------- #
# Confidence (deterministic — see §6)
# --------------------------------------------------------------------------- #
def compute_claim_confidence(claim: Claim, cfg: Dict) -> str:
    """Map a claim's ledger state to a tier. Pure function of the record + cfg.

    high   : grounded AND >= min_corroborators independent agents AND no
             unresolved objection.
    medium : grounded, not contradicted, but either single-agent OR carrying an
             unresolved sub-blocking objection (cannot reach high while contested).
    low    : not grounded, OR contradicted, OR carrying an unresolved objection
             at/above blocking_severity.
    """
    conf = cfg.get("confidence", {})
    min_corrob = int(conf.get("min_corroborators_for_high", 2))
    blocking = conf.get("blocking_severity", "high")
    contra_caps = bool(conf.get("contradiction_caps_low", True))

    grounded = len(claim.grounded_in) > 0
    if not grounded:
        return LOW
    if contra_caps and claim.contradicted_by:
        return LOW
    if any(o.is_blocking(blocking) for o in claim.critique_objections):
        return LOW

    has_unresolved = any(not o.resolved for o in claim.critique_objections)
    independent = {a for a in claim.corroborated_by if a != claim.raised_by}
    if has_unresolved:
        return MEDIUM  # contested but not blocking -> cannot be high
    if len(independent) >= min_corrob:
        return HIGH
    return MEDIUM


def compute_direction_confidence(direction: Direction, ledger: "Ledger", cfg: Dict) -> str:
    """A direction's tier from its own objections + its supporting claims.

    Critique-as-gate (§5.1): an unresolved objection at/above blocking_severity
    on the direction (or on a supporting claim) caps it at LOW ("promising but
    unvalidated"). It cannot be HIGH while any unresolved objection stands.
    """
    conf = cfg.get("confidence", {})
    blocking = conf.get("blocking_severity", "high")

    all_objs = list(direction.objections)
    support = [ledger.claims[c] for c in direction.supporting_claims if c in ledger.claims]
    for c in support:
        all_objs.extend(c.critique_objections)

    if not support or not any(c.grounded_in for c in support):
        return LOW
    if any(o.is_blocking(blocking) for o in all_objs):
        return LOW
    if any(c.contradicted_by for c in support) and conf.get("contradiction_caps_low", True):
        return LOW

    has_unresolved = any(not o.resolved for o in all_objs)
    best = _best_tier(c.confidence_tier for c in support)
    if has_unresolved:
        return MEDIUM if best != LOW else LOW
    return best


def _best_tier(tiers) -> str:
    order = {LOW: 0, MEDIUM: 1, HIGH: 2}
    best = LOW
    for t in tiers:
        if order.get(t, 0) > order[best]:
            best = t
    return best


# --------------------------------------------------------------------------- #
# Ledger
# --------------------------------------------------------------------------- #
class Ledger:
    def __init__(self, cfg: Optional[Dict] = None):
        self.cfg: Dict = cfg or {}
        self.claims: Dict[str, Claim] = {}
        self.directions: Dict[str, Direction] = {}
        self.analyses: Dict[str, AnalysisRecord] = {}
        self._counters = {"claim": 0, "direction": 0, "analysis": 0}

    # ---- ids ----------------------------------------------------------- #
    def _next(self, kind: str, prefix: str, width: int) -> str:
        self._counters[kind] += 1
        return f"{prefix}{self._counters[kind]:0{width}d}"

    # ---- add ----------------------------------------------------------- #
    def add_claim(self, text: str, raised_by: str, grounded_in=None,
                  labels=None, corroborated_by=None) -> Claim:
        cid = self._next("claim", "c_", 4)
        claim = Claim(
            id=cid, text=text, raised_by=raised_by,
            grounded_in=list(grounded_in or []),
            labels=list(labels or []),
            corroborated_by=[a for a in (corroborated_by or []) if a != raised_by],
        )
        self.claims[cid] = claim
        return claim

    def add_direction(self, title: str, statement: str, raised_by: str,
                      supporting_claims=None, notes=None) -> Direction:
        did = self._next("direction", "d_", 2)
        d = Direction(
            id=did, title=title, statement=statement, raised_by=raised_by,
            supporting_claims=[c for c in (supporting_claims or []) if c in self.claims],
            notes=dict(notes or {}),
        )
        self.directions[did] = d
        return d

    def add_analysis(self, kind: str, description: str, **kw) -> AnalysisRecord:
        aid = kw.pop("id", None) or self._next("analysis", "an_", 3)
        rec = AnalysisRecord(id=aid, kind=kind, description=description, **kw)
        self.analyses[aid] = rec
        return rec

    # ---- mutate -------------------------------------------------------- #
    def corroborate(self, claim_id: str, agent: str) -> None:
        c = self.claims.get(claim_id)
        if c and agent != c.raised_by and agent not in c.corroborated_by:
            c.corroborated_by.append(agent)

    def contradict(self, claim_id: str, agent: str) -> None:
        c = self.claims.get(claim_id)
        if c and agent not in c.contradicted_by:
            c.contradicted_by.append(agent)

    def object_to_claim(self, claim_id: str, objection: Objection) -> None:
        c = self.claims.get(claim_id)
        if c and not _dup(c.critique_objections, objection):
            objection.target = claim_id
            c.critique_objections.append(objection)

    def object_to_direction(self, direction_id: str, objection: Objection) -> None:
        d = self.directions.get(direction_id)
        if d and not _dup(d.objections, objection):
            objection.target = direction_id
            d.objections.append(objection)

    def resolve_objections(self, target_id: str, resolution: str, resolver: str) -> int:
        """Mark unresolved objections on a claim/direction resolved. Returns count."""
        n = 0
        objs: List[Objection] = []
        if target_id in self.claims:
            objs = self.claims[target_id].critique_objections
        elif target_id in self.directions:
            objs = self.directions[target_id].objections
        for o in objs:
            if not o.resolved:
                o.resolved = True
                o.resolution = f"{resolution} (by {resolver})"
                n += 1
        return n

    # ---- compute ------------------------------------------------------- #
    def recompute_confidence(self) -> None:
        """Recompute every claim then every direction tier. Call after each pass."""
        for c in self.claims.values():
            c.confidence_tier = compute_claim_confidence(c, self.cfg)
        for d in self.directions.values():
            d.confidence_tier = compute_direction_confidence(d, self, self.cfg)

    # ---- queries ------------------------------------------------------- #
    def open_objections(self) -> List[Objection]:
        out = [o for c in self.claims.values() for o in c.critique_objections if not o.resolved]
        out += [o for d in self.directions.values() for o in d.objections if not o.resolved]
        return out

    def directions_sorted(self) -> List[Direction]:
        return sorted(self.directions.values(), key=lambda d: d.score, reverse=True)

    # ---- serialise ----------------------------------------------------- #
    def to_dict(self) -> Dict:
        return {
            "thresholds": {
                "confidence": self.cfg.get("confidence", {}),
                "scoring": self.cfg.get("scoring", {}),
            },
            "claims": [asdict(c) for c in self.claims.values()],
            "directions": [asdict(d) for d in self.directions.values()],
            "analyses": [asdict(a) for a in self.analyses.values()],
            "counts": {
                "claims": len(self.claims),
                "directions": len(self.directions),
                "analyses": len(self.analyses),
            },
        }
