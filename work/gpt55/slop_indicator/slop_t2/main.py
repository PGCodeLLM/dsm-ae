"""Simple recursive regex search CLI."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Iterable, Pattern


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Search files under root for a regex pattern.")
    parser.add_argument("root", help="Directory to search recursively")
    parser.add_argument("--pattern", required=True, help="Regular expression to search for")
    parser.add_argument(
        "--langs",
        nargs="*",
        default=None,
        help="Optional file extension filter, e.g. --langs .py .js",
    )
    return parser.parse_args()


def compile_pattern(pattern: str) -> Pattern[str]:
    """Compile a regex pattern, raising re.error if it is invalid."""
    return re.compile(pattern)


def normalize_langs(langs: list[str] | None) -> set[str] | None:
    """Normalize optional extension filters to a set beginning with dots."""
    if not langs:
        return None
    return {lang if lang.startswith(".") else f".{lang}" for lang in langs}


def path_matches_langs(path: Path, langs: set[str] | None) -> bool:
    """Return True when path is allowed by the optional extension filter."""
    return langs is None or path.suffix in langs


def iter_files(root: Path, langs: set[str] | None = None) -> Iterable[Path]:
    """Yield regular files below root recursively, optionally filtered by extension."""
    if root.is_file():
        if path_matches_langs(root, langs):
            yield root
        return

    for path in root.rglob("*"):
        if path.is_file() and path_matches_langs(path, langs):
            yield path


def file_matches(path: Path, pattern: Pattern[str]) -> bool:
    """Return True if pattern appears in the file's text content."""
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                if pattern.search(line):
                    return True
    except OSError:
        return False
    return False


def print_matching_paths(root: Path, pattern: Pattern[str], langs: set[str] | None = None) -> None:
    """Print each allowed file path under root whose contents match pattern."""
    for path in iter_files(root, langs):
        if file_matches(path, pattern):
            print(path)


def main() -> None:
    args = parse_args()
    root = Path(args.root)

    if not root.exists():
        print(f"error: root does not exist: {root}", file=sys.stderr)
        raise SystemExit(2)

    try:
        pattern = compile_pattern(args.pattern)
    except re.error as exc:
        print(f"error: invalid regex: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc

    langs = normalize_langs(args.langs)
    print_matching_paths(root, pattern, langs)


if __name__ == "__main__":
    main()
