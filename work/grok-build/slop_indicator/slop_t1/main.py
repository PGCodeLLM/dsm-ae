"""search CLI — finds files under root whose content matches --pattern (regex)."""

import argparse
import re
from pathlib import Path


def matches_content(path: Path, regex: re.Pattern[str]) -> bool:
    """Return True if file content matches regex."""
    if not path.is_file():
        return False
    try:
        return bool(regex.search(path.read_text(encoding="utf-8", errors="ignore")))
    except Exception:
        return False


def matches_lang(path: Path, langs: list[str] | None) -> bool:
    """Return True if path's suffix matches one of the langs (or no filter given)."""
    if not langs:
        return True
    return path.suffix in langs


def find_matches(root: Path, pattern: str, langs: list[str] | None = None) -> list[Path]:
    """Return list of matching file paths under root, optionally filtered by langs."""
    regex = re.compile(pattern)
    return [
        p for p in root.rglob("*")
        if matches_lang(p, langs) and matches_content(p, regex)
    ]


def print_matches(matches: list[Path]) -> None:
    """Print each matching path."""
    for m in matches:
        print(m)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--pattern", required=True)
    ap.add_argument("--langs", nargs="*", default=None)
    args = ap.parse_args()

    root = Path(args.root).resolve()
    matches = find_matches(root, args.pattern, args.langs)
    print_matches(matches)


if __name__ == "__main__":
    main()
