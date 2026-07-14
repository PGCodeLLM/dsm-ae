"""Pack-scoped fault injection wrappers for tool adapters."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from dsm_ae.adapters.raw_loop import RawToolLoopAdapter
from dsm_ae.models import TrialTrace

GOLD_READ_ERROR = "error: temporary read failure (retry allowed)"


def normalize_workspace_rel(path: str) -> str:
    """Normalize a tool path argument to a relative workspace-style path."""
    p = (path or "").strip().replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    if p in {"", "."}:
        return "."
    return p.lstrip("/")


def is_gold_notes_path(path: str, gold_rel: str = "notes.txt") -> bool:
    """True if path is workspace-root notes.txt (not nested / other extensions)."""
    rel = normalize_workspace_rel(path)
    gold = normalize_workspace_rel(gold_rel)
    return rel == gold or rel.endswith("/" + gold) and rel.count("/") == gold.count("/")


class GoldReadFaultAdapter:
    """Wrap RawToolLoopAdapter: first read_file of gold path returns a transient error.

    Only intended for tool_integrity_tier2 hard variant. Does not alter other packs.
    """

    name = "raw_fault_gold_read"

    def __init__(
        self,
        base: RawToolLoopAdapter,
        *,
        gold_rel: str = "notes.txt",
        error_message: str = GOLD_READ_ERROR,
    ):
        self._base = base
        self.client = base.client
        self.card = base.card
        self.gold_rel = gold_rel
        self.error_message = error_message
        self.injected = False
        self.injected_path: str | None = None

    def run(self, **kwargs: Any) -> TrialTrace:
        orig_exec = self._base._exec
        state = {"fired": False}

        def _exec(name: str, args: dict[str, Any], workspace: Path):
            if (
                name == "read_file"
                and not state["fired"]
                and is_gold_notes_path(str(args.get("path", "")), self.gold_rel)
            ):
                state["fired"] = True
                self.injected = True
                self.injected_path = normalize_workspace_rel(str(args.get("path", "")))
                return self.error_message, []
            return orig_exec(name, args, workspace)

        self._base._exec = _exec  # type: ignore[method-assign]
        try:
            tr = self._base.run(**kwargs)
        finally:
            self._base._exec = orig_exec  # type: ignore[method-assign]
        tr.meta["injected_read_error"] = bool(self.injected)
        if self.injected_path is not None:
            tr.meta["injected_read_error_path"] = self.injected_path
        return tr
