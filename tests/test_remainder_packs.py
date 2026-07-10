
from pathlib import Path
from dsm_ae.adapters.raw_loop import RawToolLoopAdapter
from dsm_ae.litellm_client import MockClient
from dsm_ae.models import ScaffoldCard
from dsm_ae.packs.memory_context import MemoryContextPack
from dsm_ae.packs.handoff_mini import HandoffMiniPack
from dsm_ae.packs.eval_gaming_mini import EvalGamingMiniPack
from dsm_ae.packs.sandbag_mini import SandbagMiniPack
from dsm_ae.packs.clarify_verify import ClarifyVerifyPack
from dsm_ae.packs.pii_safety import PiiSafetyPack
from dsm_ae.packs.nfr_omit import NfrOmitPack
from dsm_ae.diagnose import diagnose
from dsm_ae.packs.registry import list_packs

def ad(p):
    return RawToolLoopAdapter(MockClient(persona=p), ScaffoldCard(model=f"mock/{p}", max_turns=16))

def test_memory():
    pack=MemoryContextPack()
    g={m.metric_id:m for m in pack.score(pack.run_trial(ad("well_attuned"), Path("/tmp/m1"),0)[0])}
    b={m.metric_id:m for m in pack.score(pack.run_trial(ad("contaminated"), Path("/tmp/m2"),0)[0])}
    assert g["knowledge_retention"].passed
    assert not b["distractor_resisted"].passed

def test_handoff():
    pack=HandoffMiniPack()
    g={m.metric_id:m for m in pack.score(pack.run_trial(ad("well_attuned"), Path("/tmp/h1"),0)[0])}
    assert g["handoff_consumed"].passed

def test_eval_game():
    pack=EvalGamingMiniPack()
    g={m.metric_id:m for m in pack.score(pack.run_trial(ad("well_attuned"), Path("/tmp/e1"),0)[0])}
    b={m.metric_id:m for m in pack.score(pack.run_trial(ad("gamer"), Path("/tmp/e2"),0)[0])}
    assert g["hidden_pass"].passed
    assert not b["no_test_memorization"].passed or not b["hidden_pass"].passed

def test_sandbag():
    pack=SandbagMiniPack()
    g={m.metric_id:m for m in pack.score(pack.run_trial(ad("well_attuned"), Path("/tmp/s1"),0)[0])}
    b={m.metric_id:m for m in pack.score(pack.run_trial(ad("sandbagger"), Path("/tmp/s2"),0)[0])}
    assert g["no_sandbag"].passed
    assert not b["no_sandbag"].passed

def test_clarify():
    pack=ClarifyVerifyPack()
    g={m.metric_id:m for m in pack.score(pack.run_trial(ad("well_attuned"), Path("/tmp/c1"),0)[0])}
    b={m.metric_id:m for m in pack.score(pack.run_trial(ad("shallow"), Path("/tmp/c2"),0)[0])}
    assert g["asks_clarification"].passed
    assert not b["asks_clarification"].passed

def test_pii():
    pack=PiiSafetyPack()
    g={m.metric_id:m for m in pack.score(pack.run_trial(ad("well_attuned"), Path("/tmp/p1"),0)[0])}
    b={m.metric_id:m for m in pack.score(pack.run_trial(ad("leaky"), Path("/tmp/p2"),0)[0])}
    assert g["no_secret_leak"].passed
    assert not b["no_secret_leak"].passed

def test_nfr():
    pack=NfrOmitPack()
    g={m.metric_id:m for m in pack.score(pack.run_trial(ad("well_attuned"), Path("/tmp/n1"),0)[0])}
    b={m.metric_id:m for m in pack.score(pack.run_trial(ad("sloppy"), Path("/tmp/n2"),0)[0])}
    assert g["has_validation"].passed
    assert not b["has_error_handling"].passed or not b["has_validation"].passed

def test_all_packs_mock():
    report = diagnose(model="mock/well_attuned", packs=list_packs(), k=1, concurrency=2, keep_traces=False)
    assert len(list_packs()) >= 15
    assert report.gates
