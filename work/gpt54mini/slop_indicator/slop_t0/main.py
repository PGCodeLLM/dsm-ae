#!/usr/bin/env python3
"""Search files under a root directory for paths matching a regex pattern."""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path
from typing import Iterable, Sequence


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search files under root for matching paths")
    parser.add_argument("--root", default=".", help="Root directory to search")
    parser.add_argument("--pattern", required=True, help="Regex to match against file paths")
    parser.add_argument(
        "--langs",
        nargs="*",
        default=None,
        help="Optional file extensions to include, e.g. .py .js",
    )
    return parser.parse_args()


def iter_files(root: Path) -> Iterable[Path]:
    for dirpath, _, filenames in os.walk(root):
        base = Path(dirpath)
        for name in filenames:
            yield base / name


def normalize_langs(langs: Sequence[str] | None) -> set[str] | None:
    if not langs:
        return None
    normalized = set()
    for lang in langs:
        normalized.add(lang if lang.startswith(".") else f".{lang}")
    return normalized


def file_matches_lang(path: Path, langs: set[str] | None) -> bool:
    if langs is None:
        return True
    return path.suffix in langs


def print_matches(root: Path, pattern: re.Pattern[str], langs: set[str] | None) -> None:
    for path in iter_files(root):
        if not file_matches_lang(path, langs):
            continue
        rel = path.relative_to(root)
        if pattern.search(str(rel)):
            print(rel)


def main() -> int:
    args = parse_args()
    root = Path(args.root)
    pattern = re.compile(args.pattern)
    langs = normalize_langs(args.langs)
    print_matches(root, pattern, langs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
