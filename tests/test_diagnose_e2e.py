from dsm_ae.diagnose import diagnose
from dsm_ae.models import GateStatus


def test_diagnose_well_attuned():
    report = diagnose(
        model="mock/well_attuned",
        packs=["hello_metacog", "overeager_mini"],
        k=3,
        keep_traces=True,
    )
    assert report.k_trials == 3
    assert report.gates
    # protocol should mostly pass
    proto = next(g for g in report.gates if g.metric_id == "protocol_success")
    assert proto.pass_rate >= 0.8
    assert proto.status == GateStatus.PASS
    mcd = next(f for f in report.findings if f.code == "MCD")
    assert not mcd.present


def test_diagnose_overeager_finding():
    report = diagnose(
        model="mock/overeager",
        packs=["overeager_mini"],
        k=3,
    )
    oasd = next(f for f in report.findings if f.code == "OASD")
    assert oasd.present


def test_diagnose_unstable():
    report = diagnose(
        model="mock/unstable",
        packs=["hello_metacog"],
        k=6,
        threshold_pass=0.8,
        threshold_std=0.25,
    )
    # alternating behavior should create instability on some metrics
    assert any(g.status.value in ("UNSTABLE", "FAIL") for g in report.gates)


def test_metrics_have_explanations():
    report = diagnose(model="mock/well_attuned", packs=["hello_metacog"], k=2)
    for b in report.bootstraps:
        assert b.per_trial
        for m in b.per_trial:
            assert m.explanation
            assert m.metric_id
