from pathlib import Path

from dsm_ae.adapters.raw_loop import RawToolLoopAdapter
from dsm_ae.litellm_client import MockClient
from dsm_ae.models import ScaffoldCard
from dsm_ae.packs.gate_discipline import GateDisciplinePack
from dsm_ae.packs.injection_mini import InjectionMiniPack
from dsm_ae.packs.loop_control import LoopControlPack
from dsm_ae.packs.sycophancy_mini import SycophancyMiniPack
from dsm_ae.packs.tool_integrity import ToolIntegrityPack


def _adapter(persona: str) -> RawToolLoopAdapter:
    card = ScaffoldCard(model=f"mock/{persona}", k_trials=1, max_turns=16)
    return RawToolLoopAdapter(MockClient(persona=persona), card)


def test_loop_well_attuned(tmp_path: Path):
    pack = LoopControlPack()
    tr = pack.run_trial(_adapter("well_attuned"), tmp_path, 0)[0]
    by = {m.metric_id: m for m in pack.score(tr)}
    assert by["all_files_read"].passed
    assert by["count_correct"].passed
    assert by["no_read_loop"].passed


def test_loop_persona_fails(tmp_path: Path):
    pack = LoopControlPack()
    tr = pack.run_trial(_adapter("looping"), tmp_path, 0)[0]
    by = {m.metric_id: m for m in pack.score(tr)}
    assert not by["all_files_read"].passed or not by["no_read_loop"].passed


def test_tool_halluc(tmp_path: Path):
    pack = ToolIntegrityPack()
    tr = pack.run_trial(_adapter("tool_halluc"), tmp_path, 0)[0]
    by = {m.metric_id: m for m in pack.score(tr)}
    assert not by["no_tool_hallucination"].passed


def test_tool_ok(tmp_path: Path):
    pack = ToolIntegrityPack()
    tr = pack.run_trial(_adapter("well_attuned"), tmp_path, 0)[0]
    by = {m.metric_id: m for m in pack.score(tr)}
    assert by["no_tool_hallucination"].passed
    assert by["task_tool_success"].passed


def test_sycophancy(tmp_path: Path):
    pack = SycophancyMiniPack()
    good = pack.score(pack.run_trial(_adapter("well_attuned"), tmp_path / "g", 0)[0])
    bad = pack.score(pack.run_trial(_adapter("sycophant"), tmp_path / "b", 0)[0])
    assert {m.metric_id: m for m in good}["resists_wrong_user"].passed
    assert not {m.metric_id: m for m in bad}["resists_wrong_user"].passed


def test_injection(tmp_path: Path):
    pack = InjectionMiniPack()
    good = {m.metric_id: m for m in pack.score(pack.run_trial(_adapter("well_attuned"), tmp_path / "g", 0)[0])}
    bad = {m.metric_id: m for m in pack.score(pack.run_trial(_adapter("injectable"), tmp_path / "b", 0)[0])}
    assert good["injection_resisted"].passed
    assert not bad["injection_resisted"].passed


def test_gate(tmp_path: Path):
    pack = GateDisciplinePack()
    good = {m.metric_id: m for m in pack.score(pack.run_trial(_adapter("well_attuned"), tmp_path / "g", 0)[0])}
    bad = {m.metric_id: m for m in pack.score(pack.run_trial(_adapter("ungated"), tmp_path / "b", 0)[0])}
    assert good["approval_before_delete"].passed
    assert not bad["no_ungated_delete"].passed
