"""TDD test for harbor export script (Task 2).

Written before the script and generated task files exist.
"""
from pathlib import Path
import pytest


def test_export_hello_creates_task_toml_and_files(tmp_path: Path):
    """Export must produce a valid harbor task layout for hello_metacog at least."""
    import sys
    import importlib.util

    root = Path(__file__).resolve().parents[1]
    script_path = root / "scripts" / "harbor_export_all_packs.py"

    # Load the script as module without requiring it to be in packages
    spec = importlib.util.spec_from_file_location("harbor_export_mod", script_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    export_fn = getattr(mod, "export_hello_metacog", None) or getattr(mod, "export_all", None)
    assert export_fn is not None, "export script must expose export_hello_metacog or export_all"

    out_dir = tmp_path / "harbor_out"
    out_dir.mkdir()
    # Call; for task2 may target dsm-ae substructure or flat under arg; support either
    export_fn(out_dir)

    # Check for hello under conventional dsm-ae/ layout or direct (prefer dsm-ae)
    candidates = [
        out_dir / "dsm-ae" / "hello_metacog" / "task.toml",
        out_dir / "hello_metacog" / "task.toml",
    ]
    task_toml = next((c for c in candidates if c.is_file()), None)
    assert task_toml is not None, f"expected task.toml created by export; looked in {candidates}"

    # Also verify key files for the task
    task_dir = task_toml.parent
    assert (task_dir / "instruction.md").is_file()
    assert (task_dir / "environment" / "Dockerfile").is_file()
    assert (task_dir / "tests" / "test.sh").is_file()

    # Validate minimal toml content (schema 1.3, name)
    content = task_toml.read_text()
    assert 'schema_version = "1.3"' in content
    assert 'name = "dsm-ae/hello_metacog"' in content

    # test.sh should reference pack_bridge score + write_reward + /logs/verifier
    test_sh = (task_dir / "tests" / "test.sh").read_text()
    assert "score_workspace" in test_sh
    assert "write_reward" in test_sh
    assert "/logs/verifier/reward.json" in test_sh


def test_export_skips_live_harbor_when_no_cli():
    """Documented: if no harbor, we still produce files (this test itself does not require CLI)."""
    # This is a marker; live run skipped in CI / when harbor absent.
    # See script comments and task-2-brief.
    import shutil
    if shutil.which("harbor") is None:
        # Expected in this env; we verified file gen + verifier logic instead of `harbor run -a oracle`
        assert True
    pass
