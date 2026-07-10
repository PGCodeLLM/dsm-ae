"""Command-line file path search utility."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Iterable, Pattern, Sequence


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Search files under ROOT and print paths matching a regex."
    )
    parser.add_argument("root", help="Directory to search under")
    parser.add_argument("--pattern", required=True, help="Regular expression to match paths")
    parser.add_argument(
        "--langs",
        nargs="*",
        default=None,
        help="Optional file extensions to include, such as .py .js",
    )
    return parser.parse_args()


def compile_pattern(pattern: str) -> Pattern[str]:
    """Compile a regex pattern, raising a clear error on failure."""
    try:
        return re.compile(pattern)
    except re.error as exc:
        raise SystemExit(f"invalid --pattern: {exc}") from exc


def normalize_langs(langs: Sequence[str] | None) -> set[str] | None:
    """Return normalized extension filters, or None when no filter was supplied."""
    if langs is None:
        return None

    normalized: set[str] = set()
    for lang in langs:
        lang = lang.strip()
        if not lang:
            continue
        normalized.add(lang if lang.startswith(".") else f".{lang}")
    return normalized


def iter_files(root: Path) -> Iterable[Path]:
    """Yield files beneath root recursively."""
    if root.is_file():
        yield root
        return

    for path in root.rglob("*"):
        if path.is_file():
            yield path


def language_matches(path: Path, langs: set[str] | None) -> bool:
    """Return True when path passes the optional language/extension filter."""
    if langs is None:
        return True
    return path.suffix in langs


def matching_paths(
    root: Path, pattern: Pattern[str], langs: set[str] | None = None
) -> Iterable[Path]:
    """Yield files whose path matches pattern and optional extension filters."""
    for path in iter_files(root):
        if language_matches(path, langs) and pattern.search(str(path)):
            yield path


def main() -> None:
    """Run the search CLI."""
    args = parse_args()
    root = Path(args.root)
    pattern = compile_pattern(args.pattern)
    langs = normalize_langs(args.langs)

    for path in matching_paths(root, pattern, langs):
        print(path)


if __name__ == "__main__":
    main()
