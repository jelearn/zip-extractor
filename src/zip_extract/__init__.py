"""
zip_extract — Extract files from a zip archive with full path preservation
and arbitrary character/pattern transformations on output paths.
"""

__version__ = "0.0.1"
__author__  = "Jason"
__email__   = "jason.e.learning@gmail.com"

from zip_extract.cli import (
    main,
    Transform,
    LiteralReplace,
    RegexSub,
    CaseTransform,
    CharMap,
    apply_pipeline,
    build_pipeline,
    match_entries,
)

__all__ = [
    "main",
    "Transform",
    "LiteralReplace",
    "RegexSub",
    "CaseTransform",
    "CharMap",
    "apply_pipeline",
    "build_pipeline",
    "match_entries",
]
