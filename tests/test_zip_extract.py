"""
Tests for zip_extract — transformation pipeline and entry matching.
Run with: pytest  (or: hatch run test)
"""

import io
import zipfile
from pathlib import Path

import pytest

# Import from the installed package (or editable install)
from zip_extract import (
    LiteralReplace,
    RegexSub,
    CaseTransform,
    CharMap,
    apply_pipeline,
    match_entries,
)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def make_zip(entries: dict[str, bytes]) -> Path:
    """Write an in-memory zip to a tmp file and return its path."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    buf.seek(0)
    return buf


# ──────────────────────────────────────────────────────────────────────────────
# LiteralReplace
# ──────────────────────────────────────────────────────────────────────────────

class TestLiteralReplace:
    def test_replaces_all(self):
        t = LiteralReplace("a", "X")
        assert t.apply("banana") == "bXnXnX"

    def test_replaces_first_only(self):
        t = LiteralReplace("a", "X", count=1)
        assert t.apply("banana") == "bXnana"

    def test_no_match(self):
        t = LiteralReplace("z", "X")
        assert t.apply("banana") == "banana"

    def test_describe(self):
        assert "replace" in LiteralReplace("a", "b").describe()
        assert "first 1" in LiteralReplace("a", "b", count=1).describe()


# ──────────────────────────────────────────────────────────────────────────────
# RegexSub
# ──────────────────────────────────────────────────────────────────────────────

class TestRegexSub:
    def test_basic_substitution(self):
        t = RegexSub(r"^project/", "app/")
        assert t.apply("project/src/main.py") == "app/src/main.py"

    def test_all_matches(self):
        t = RegexSub(r"v\d+", "vX")
        assert t.apply("v1/data/v1/config.yaml") == "vX/data/vX/config.yaml"

    def test_first_match_only(self):
        t = RegexSub(r"v\d+", "vX", count=1)
        assert t.apply("v1/data/v1/config.yaml") == "vX/data/v1/config.yaml"

    def test_no_match(self):
        t = RegexSub(r"^foo/", "bar/")
        assert t.apply("project/main.py") == "project/main.py"

    def test_describe(self):
        assert "regex" in RegexSub(r"^a/", "b/").describe()


# ──────────────────────────────────────────────────────────────────────────────
# CaseTransform
# ──────────────────────────────────────────────────────────────────────────────

class TestCaseTransform:
    def test_lower(self):
        assert CaseTransform("lower").apply("Project/SRC/Main.PY") == "project/src/main.py"

    def test_upper(self):
        assert CaseTransform("upper").apply("project/src/main.py") == "PROJECT/SRC/MAIN.PY"

    def test_title(self):
        assert CaseTransform("title").apply("project/src/main.py") == "Project/Src/Main.Py"

    def test_describe(self):
        assert "lower" in CaseTransform("lower").describe()


# ──────────────────────────────────────────────────────────────────────────────
# CharMap
# ──────────────────────────────────────────────────────────────────────────────

class TestCharMap:
    def test_single_mapping(self):
        t = CharMap(" =_")
        assert t.apply("my file.py") == "my_file.py"

    def test_multiple_mappings(self):
        t = CharMap(" =_,-=_")
        assert t.apply("my-file name.py") == "my_file_name.py"

    def test_no_match(self):
        t = CharMap("z=Z")
        assert t.apply("hello") == "hello"

    def test_describe(self):
        assert "charmap" in CharMap("a=b").describe()


# ──────────────────────────────────────────────────────────────────────────────
# apply_pipeline
# ──────────────────────────────────────────────────────────────────────────────

class TestApplyPipeline:
    def test_empty_pipeline(self):
        assert apply_pipeline("project/src/main.py", []) == "project/src/main.py"

    def test_single_transform(self):
        pipeline = [LiteralReplace(" ", "_")]
        assert apply_pipeline("my file.py", pipeline) == "my_file.py"

    def test_chained_transforms(self):
        pipeline = [
            RegexSub(r"^project/", "app/"),
            LiteralReplace(" ", "_"),
            CaseTransform("lower"),
        ]
        result = apply_pipeline("project/My Source/Main.PY", pipeline)
        assert result == "app/my_source/main.py"

    def test_order_matters(self):
        # lower first then replace underscore → different from replace then lower
        p1 = [CaseTransform("lower"), LiteralReplace("src", "SOURCE")]
        p2 = [LiteralReplace("SRC", "SOURCE"), CaseTransform("lower")]

        path = "project/SRC/Main.py"
        assert apply_pipeline(path, p1) == "project/SOURCE/main.py"
        # p2: "SRC" won't match lowercase "src", so no replacement
        assert apply_pipeline(path, p2) == "project/source/main.py"


# ──────────────────────────────────────────────────────────────────────────────
# match_entries
# ──────────────────────────────────────────────────────────────────────────────

class TestMatchEntries:
    ALL = [
        "project/src/main.py",
        "project/src/utils.py",
        "project/tests/test_main.py",
        "project/README.md",
        "other/file.txt",
    ]

    def test_exact_file(self):
        result = match_entries(self.ALL, ["project/README.md"])
        assert result == ["project/README.md"]

    def test_directory_prefix(self):
        result = match_entries(self.ALL, ["project/src/"])
        assert "project/src/main.py" in result
        assert "project/src/utils.py" in result
        assert "project/README.md" not in result

    def test_top_level_directory(self):
        result = match_entries(self.ALL, ["project/"])
        assert len(result) == 4
        assert "other/file.txt" not in result

    def test_multiple_patterns(self):
        result = match_entries(self.ALL, ["project/README.md", "other/"])
        assert "project/README.md" in result
        assert "other/file.txt" in result

    def test_no_duplicates(self):
        result = match_entries(self.ALL, ["project/src/", "project/src/main.py"])
        assert result.count("project/src/main.py") == 1

    def test_no_match(self):
        result = match_entries(self.ALL, ["nonexistent/"])
        assert result == []
