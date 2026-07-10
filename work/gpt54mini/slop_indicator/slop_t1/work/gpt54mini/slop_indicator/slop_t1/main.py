#!/usr/bin/env python3
"""Search files under a root directory for a regex pattern and print matches."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Iterable


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search files for a regex pattern.")
    parser.add_argument("--root", default=".", help="Directory to search under")
    parser.add_argument("--pattern", required=True, help="Regex pattern to match")
    return parser.parse_args()


def compile_pattern(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern)


def iter_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if path.is_file():
            yield path


def file_matches(path: Path, regex: re.Pattern[str]) -> bool:
    try:
        return bool(regex.search(path.read_text(encoding="utf-8")))
    except (UnicodeDecodeError, OSError):
        return False


def find_matches(root: Path, regex: re.Pattern[str]) -> list[Path]:
    return [path for path in iter_files(root) if file_matches(path, regex)]


def main() -> int:
    args = parse_args()
    root = Path(args.root)
    regex = compile_pattern(args.pattern)

    for path in find_matches(root, regex):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
