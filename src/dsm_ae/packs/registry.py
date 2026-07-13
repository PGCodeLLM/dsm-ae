from __future__ import annotations

from dsm_ae.packs.base import IndicatorPack
from dsm_ae.packs.clarify_verify import ClarifyVerifyPack
from dsm_ae.packs.coord_tax_mini import CoordTaxMiniPack
from dsm_ae.packs.eval_gaming_mini import EvalGamingMiniPack
from dsm_ae.packs.gate_discipline import GateDisciplinePack
from dsm_ae.packs.handoff_mini import HandoffMiniPack
from dsm_ae.packs.hello_metacog import HelloMetacogPack
from dsm_ae.packs.injection_mini import InjectionMiniPack
from dsm_ae.packs.loop_control import LoopControlPack
from dsm_ae.packs.mas_verify_mini import MasVerifyMiniPack
from dsm_ae.packs.memory_context import MemoryContextPack
from dsm_ae.packs.nfr_omit import NfrOmitPack
from dsm_ae.packs.overeager_mini import OvereagerMiniPack
from dsm_ae.packs.pii_safety import PiiSafetyPack
from dsm_ae.packs.role_confusion_mini import RoleConfusionMiniPack
from dsm_ae.packs.sandbag_mini import SandbagMiniPack
from dsm_ae.packs.session_overwrite_mini import SessionOverwriteMiniPack
from dsm_ae.packs.erosion_tier2 import ErosionTier2Pack
from dsm_ae.packs.erosion_tier3 import ErosionTier3Pack
from dsm_ae.packs.slop_indicator import SlopIndicatorPack
from dsm_ae.packs.sycophancy_mini import SycophancyMiniPack
from dsm_ae.packs.tool_integrity import ToolIntegrityPack

_PACK_INSTANCES: list[IndicatorPack] = [
    HelloMetacogPack(),
    OvereagerMiniPack(),
    SlopIndicatorPack(),
    ErosionTier2Pack(),
    ErosionTier3Pack(),
    LoopControlPack(),
    ToolIntegrityPack(),
    SycophancyMiniPack(),
    InjectionMiniPack(),
    GateDisciplinePack(),
    MemoryContextPack(),
    HandoffMiniPack(),
    EvalGamingMiniPack(),
    SandbagMiniPack(),
    ClarifyVerifyPack(),
    PiiSafetyPack(),
    NfrOmitPack(),
    RoleConfusionMiniPack(),
    MasVerifyMiniPack(),
    SessionOverwriteMiniPack(),
    CoordTaxMiniPack(),
]

PACKS: dict[str, IndicatorPack] = {p.id: p for p in _PACK_INSTANCES}


def get_pack(pack_id: str) -> IndicatorPack:
    if pack_id not in PACKS:
        raise KeyError(f"Unknown pack {pack_id!r}. Available: {list(PACKS)}")
    return PACKS[pack_id]


def list_packs() -> list[str]:
    return sorted(PACKS)


def pack_pattern_index() -> dict[str, list[str]]:
    idx: dict[str, list[str]] = {}
    for p in _PACK_INSTANCES:
        for code in p.patterns:
            idx.setdefault(code, []).append(p.id)
    return idx
