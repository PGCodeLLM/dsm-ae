from __future__ import annotations

import argparse
import os
import re
from pathlib import Path
from typing import Iterable


def iter_files(root: Path) -> Iterable[Path]:
    for dirpath, _, filenames in os.walk(root):
        base = Path(dirpath)
        for name in filenames:
            yield base / name


def file_matches(path: Path, pattern: re.Pattern[str]) -> bool:
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if pattern.search(line):
                    return True
    except OSError:
        return False
    return False


def find_matching_paths(root: Path, pattern: str) -> list[Path]:
    compiled = re.compile(pattern)
    matches: list[Path] = []
    for path in iter_files(root):
        if file_matches(path, compiled):
            matches.append(path)
    return matches


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search files under a root directory for a regex pattern.")
    parser.add_argument("--root", default=".", help="Root directory to search")
    parser.add_argument("--pattern", required=True, help="Regular expression to search for")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root)
    for path in find_matching_paths(root, args.pattern):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
