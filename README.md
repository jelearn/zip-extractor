# zip-extract

Extract files from a zip archive with **full path preservation** and a chainable pipeline of output-path transformations — rename segments, substitute characters, change case, and more, all before anything is written to disk.

## Context

The primary purpose is to ensure that the UTF-8 character encodings of source file paths are respected on output, which doesn't seem to be possible with the standard `unzip` included in Mac OS 26.3.1 by default.

While there are probably better ways, including using homebrew to install a better version of `unzip`, I thought I'd play around with claude.ai to see what it could produce and what possible issues it would create.

Initially I believed that I would need to choose individual files and change specific unprocessable characters individually, but it turned out that the characters in the original zip files were good.  As a result I didn't need any of the extra path transformation pipelines, just that the zip file path with UTF-8 charactes be extracted properly.

## Installation

Clone this repository.

```bash
pip install ./zip-extract
```

Or with [pipx](https://pipx.pypa.io/) for an isolated global CLI tool:

```bash
pipx install ./zip-extract
```

## Quick Start

```bash
# List all entries in a zip
zip-extract -z archive.zip -l

# Extract a directory, preserving its full path
zip-extract -z archive.zip -o ./out -e "project/"

# Preview changes without writing (dry run)
zip-extract -z archive.zip -o ./out -e "project/" -r " " "_" --dry-run
```

## Transformation Options

Transforms are applied **in the order they appear** on the command line.

| Flag | Arguments | Effect |
|---|---|---|
| `-r` / `--replace` | `OLD NEW` | Replace **all** literal occurrences of `OLD` with `NEW` |
| `-r1` / `--replace-first` | `OLD NEW` | Replace only the **first** literal occurrence |
| `-s` / `--sub` | `PATTERN REPL` | Regex substitution, all matches (Python `re` syntax) |
| `-s1` / `--sub-first` | `PATTERN REPL` | Regex substitution, first match only |
| `--lower` | — | Convert the full path to lowercase |
| `--upper` | — | Convert the full path to uppercase |
| `--title` | — | Convert the full path to title case |
| `-m` / `--map` | `PAIRS` | Map individual characters; format: `"a=@,b=8, =_"` |

All transforms operate on the full **relative path** inside the zip (e.g. `project/src/Main File.py`) before being joined with the output directory.

## Examples

```bash
# Rename a top-level directory segment via regex
zip-extract -z archive.zip -o ./out \
    -e "project/src/main.py" -s "^project/" "app/"
# → ./out/app/src/main.py

# Replace spaces with underscores and lowercase the entire path
zip-extract -z archive.zip -o ./out \
    -e "project/" -r " " "_" --lower
# → ./out/project/src/my_file.py

# Map individual characters (spaces and hyphens → underscores)
zip-extract -z archive.zip -o ./out \
    -e "project/config.yaml" -m " =_,-=_"

# Chain multiple transforms
zip-extract -z archive.zip -o ./out \
    -e "project/src/" -s "^project/" "app/" -r " " "_" --lower

# Replace all occurrences of a version string in the path
zip-extract -z archive.zip -o ./out \
    -e "v1/data/v1/config.yaml" -g -s "v1" "v2"
```

## Using as a Library

The transformation classes are importable for use in your own scripts:

```python
from zip_extract import LiteralReplace, RegexSub, CaseTransform, apply_pipeline

pipeline = [
    RegexSub(r"^project/", "app/"),
    LiteralReplace(" ", "_"),
    CaseTransform("lower"),
]

result = apply_pipeline("project/My Source/Main.py", pipeline)
# → "app/my_source/main.py"
```

## CLI Reference

```
usage: zip-extract [-h] [-z ZIPFILE] [-o OUTPUT_DIR] [-e ENTRY] [-l] [--dry-run]
                   [-r OLD NEW] [-r1 OLD NEW] [-s PATTERN REPL] [-s1 PATTERN REPL]
                   [-m PAIRS] [--upper] [--lower] [--title]
```

## Requirements

- Python 3.9 or later
- No third-party dependencies (stdlib only)

## Development

```bash
# Clone and install in editable mode with dev extras
git clone https://github.com/jelearn/zip-extractor.git
cd zip-extract
pip install -e ".[dev]"

# Run tests
pytest

# Or with hatch
hatch run test
hatch run test-cov
```

## License

MIT — see [LICENSE](LICENSE).

## Acknowledgements

Initial code generated with assistance from [Claude](https://claude.ai) by Anthropic.
