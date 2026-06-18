"""Unit tests for the computed-confidence function (build spec v2 §6, build
order step 1). Plain asserts; run with:  python tests/test_ledger.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mars.ledger import (  # noqa: E402
    Grounding, Objection, Ledger,
    compute_claim_confidence, compute_direction_confidence, HIGH, MEDIUM, LOW,
)

CFG = {"confidence": {"min_corroborators_for_high": 2, "blocking_severity": "high",
                      "contradiction_caps_low": True}}
PAPER = [Grounding("paper", "smith2021", "p4")]


def _claim(L, **kw):
    c = L.add_claim(kw.get("text", "x"), kw.get("raised_by", "literature"),
                    grounded_in=kw.get("grounded_in", PAPER))
    c.corroborated_by = kw.get("corroborated_by", [])
    c.contradicted_by = kw.get("contradicted_by", [])
    c.critique_objections = kw.get("objections", [])
    return c


def test_claim_confidence():
    L = Ledger(CFG)
    # 1. not grounded -> low
    assert compute_claim_confidence(_claim(L, grounded_in=[]), CFG) == LOW
    # 2. grounded, single-agent, uncontested -> medium
    assert compute_claim_confidence(_claim(L), CFG) == MEDIUM
    # 3. grounded + 2 independent corroborators -> high
    assert compute_claim_confidence(_claim(L, corroborated_by=["data", "methods"]), CFG) == HIGH
    # 4. corroborators that are just the raiser don't count -> medium
    assert compute_claim_confidence(
        _claim(L, raised_by="literature", corroborated_by=["literature"]), CFG) == MEDIUM
    # 5. contradicted -> low (even with corroboration)
    assert compute_claim_confidence(
        _claim(L, corroborated_by=["data", "methods"], contradicted_by=["red_team"]), CFG) == LOW
    # 6. unresolved HIGH-severity objection -> low
    assert compute_claim_confidence(
        _claim(L, corroborated_by=["data", "methods"],
               objections=[Objection("critique", "confound", "high")]), CFG) == LOW
    # 7. unresolved MEDIUM (sub-blocking) objection -> capped at medium, not high
    assert compute_claim_confidence(
        _claim(L, corroborated_by=["data", "methods"],
               objections=[Objection("critique", "minor", "medium")]), CFG) == MEDIUM
    # 8. resolved objection no longer caps -> high
    assert compute_claim_confidence(
        _claim(L, corroborated_by=["data", "methods"],
               objections=[Objection("critique", "x", "high", resolved=True)]), CFG) == HIGH
    print("  ok  claim confidence (8 cases)")


def test_direction_confidence():
    L = Ledger(CFG)
    hi = _claim(L, corroborated_by=["data", "methods"])          # high
    med = _claim(L)                                              # medium
    L.recompute_confidence()

    d_hi = L.add_direction("D1", "stmt", "hypothesis", supporting_claims=[hi.id])
    assert compute_direction_confidence(d_hi, L, CFG) == HIGH

    d_med = L.add_direction("D2", "stmt", "hypothesis", supporting_claims=[med.id])
    assert compute_direction_confidence(d_med, L, CFG) == MEDIUM

    # blocking objection on the direction caps it low (critique-as-gate)
    d_blocked = L.add_direction("D3", "stmt", "hypothesis", supporting_claims=[hi.id])
    L.object_to_direction(d_blocked.id, Objection("critique", "already done", "high"))
    assert compute_direction_confidence(d_blocked, L, CFG) == LOW

    # sub-blocking unresolved objection caps a would-be-high direction at medium
    d_capped = L.add_direction("D4", "stmt", "hypothesis", supporting_claims=[hi.id])
    L.object_to_direction(d_capped.id, Objection("critique", "needs check", "medium"))
    assert compute_direction_confidence(d_capped, L, CFG) == MEDIUM

    # resolving the objection lets it reach high again
    L.resolve_objections(d_blocked.id, "scout found it is novel", "editorial")
    assert compute_direction_confidence(d_blocked, L, CFG) == HIGH

    # no grounded support -> low
    ungrounded = _claim(L, grounded_in=[])
    d_ungrounded = L.add_direction("D5", "stmt", "hypothesis", supporting_claims=[ungrounded.id])
    assert compute_direction_confidence(d_ungrounded, L, CFG) == LOW
    print("  ok  direction confidence (6 cases)")


if __name__ == "__main__":
    test_claim_confidence()
    test_direction_confidence()
    print("ALL LEDGER TESTS PASSED")
