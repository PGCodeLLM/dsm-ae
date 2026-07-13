"""Print files below a root directory whose paths match a regular expression."""

import argparse
import re
from pathlib import Path
from typing import Iterator, Optional, Pattern, Sequence


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Recursively list files with paths matching a regular expression."
    )
    parser.add_argument("root", type=Path, help="directory to search")
    parser.add_argument("--pattern", required=True, help="regular expression to match")
    parser.add_argument(
        "--langs",
        nargs="+",
        metavar="EXT",
        help="optional file extensions to include (for example: .py .js)",
    )
    return parser.parse_args()


def iter_files(root: Path) -> Iterator[Path]:
    """Yield regular files contained in *root*."""
    if root.is_file():
        yield root
        return
    yield from (path for path in root.rglob("*") if path.is_file())


def has_allowed_extension(path: Path, langs: Optional[Sequence[str]]) -> bool:
    """Return whether *path* is allowed by the optional extension filter."""
    return langs is None or path.suffix in langs


def matching_files(
    root: Path, pattern: Pattern[str], langs: Optional[Sequence[str]] = None
) -> Iterator[Path]:
    """Yield matching files, optionally limited to extensions in *langs*."""
    for path in iter_files(root):
        if not has_allowed_extension(path, langs):
            continue
        display_path = path if root.is_file() else path.relative_to(root)
        if pattern.search(str(display_path)):
            yield display_path


def main() -> None:
    """Run the file-path search CLI."""
    args = parse_args()
    try:
        pattern = re.compile(args.pattern)
    except re.error as error:
        raise SystemExit(f"invalid regular expression: {error}") from error

    if not args.root.exists():
        raise SystemExit(f"root does not exist: {args.root}")

    for path in matching_files(args.root, pattern, args.langs):
        print(path)


if __name__ == "__main__":
    main()
