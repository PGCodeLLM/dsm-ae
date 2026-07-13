"""Smoke / floor metric labels for weak gates (tier1).

These metrics remain useful as *floor* checks but are not diagnostic of the
full taxonomy construct (CQ-01 slope, BMAD prose verbosity, multi-channel
injection, etc.). Reports and matrix HTML should badge them as smoke.
"""

from __future__ import annotations

# Canonical smoke metric ids (tier1 / floor definitions).
SMOKE_METRIC_IDS: frozenset[str] = frozenset(
    {
        # erosion tier1 (legacy + explicit)
        "erosion_indicator",
        "erosion_indicator.tier1",
        # verbosity / quality floor (current definitions)
        "verbosity_indicator",
        "verbosity_indicator.tier1",
        "quality_stable",
        "quality_stable.tier1",
        # injection critical resource floor
        "critical_preserved",
        "critical_preserved.tier1",
    }
)

SMOKE_BADGE = "SMOKE/FLOOR"
SMOKE_NOTE = (
    "Smoke/floor metric (tier1): saturates easily; not full CQ/AA diagnostic. "
    "See docs/superpowers/specs/weak-metric-audits/."
)


def is_smoke_metric(metric_id: str) -> bool:
    mid = (metric_id or "").strip()
    if mid in SMOKE_METRIC_IDS:
        return True
    # any explicit .tier1 suffix is smoke by convention
    if mid.endswith(".tier1"):
        return True
    return False


def smoke_prefix(metric_id: str) -> str:
    if is_smoke_metric(metric_id):
        return f"[{SMOKE_BADGE}] "
    return ""


def annotate_smoke_explanation(metric_id: str, explanation: str) -> str:
    """Ensure smoke metrics carry an explicit badge in the explanation string."""
    exp = explanation or ""
    if not is_smoke_metric(metric_id):
        return exp
    if SMOKE_BADGE in exp:
        return exp
    return f"[{SMOKE_BADGE}] {exp}"
