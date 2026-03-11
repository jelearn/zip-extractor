#!/usr/bin/env python3
"""
zip_extract.py — Extract files from a zip archive with full path preservation
and arbitrary character/pattern transformations on output paths.

Transformations are applied in the order they are specified and support:
  - Literal string replacement  (-r / --replace)
  - Regex substitution           (-s / --sub)
  - Case conversion              (--upper, --lower, --title)
  - Character mapping            (--map)

Usage examples are shown in --help.
"""

import argparse
import re
import sys
import zipfile
from pathlib import Path


# ──────────────────────────────────────────────────────────────────────────────
# ANSI colours (disabled automatically on non-TTY)
# ──────────────────────────────────────────────────────────────────────────────
USE_COLOUR = sys.stdout.isatty()

def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if USE_COLOUR else text

def cyan(t):   return _c("36",    t)
def green(t):  return _c("32",    t)
def yellow(t): return _c("33",    t)
def red(t):    return _c("31",    t)
def bold(t):   return _c("1",     t)

def info(msg):  print(cyan("→ ") + msg)
def ok(msg):    print(green("✓ ") + msg)
def warn(msg):  print(yellow("⚠ ") + msg, file=sys.stderr)
def err(msg):   print(red("✗ ERROR: ") + msg, file=sys.stderr); sys.exit(1)


# ──────────────────────────────────────────────────────────────────────────────
# Transformation pipeline
# ──────────────────────────────────────────────────────────────────────────────

class Transform:
    """Base class for a single path transformation step."""
    def apply(self, path: str) -> str:
        raise NotImplementedError

    def describe(self) -> str:
        raise NotImplementedError


class LiteralReplace(Transform):
    def __init__(self, old: str, new: str, count: int = 0):
        self.old   = old
        self.new   = new
        self.count = count   # 0 = all occurrences

    def apply(self, path: str) -> str:
        if self.count:
            return path.replace(self.old, self.new, self.count)
        return path.replace(self.old, self.new)

    def describe(self) -> str:
        n = f" (first {self.count})" if self.count else " (all)"
        return f"replace{n}: {self.old!r} → {self.new!r}"


class RegexSub(Transform):
    def __init__(self, pattern: str, repl: str, count: int = 0):
        self.pattern = re.compile(pattern)
        self.repl    = repl
        self.count   = count   # 0 = all occurrences

    def apply(self, path: str) -> str:
        return self.pattern.sub(self.repl, path, count=self.count)

    def describe(self) -> str:
        n = f" (first {self.count})" if self.count else " (all)"
        return f"regex{n}: {self.pattern.pattern!r} → {self.repl!r}"


class CaseTransform(Transform):
    def __init__(self, mode: str):
        assert mode in ("upper", "lower", "title")
        self.mode = mode

    def apply(self, path: str) -> str:
        return getattr(path, self.mode)()

    def describe(self) -> str:
        return f"case: {self.mode}"


class CharMap(Transform):
    """Replace individual characters using a mapping string like 'a=@,b=8'."""
    def __init__(self, mapping_str: str):
        self.table: dict[str, str] = {}
        for pair in mapping_str.split(","):
            pair = pair.strip()
            if "=" not in pair:
                err(f"--map: invalid pair {pair!r}. Expected format: char=char (e.g. a=@)")
            k, v = pair.split("=", 1)
            self.table[k] = v
        self._str_table = str.maketrans(self.table)

    def apply(self, path: str) -> str:
        return path.translate(self._str_table)

    def describe(self) -> str:
        pairs = ", ".join(f"{k!r}→{v!r}" for k, v in self.table.items())
        return f"charmap: {pairs}"


def build_pipeline(args) -> list[Transform]:
    """
    Reconstruct the ordered transformation pipeline from sys.argv so that
    transforms are applied in the exact order the user wrote them.
    """
    transforms: list[Transform] = []
    argv = sys.argv[1:]
    i = 0
    while i < len(argv):
        tok = argv[i]

        if tok in ("-r", "--replace"):
            old, new = argv[i + 1], argv[i + 2]
            transforms.append(LiteralReplace(old, new))
            i += 3

        elif tok in ("-r1", "--replace-first"):
            old, new = argv[i + 1], argv[i + 2]
            transforms.append(LiteralReplace(old, new, count=1))
            i += 3

        elif tok in ("-s", "--sub"):
            pattern, repl = argv[i + 1], argv[i + 2]
            transforms.append(RegexSub(pattern, repl))
            i += 3

        elif tok in ("-s1", "--sub-first"):
            pattern, repl = argv[i + 1], argv[i + 2]
            transforms.append(RegexSub(pattern, repl, count=1))
            i += 3

        elif tok == "--upper":
            transforms.append(CaseTransform("upper"))
            i += 1

        elif tok == "--lower":
            transforms.append(CaseTransform("lower"))
            i += 1

        elif tok == "--title":
            transforms.append(CaseTransform("title"))
            i += 1

        elif tok in ("-m", "--map"):
            transforms.append(CharMap(argv[i + 1]))
            i += 2

        else:
            i += 1

    return transforms


