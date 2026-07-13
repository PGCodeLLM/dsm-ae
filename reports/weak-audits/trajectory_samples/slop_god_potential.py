"""Recursively print files whose contents match a regular expression."""

import argparse
import re
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Pattern


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="file or directory to search")
    parser.add_argument("--pattern", required=True, help="regular expression to find")
    parser.add_argument(
        "--langs",
        nargs="+",
        metavar="EXT",
        help="only search files with these extensions (for example: .py .js)",
    )
    return parser.parse_args()


def iter_files(root: Path) -> Iterator[Path]:
    if root.is_file():
        yield root
    elif root.is_dir():
        yield from (path for path in root.rglob("*") if path.is_file())


def normalize_extensions(langs: Iterable[str]) -> set[str]:
    return {lang if lang.startswith(".") else f".{lang}" for lang in langs}


def filter_languages(paths: Iterable[Path], langs: Iterable[str] | None) -> Iterator[Path]:
    if langs is None:
        yield from paths
        return

    extensions = normalize_extensions(langs)
    yield from (path for path in paths if path.suffix in extensions)


def file_matches(path: Path, pattern: Pattern[str]) -> bool:
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as stream:
            return any(pattern.search(line) for line in stream)
    except OSError:
        return False


def compile_pattern(value: str) -> Pattern[str]:
    try:
        return re.compile(value)
    except re.error as error:
        raise ValueError(f"invalid regular expression: {error}") from error


def main() -> None:
    args = parse_args()
    try:
        pattern = compile_pattern(args.pattern)
    except ValueError as error:
        raise SystemExit(str(error)) from error

    for path in filter_languages(iter_files(args.root), args.langs):
        if file_matches(path, pattern):
            print(path)


if __name__ == "__main__":
    main()
