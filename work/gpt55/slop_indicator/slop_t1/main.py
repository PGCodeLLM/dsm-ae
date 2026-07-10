#!/usr/bin/env python3
"""A small source-file scanner with optional language filtering.

The program walks a directory (or analyses a single file) and prints a simple
line-count report for the files it can read as text.  Use ``--langs`` to limit
which file extensions are considered, for example::

    python main.py src --langs .py .js

Extensions may be supplied with or without the leading dot and matching is
case-insensitive.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Sequence


@dataclass(frozen=True)
class FileReport:
    """Summary for one analysed file."""

    path: Path
    lines: int


DEFAULT_EXCLUDED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    "node_modules",
    ".mypy_cache",
    ".pytest_cache",
    ".venv",
    "venv",
}


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line parser."""

    parser = argparse.ArgumentParser(description="Scan text/source files and report line counts.")
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="File or directory to scan (defaults to the current directory).",
    )
    parser.add_argument(
        "--langs",
        nargs="+",
        metavar="EXT",
        help="Optional extension filter, e.g. --langs .py .js (dots are optional).",
    )
    return parser


def normalize_lang(lang: str) -> str:
    """Normalize one language/extension value for comparison."""

    cleaned = lang.strip().lower()
    if not cleaned:
        raise ValueError("language extensions passed to --langs must not be empty")
    return cleaned if cleaned.startswith(".") else f".{cleaned}"


def normalize_langs(langs: Sequence[str] | None) -> set[str] | None:
    """Return a normalized extension set, or None when no filter was supplied."""

    if langs is None:
        return None
    return {normalize_lang(lang) for lang in langs}


def matches_lang_filter(path: Path, langs: set[str] | None) -> bool:
    """Return True when *path* should be analysed for the given extension set."""

    if langs is None:
        return True
    return path.suffix.lower() in langs


def should_skip_dir(path: Path) -> bool:
    """Return True for directories that should not be traversed."""

    return path.name in DEFAULT_EXCLUDED_DIRS


def iter_candidate_files(root: Path, langs: set[str] | None = None) -> Iterator[Path]:
    """Yield files below *root* that match the optional extension filter."""

    if root.is_file():
        if matches_lang_filter(root, langs):
            yield root
        return

    for child in sorted(root.iterdir(), key=lambda p: (not p.is_dir(), str(p).lower())):
        if child.is_dir():
            if not should_skip_dir(child):
                yield from iter_candidate_files(child, langs)
        elif child.is_file() and matches_lang_filter(child, langs):
            yield child


def count_text_lines(path: Path) -> int | None:
    """Return the number of lines in a text file, or None for unreadable/binary files."""

    try:
        with path.open("r", encoding="utf-8") as handle:
            return sum(1 for _ in handle)
    except (UnicodeDecodeError, OSError):
        return None


def analyse_files(files: Iterable[Path]) -> list[FileReport]:
    """Analyse each candidate file and return successful reports."""

    reports: list[FileReport] = []
    for path in files:
        line_count = count_text_lines(path)
        if line_count is not None:
            reports.append(FileReport(path=path, lines=line_count))
    return reports


def format_path(path: Path, base: Path) -> str:
    """Format paths relative to the scan root when possible."""

    try:
        return str(path.relative_to(base if base.is_dir() else base.parent))
    except ValueError:
        return str(path)


def print_report(reports: Sequence[FileReport], root: Path) -> None:
    """Print a compact, deterministic report."""

    total_lines = sum(report.lines for report in reports)
    print(f"Analyzed files: {len(reports)}")
    print(f"Total lines: {total_lines}")
    for report in reports:
        print(f"{format_path(report.path, root)}\t{report.lines}")


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point."""

    parser = build_parser()
    args = parser.parse_args(argv)

    root = Path(args.path)
    if not root.exists():
        parser.error(f"path does not exist: {root}")

    try:
        langs = normalize_langs(args.langs)
    except ValueError as exc:
        parser.error(str(exc))

    reports = analyse_files(iter_candidate_files(root, langs))
    print_report(reports, root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