def apply_pipeline(path: str, pipeline: list[Transform]) -> str:
    for t in pipeline:
        path = t.apply(path)
    return path


# ──────────────────────────────────────────────────────────────────────────────
# Argument parsing
# ──────────────────────────────────────────────────────────────────────────────

EPILOG = """
TRANSFORMATION OPTIONS (applied in the order given on the command line)
------------------------------------------------------------------------
  -r  / --replace       OLD NEW   Replace all occurrences of OLD with NEW (literal)
  -r1 / --replace-first OLD NEW   Replace only the first occurrence (literal)
  -s  / --sub           PAT REPL  Regex substitution, all matches (Python re syntax)
  -s1 / --sub-first     PAT REPL  Regex substitution, first match only
  --upper                         Convert entire path to uppercase
  --lower                         Convert entire path to lowercase
  --title                         Convert entire path to title case
  -m  / --map           PAIRS     Map individual characters; PAIRS = "a=@,b=8, =_"

All transforms operate on the full relative path inside the zip
(e.g. "project/src/Main File.py") before the output directory is joined.

EXAMPLES
--------
  # List zip contents
  python zip_extract.py -z archive.zip -l

  # Extract everything, no transforms
  python zip_extract.py -z archive.zip -o ./out -e "project/"

  # Rename a top-level directory segment
  python zip_extract.py -z archive.zip -o ./out \\
      -e "project/src/main.py" -s "^project/" "app/"
  # → ./out/app/src/main.py

  # Replace spaces with underscores and lowercase everything
  python zip_extract.py -z archive.zip -o ./out \\
      -e "project/" -r " " "_" --lower
  # → ./out/project/src/my_file.py  (spaces → underscores, all lowercase)

  # Map individual characters
  python zip_extract.py -z archive.zip -o ./out \\
      -e "project/config.yaml" -m " =_,-=_"
  # Spaces and hyphens become underscores in the output path

  # Chain multiple transforms
  python zip_extract.py -z archive.zip -o ./out \\
      -e "project/src/" -s "^project/" "app/" -r " " "_" --lower

  # Extract multiple specific entries with different transforms each
  # (run the script once per entry group, or combine via shell loops)
"""

def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="zip_extract.py",
        description="Extract files from a zip with full path preservation and output path transforms.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EPILOG,
        add_help=True,
    )
    p.add_argument("-z", "--zip",    metavar="ZIPFILE",    required=False, help="Path to the .zip archive")
    p.add_argument("-o", "--output", metavar="OUTPUT_DIR", required=False, help="Root output directory (created if absent)")
    p.add_argument("-e", "--entry",  metavar="ENTRY",      action="append", default=[],
                   help="Path inside the zip to extract (repeatable; prefix match for directories)")
    p.add_argument("-l", "--list",   action="store_true",  help="List all entries and exit")
    p.add_argument("--dry-run",      action="store_true",  help="Show what would be extracted without writing files")

    # Transformation flags (parsed in order from sys.argv by build_pipeline)
    p.add_argument("-r",  "--replace",       nargs=2, metavar=("OLD", "NEW"),     action="append", default=[], help=argparse.SUPPRESS)
    p.add_argument("-r1", "--replace-first", nargs=2, metavar=("OLD", "NEW"),     action="append", default=[], help=argparse.SUPPRESS)
    p.add_argument("-s",  "--sub",           nargs=2, metavar=("PATTERN", "REPL"),action="append", default=[], help=argparse.SUPPRESS)
    p.add_argument("-s1", "--sub-first",     nargs=2, metavar=("PATTERN", "REPL"),action="append", default=[], help=argparse.SUPPRESS)
    p.add_argument("-m",  "--map",           metavar="PAIRS",                      action="append", default=[], help=argparse.SUPPRESS)
    p.add_argument("--upper",  action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--lower",  action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--title",  action="store_true", help=argparse.SUPPRESS)
    return p


