"""search CLI — finds files under root containing regex pattern."""
import argparse
import re
from pathlib import Path


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--pattern", required=True)
    ap.add_argument("--langs", nargs="*", default=[])
    return ap.parse_args()


def compile_regex(pattern: str) -> re.Pattern | None:
    try:
        return re.compile(pattern)
    except re.error:
        return None


def normalize_langs(langs: list[str]) -> list[str]:
    return [lang if lang.startswith(".") else f".{lang}" for lang in langs]


def extension_matches(path: Path, langs: list[str]) -> bool:
    if not langs:
        return True
    norm_langs = normalize_langs(langs)
    return path.suffix in norm_langs


def file_matches(path: Path, pattern: re.Pattern, langs: list[str]) -> bool:
    if not path.is_file():
        return False
    if not extension_matches(path, langs):
        return False
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if pattern.search(line):
                    return True
        return False
    except Exception:
        return False


def find_matches(root: str, pattern: re.Pattern, langs: list[str]) -> list[Path]:
    root_path = Path(root)
    if not root_path.exists():
        return []
    matches: list[Path] = []
    for p in root_path.rglob("*"):
        if file_matches(p, pattern, langs):
            matches.append(p)
    return matches


def main() -> None:
    args = parse_args()
    regex = compile_regex(args.pattern)
    if regex is None:
        print("Invalid regex pattern", file=__import__("sys").stderr)
        return
    for match in find_matches(args.root, regex, args.langs):
        print(match)


if __name__ == "__main__":
    main()
