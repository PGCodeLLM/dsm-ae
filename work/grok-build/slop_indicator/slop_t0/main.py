"""search CLI — finds files under root whose content matches --pattern (regex)."""

import argparse
import re
from pathlib import Path


def file_matches(path: Path, regex: re.Pattern[str]) -> bool:
    """Return True if file content matches regex (ignore decode errors)."""
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
        return bool(regex.search(content))
    except Exception:
        return False


def lang_matches(path: Path, langs: list[str]) -> bool:
    """Return True if no langs specified or path suffix matches one of the langs."""
    if not langs:
        return True
    return path.suffix in langs


def find_matching_paths(root: Path, pattern: str, langs: list[str] | None = None) -> list[Path]:
    """Return list of file paths under root matching the regex pattern and optional langs."""
    regex = re.compile(pattern)
    langs = langs or []
    matches: list[Path] = []
    for path in root.rglob("*"):
        if path.is_file() and lang_matches(path, langs) and file_matches(path, regex):
            matches.append(path)
    return matches


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--pattern", required=True)
    ap.add_argument("--langs", nargs="*", default=[])
    args = ap.parse_args()

    root = Path(args.root)
    for path in find_matching_paths(root, args.pattern, args.langs):
        print(path)


if __name__ == "__main__":
    main()