# ──────────────────────────────────────────────────────────────────────────────
# Core logic
# ──────────────────────────────────────────────────────────────────────────────

def list_zip(zf: zipfile.ZipFile) -> None:
    print(bold(f"\nContents of: {zf.filename}\n"))
    name_w = max((len(i.filename) for i in zf.infolist()), default=40)
    header = f"  {'Path':<{name_w}}  {'Size':>10}  {'Compressed':>10}"
    print(bold(header))
    print("  " + "─" * (name_w + 24))
    for info_item in zf.infolist():
        size = f"{info_item.file_size:,}"
        comp = f"{info_item.compress_size:,}"
        print(f"  {info_item.filename:<{name_w}}  {size:>10}  {comp:>10}")
    print()


def match_entries(all_names: list[str], patterns: list[str]) -> list[str]:
    """Return zip names that match any of the given prefix patterns."""
    matched: list[str] = []
    seen: set[str] = set()
    for pat in patterns:
        pat_clean = pat.rstrip("/")
        for name in all_names:
            if name == pat_clean or name.startswith(pat_clean + "/"):
                if name not in seen:
                    matched.append(name)
                    seen.add(name)
    return matched


def extract(args, pipeline: list[Transform]) -> None:
    zip_path = Path(args.zip)
    out_root = Path(args.output)

    if not zip_path.exists():
        err(f"Zip file not found: {zip_path}")

    with zipfile.ZipFile(zip_path, "r") as zf:
        all_names = zf.namelist()

        if args.list:
            list_zip(zf)
            return

        if not args.entry:
            err("No entries specified. Use -e to select files or directories.")

        matched = match_entries(all_names, args.entry)

        if not matched:
            err("None of the specified entries were found in the archive.")

        print()
        print(bold(f"Archive : {zip_path}"))
        print(bold(f"Output  : {out_root}"))

        if pipeline:
            print(bold("Transforms:"))
            for t in pipeline:
                print(f"  {cyan('•')} {t.describe()}")
        print()

        extracted_count = 0
        skipped_count   = 0

        for zip_name in matched:
            # Skip pure-directory entries
            if zip_name.endswith("/"):
                continue

            # Apply transformation pipeline to the relative path
            out_rel  = apply_pipeline(zip_name, pipeline)
            dest     = out_root / out_rel

            if args.dry_run:
                if out_rel != zip_name:
                    print(f"  {cyan(zip_name)}")
                    print(f"  {green('→ ' + out_rel)}")
                else:
                    print(f"  {ok_str(zip_name)}")
                extracted_count += 1
                continue

            # Create all intermediate directories
            dest.parent.mkdir(parents=True, exist_ok=True)

            # Extract
            try:
                data = zf.read(zip_name)
                dest.write_bytes(data)
            except Exception as exc:
                warn(f"  Failed to extract {zip_name}: {exc}")
                skipped_count += 1
                continue

            if out_rel != zip_name:
                print(f"  {cyan(zip_name)}")
                print(f"  {green('→ ' + out_rel)}")
            else:
                print(green("✓ ") + zip_name)

            extracted_count += 1

        verb = "Would extract" if args.dry_run else "Extracted"
        print()
        print(bold(green(f"Done! ")) +
              f"{verb} {extracted_count} file(s)" +
              (f", skipped {skipped_count}" if skipped_count else "") +
              (f" → {out_root}" if not args.dry_run else " (dry run)"))


def ok_str(s: str) -> str:
    return green("✓ ") + s


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = build_arg_parser()
    args   = parser.parse_args()

    # Require -z unless --help was the only argument
    if not args.zip and not args.list:
        parser.print_help()
        sys.exit(0)

    # Build the ordered transform pipeline by re-reading sys.argv
    pipeline = build_pipeline(args)

    # List-only mode (no -o required)
    if args.list:
        if not args.zip:
            err("--list requires -z <zipfile>.")
        with zipfile.ZipFile(args.zip) as zf:
            list_zip(zf)
        return

    if not args.output:
        err("No output directory specified. Use -o <output_dir>.")

    extract(args, pipeline)


if __name__ == "__main__":
    main()
