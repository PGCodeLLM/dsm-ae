from dsm_ae.metric_citations import (
    METRIC_CITATIONS,
    REFERENCES,
    citations_for_metric,
    format_cite_keys,
    references_used,
)


def test_overeager_cites_qu():
    ids = citations_for_metric("overeager_rate")
    assert 1 in ids
    assert format_cite_keys(ids) == ",".join(str(i) for i in sorted(set(ids)))


def test_all_mapped_refs_exist():
    for metric, ids in METRIC_CITATIONS.items():
        for i in ids:
            assert i in REFERENCES, f"metric {metric} cites missing ref {i}"


def test_references_used_subset():
    used = references_used(["overeager_rate", "erosion_indicator"])
    assert 1 in used and 2 in used
    assert set(used) <= set(REFERENCES)
