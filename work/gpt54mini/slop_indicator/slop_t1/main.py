"""search CLI seed — agent extends this."""
import argparse
from pathlib import Path
from typing import Iterable, Iterator


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--pattern", required=True)
    ap.add_argument(
        "--langs",
        nargs="*",
        default=None,
        help="Optional file extensions to include, e.g. .py .js",
    )
    return ap.parse_args()


def normalize_langs(langs: list[str] | None) -> set[str] | None:
    if not langs:
        return None
    normalized: set[str] = set()
    for lang in langs:
        ext = lang.strip()
        if not ext:
            continue
        if not ext.startswith("."):
            ext = f".{ext}"
        normalized.add(ext.lower())
    return normalized or None


def iter_files(root: Path) -> Iterator[Path]:
    for path in root.rglob("*"):
        if path.is_file():
            yield path


def file_allowed(path: Path, langs: set[str] | None) -> bool:
    if langs is None:
        return True
    return path.suffix.lower() in langs


def search_matches(root: Path, pattern: str, langs: set[str] | None) -> Iterable[Path]:
    for path in iter_files(root):
        if not file_allowed(path, langs):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        except OSError:
            continue
        if pattern in text:
            yield path


def main() -> None:
    args = parse_args()
    root = Path(args.root)
    langs = normalize_langs(args.langs)

    for path in search_matches(root, args.pattern, langs):
        print(path)


if __name__ == "__main__":
    main()
