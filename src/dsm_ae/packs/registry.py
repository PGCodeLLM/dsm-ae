from __future__ import annotations

from dsm_ae.packs.base import IndicatorPack
from dsm_ae.packs.hello_metacog import HelloMetacogPack
from dsm_ae.packs.overeager_mini import OvereagerMiniPack
from dsm_ae.packs.slop_indicator import SlopIndicatorPack

PACKS: dict[str, IndicatorPack] = {
    p.id: p
    for p in (HelloMetacogPack(), OvereagerMiniPack(), SlopIndicatorPack())
}


def get_pack(pack_id: str) -> IndicatorPack:
    if pack_id not in PACKS:
        raise KeyError(f"Unknown pack {pack_id!r}. Available: {list(PACKS)}")
    return PACKS[pack_id]


def list_packs() -> list[str]:
    return sorted(PACKS)
