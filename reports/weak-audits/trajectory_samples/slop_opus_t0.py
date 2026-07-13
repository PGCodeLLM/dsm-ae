#!/usr/bin/env python3
import argparse
import re
from pathlib import Path


def iter_files(root, suffixes=None):
    for path in Path(root).rglob("*"):
        if path.is_file():
            if suffixes is None or path.suffix in suffixes:
                yield path


def file_matches(path, regex):
    try:
        text = path.read_text(errors="ignore")
    except OSError:
        return False
    return regex.search(text) is not None


def normalize_suffixes(langs):
    if not langs:
        return None
    return {lang if lang.startswith(".") else "." + lang for lang in langs}


def search(root, pattern, suffixes=None):
    regex = re.compile(pattern)
    for path in iter_files(root, suffixes):
        if file_matches(path, regex):
            yield path


def main(argv=None):
    parser = argparse.ArgumentParser(description="Search files for a regex pattern.")
    parser.add_argument("--root", default=".", help="Directory to search (default: .)")
    parser.add_argument("--pattern", required=True, help="Regex pattern to match.")
    parser.add_argument(
        "--langs",
        nargs="+",
        help="Only search files with these extensions (e.g. .py .js).",
    )
    args = parser.parse_args(argv)

    suffixes = normalize_suffixes(args.langs)
    for path in search(args.root, args.pattern, suffixes):
        print(path)


if __name__ == "__main__":
    main()
