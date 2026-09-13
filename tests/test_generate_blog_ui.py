"""Unit tests for blog UI preprocess (mermaid + fence languages)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_MOD = Path(__file__).resolve().parents[1] / "scripts" / "generate_blog_ui.py"
_spec = importlib.util.spec_from_file_location("generate_blog_ui", _MOD)
assert _spec and _spec.loader
_blog = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_blog)

infer_fence_lang = _blog.infer_fence_lang
preprocess_markdown = _blog.preprocess_markdown
text_pipeline_to_mermaid = _blog.text_pipeline_to_mermaid


def test_pipeline_text_becomes_mermaid() -> None:
    src = """\
```text
  representative tasks
       ↓  (outer oracle)
  success ∪ fail
       ↓
  clusters
```
"""
    out = preprocess_markdown(src)
    assert out.startswith("```mermaid\n")
    assert "flowchart TD" in out
    assert "representative tasks" in out
    assert "outer oracle" in out


def test_atom_log_stays_text() -> None:
    src = """\
```text
  1 read_file    persistence/album.go
  2 read_file    persistence/artist.go
  3 edit         model/album.go
```
"""
    out = preprocess_markdown(src)
    assert out.startswith("```text\n")
    assert "mermaid" not in out


def test_instance_card_stays_text() -> None:
    src = """\
```text
instance : cais/instance_navidrome
trial    : instance_navidrome__Uh6sAuW
harness  : opencode 1.18.18
```
"""
    assert text_pipeline_to_mermaid(src.split("```text")[1]) is None
    assert preprocess_markdown(src).startswith("```text\n")


def test_unlabeled_python_gets_language() -> None:
    src = """\
```
from pathlib import Path
print(Path('.'))
```
"""
    out = preprocess_markdown(src)
    assert out.startswith("```python\n")


def test_unlabeled_bash_gets_language() -> None:
    src = """\
```
export DSM_MONGO_URI=mongodb://localhost:27018/
python3 scripts/mine_sessions.py --session-id f4ac2beb --stats
```
"""
    out = preprocess_markdown(src)
    assert out.startswith("```bash\n")


def test_infer_keeps_explicit_lang() -> None:
    assert infer_fence_lang("python", "not python looking") == "python"
    assert infer_fence_lang("mermaid", "flowchart TD") == "mermaid"
