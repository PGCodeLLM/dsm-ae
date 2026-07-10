from __future__ import annotations

from dsm_ae.packs.base import IndicatorPack
from dsm_ae.packs.gate_discipline import GateDisciplinePack
from dsm_ae.packs.hello_metacog import HelloMetacogPack
from dsm_ae.packs.injection_mini import InjectionMiniPack
from dsm_ae.packs.loop_control import LoopControlPack
from dsm_ae.packs.overeager_mini import OvereagerMiniPack
from dsm_ae.packs.slop_indicator import SlopIndicatorPack
from dsm_ae.packs.sycophancy_mini import SycophancyMiniPack
from dsm_ae.packs.tool_integrity import ToolIntegrityPack

_PACK_INSTANCES: list[IndicatorPack] = [
    HelloMetacogPack(),
    OvereagerMiniPack(),
    SlopIndicatorPack(),
    LoopControlPack(),
    ToolIntegrityPack(),
    SycophancyMiniPack(),
    InjectionMiniPack(),
    GateDisciplinePack(),
]

PACKS: dict[str, IndicatorPack] = {p.id: p for p in _PACK_INSTANCES}


def get_pack(pack_id: str) -> IndicatorPack:
    if pack_id not in PACKS:
        raise KeyError(f"Unknown pack {pack_id!r}. Available: {list(PACKS)}")
    return PACKS[pack_id]


def list_packs() -> list[str]:
    return sorted(PACKS)


def pack_pattern_index() -> dict[str, list[str]]:
    """pattern code -> list of pack ids that measure it."""
    idx: dict[str, list[str]] = {}
    for p in _PACK_INSTANCES:
        for code in p.patterns:
            idx.setdefault(code, []).append(p.id)
    return idx
