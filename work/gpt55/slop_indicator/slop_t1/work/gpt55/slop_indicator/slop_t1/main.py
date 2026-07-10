#!/usr/bin/env python3
"""Search files under a root directory for a regular expression."""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path
from typing import Iterable, Pattern


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Print paths of files whose contents match a regex pattern."
    )
    parser.add_argument(
        "root",
        nargs="?",
        default=".",
        help="Root directory to search (default: current directory).",
    )
    parser.add_argument(
        "--pattern",
        required=True,
        help="Regular expression to search for in file contents.",
    )
    return parser.parse_args()


def iter_files(root: Path) -> Iterable[Path]:
    """Yield regular files under root recursively."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for filename in sorted(filenames):
            path = Path(dirpath) / filename
            if path.is_file():
                yield path


def file_matches(path: Path, pattern: Pattern[str]) -> bool:
    """Return True if the text file contains the compiled regex pattern."""
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                if pattern.search(line):
                    return True
    except OSError:
        return False
    return False


def find_matches(root: Path, pattern: Pattern[str]) -> Iterable[Path]:
    """Yield paths of files under root whose contents match pattern."""
    for path in iter_files(root):
        if file_matches(path, pattern):
            yield path


def main() -> int:
    """Run the CLI."""
    args = parse_args()
    root = Path(args.root)
    pattern = re.compile(args.pattern)

    for path in find_matches(root, pattern):
        print(path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
