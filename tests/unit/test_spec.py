"""Tests for NamespaceBuilder — spec loading, path building, parsing."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from acquisition_namespace import NamespaceBuilder, NamespaceLevelSpec, NamespaceSpec

# ---------------------------------------------------------------------------
# Inline spec fixtures

_SIMPLE_SPEC = {
    "version": "1.0",
    "description": "Test spec",
    "hierarchy": ["subject", "session"],
    "optional_levels": [],
    "levels": {
        "subject": {
            "template": "{subject}",
            "regex": r"(?P<subject>[\w\-]+)",
            "optional_fields": [],
        },
        "session": {
            "template": "{subject}__{datetime}__{task}",
            "regex": r"(?P<subject>[\w\-]+)__(?P<datetime>\d{8}_\d{6}(?:_\d{6})?)__(?P<task>[\w\-]+)",
            "optional_fields": [],
        },
    },
}

_V3_SPEC = {
    "version": "3.0",
    "description": "Full hierarchy with file level",
    "hierarchy": ["subject", "session", "file"],
    "optional_levels": [],
    "levels": {
        "subject": {
            "template": "{prefix}{id}_{exp}_m{mouse}",
            "regex": r"(?P<prefix>[a-zA-Z])(?P<id>\d{3})_(?P<exp>\w+)_m(?P<mouse>\d+)",
            "optional_fields": [],
        },
        "session": {
            "template": "{subject}__{date}_{time}__{modality}",
            "regex": r"(?P<subject>.+)__(?P<date>\d{8})_(?P<time>\d{6})__(?P<modality>\w+)",
            "optional_fields": [],
        },
        "file": {
            "template": "{session}.{suffix}.{extension}",
            "regex": r"(?P<session>.+)\.(?P<suffix>\w+)\.(?P<extension>\w+)",
            "optional_fields": [],
        },
    },
}

_V3_VALUES = {
    "prefix": "s",
    "id": "082",
    "exp": "tabfixed",
    "mouse": "1099615",
    "date": "20240502",
    "time": "131422",
    "modality": "recording",
    "suffix": "msw",
    "extension": "pkl",
}

DATA_DIR = Path(__file__).parent.parent / "data"


# ---------------------------------------------------------------------------
# NamespaceLevelSpec validation


def test_level_spec_invalid_regex_raises():
    with pytest.raises(ValidationError):
        NamespaceLevelSpec(template="{x}", regex="(?P<x>[")


def test_level_spec_stores_optional_fields():
    spec = NamespaceLevelSpec(
        template="{subject}__{tag}",
        regex=r"(?P<subject>.+)(?:__(?P<tag>\w+))?",
        optional_fields=["tag"],
    )
    assert "tag" in spec.optional_fields


# ---------------------------------------------------------------------------
# NamespaceSpec validation


def test_spec_missing_hierarchy_level_raises():
    with pytest.raises(ValidationError):
        NamespaceSpec(
            version="0",
            hierarchy=["a", "b"],
            levels={"a": NamespaceLevelSpec(template="{a}", regex=r"(?P<a>.+)")},
        )


def test_spec_optional_levels_stored():
    spec = NamespaceSpec(
        version="1",
        hierarchy=["a", "b"],
        optional_levels=["b"],
        levels={
            "a": NamespaceLevelSpec(template="{a}", regex=r"(?P<a>\w+)"),
            "b": NamespaceLevelSpec(
                template="{a}__{b}", regex=r"(?P<a>.+)__(?P<b>\w+)"
            ),
        },
    )
    assert spec.optional_levels == ["b"]


# ---------------------------------------------------------------------------
# NamespaceBuilder.from_dict


def test_from_dict_simple():
    b = NamespaceBuilder.from_dict(_SIMPLE_SPEC)
    assert b.hierarchy == ["subject", "session"]
    assert b.spec.version == "1.0"


def test_from_dict_v3():
    b = NamespaceBuilder.from_dict(_V3_SPEC)
    assert b.hierarchy == ["subject", "session", "file"]


# ---------------------------------------------------------------------------
# NamespaceBuilder.from_yaml / write_yaml


def test_from_yaml_write_and_reload(tmp_path):
    b = NamespaceBuilder.from_dict(_SIMPLE_SPEC)
    out = tmp_path / "ns.yaml"
    b.write_yaml(out)
    b2 = NamespaceBuilder.from_yaml(out)
    assert b2.hierarchy == b.hierarchy
    assert b2.spec.version == b.spec.version


def test_yaml_roundtrip_preserves_build(tmp_path):
    b = NamespaceBuilder.from_dict(_SIMPLE_SPEC)
    out = tmp_path / "ns.yaml"
    b.write_yaml(out)
    b2 = NamespaceBuilder.from_yaml(out)
    values = {
        "subject": "mouse_01",
        "datetime": "20260524_143022_123456",
        "task": "sequence",
    }
    assert b2.build_path("session", values) == b.build_path("session", values)


def test_write_yaml_preserves_optional_levels(tmp_path):
    spec_dict = {
        "version": "2.0",
        "description": "",
        "hierarchy": ["subject", "acquisition", "session"],
        "optional_levels": ["acquisition"],
        "levels": {
            "subject": {
                "template": "{subject}",
                "regex": r"(?P<subject>\w+)",
                "optional_fields": [],
            },
            "acquisition": {
                "template": "{subject}__{date}",
                "regex": r"(?P<subject>.+)__(?P<date>\d{8})",
                "optional_fields": [],
            },
            "session": {
                "template": "{acquisition}__{task}",
                "regex": r"(?P<acquisition>.+)__(?P<task>\w+)",
                "optional_fields": [],
            },
        },
    }
    b = NamespaceBuilder.from_dict(spec_dict)
    out = tmp_path / "ns.yaml"
    b.write_yaml(out)
    b2 = NamespaceBuilder.from_yaml(out)
    assert b2.optional_levels == ["acquisition"]


# ---------------------------------------------------------------------------
# Loading from tests/data real YAML


def test_from_yaml_v3_data_file():
    b = NamespaceBuilder.from_yaml(DATA_DIR / "namespace.v3.yaml")
    assert b.hierarchy == ["subject", "acquisition", "session", "file"]
    assert b.spec.version == "3.0"


def test_v3_data_file_no_optional_levels():
    b = NamespaceBuilder.from_yaml(DATA_DIR / "namespace.v3.yaml")
    assert b.optional_levels == []


def test_v3_data_file_has_four_levels():
    b = NamespaceBuilder.from_yaml(DATA_DIR / "namespace.v3.yaml")
    assert set(b.spec.levels.keys()) == {"subject", "acquisition", "session", "file"}


def test_v3_data_file_subject_optional_fields():
    b = NamespaceBuilder.from_yaml(DATA_DIR / "namespace.v3.yaml")
    assert "ear" in b.spec.levels["subject"].optional_fields


# ---------------------------------------------------------------------------
# build_path


def test_build_path_session():
    b = NamespaceBuilder.from_dict(_SIMPLE_SPEC)
    result = b.build_path(
        "session",
        {
            "subject": "mouse_01",
            "datetime": "20260524_143022_123456",
            "task": "sequence",
        },
    )
    assert result == "mouse_01__20260524_143022_123456__sequence"


def test_build_path_subject():
    b = NamespaceBuilder.from_dict(_V3_SPEC)
    result = b.build_path("subject", _V3_VALUES)
    assert result == "s082_tabfixed_m1099615"


def test_build_path_session_v3():
    b = NamespaceBuilder.from_dict(_V3_SPEC)
    result = b.build_path("session", _V3_VALUES)
    assert result == "s082_tabfixed_m1099615__20240502_131422__recording"


def test_build_path_file_resolves_session_automatically():
    """The file level references {session}; builder must resolve it from values."""
    b = NamespaceBuilder.from_dict(_V3_SPEC)
    result = b.build_path("file", _V3_VALUES)
    assert result == "s082_tabfixed_m1099615__20240502_131422__recording.msw.pkl"


def test_build_path_unknown_level_raises():
    b = NamespaceBuilder.from_dict(_SIMPLE_SPEC)
    with pytest.raises(ValueError, match="Unknown level"):
        b.build_path("bogus", {})


def test_build_path_missing_field_raises():
    b = NamespaceBuilder.from_dict(_SIMPLE_SPEC)
    with pytest.raises(ValueError, match="Missing value"):
        b.build_path("session", {"subject": "m01"})  # missing datetime and task


def test_build_path_idempotent():
    b = NamespaceBuilder.from_dict(_SIMPLE_SPEC)
    vals = {
        "subject": "mouse_01",
        "datetime": "20260524_143022_123456",
        "task": "sequence",
    }
    assert b.build_path("session", vals) == b.build_path("session", vals)


# ---------------------------------------------------------------------------
# generate_path


def test_generate_path_to_session():
    b = NamespaceBuilder.from_dict(_V3_SPEC)
    path = b.generate_path("session", _V3_VALUES)
    parts = path.split("/")
    assert len(parts) == 2
    assert parts[0] == "s082_tabfixed_m1099615"
    assert "20240502" in parts[1]


def test_generate_path_to_file():
    b = NamespaceBuilder.from_dict(_V3_SPEC)
    path = b.generate_path("file", _V3_VALUES)
    parts = path.split("/")
    assert len(parts) == 3
    assert parts[-1].endswith(".msw.pkl")


def test_generate_path_unknown_level_raises():
    b = NamespaceBuilder.from_dict(_SIMPLE_SPEC)
    with pytest.raises(ValueError, match="Unknown level"):
        b.generate_path("bogus", {})


def test_generate_path_to_subject_single_segment():
    b = NamespaceBuilder.from_dict(_V3_SPEC)
    path = b.generate_path("subject", _V3_VALUES)
    assert "/" not in path
    assert path == "s082_tabfixed_m1099615"


# ---------------------------------------------------------------------------
# extract_level_values


def test_extract_session_values():
    b = NamespaceBuilder.from_dict(_SIMPLE_SPEC)
    vals = b.extract_level_values(
        "session", "mouse_01__20260524_143022_123456__sequence"
    )
    assert vals["subject"] == "mouse_01"
    assert vals["datetime"] == "20260524_143022_123456"
    assert vals["task"] == "sequence"


def test_extract_legacy_datetime():
    b = NamespaceBuilder.from_dict(_SIMPLE_SPEC)
    vals = b.extract_level_values("session", "mouse_01__20210718_152153__task")
    assert vals["datetime"] == "20210718_152153"


def test_extract_unknown_level_raises():
    b = NamespaceBuilder.from_dict(_SIMPLE_SPEC)
    with pytest.raises(ValueError, match="Unknown level"):
        b.extract_level_values("bogus", "anything")


def test_extract_no_match_raises():
    b = NamespaceBuilder.from_dict(_SIMPLE_SPEC)
    with pytest.raises(ValueError, match="does not match"):
        b.extract_level_values("session", "this-does-not-match")


def test_extract_roundtrip_with_build():
    """build_path → extract_level_values must recover the original values."""
    b = NamespaceBuilder.from_dict(_SIMPLE_SPEC)
    vals = {
        "subject": "mouse_01",
        "datetime": "20260524_143022_123456",
        "task": "sequence",
    }
    name = b.build_path("session", vals)
    recovered = b.extract_level_values("session", name)
    assert recovered["subject"] == vals["subject"]
    assert recovered["datetime"] == vals["datetime"]
    assert recovered["task"] == vals["task"]


def test_extract_file_values():
    b = NamespaceBuilder.from_dict(_V3_SPEC)
    name = b.build_path("file", _V3_VALUES)
    parts = b.extract_level_values("file", name)
    assert parts["suffix"] == "msw"
    assert parts["extension"] == "pkl"


# ---------------------------------------------------------------------------
# validate_path


def test_validate_path_stop_at():
    b = NamespaceBuilder.from_dict(_V3_SPEC)
    path = (
        Path("s082_tabfixed_m1099615")
        / "s082_tabfixed_m1099615__20240502_131422__recording"
        / "s082_tabfixed_m1099615__20240502_131422__recording.msw.pkl"
    )
    result = b.validate_path(path, stop_at="session")
    assert result["date"] == "20240502"
    assert result["modality"] == "recording"


def test_validate_path_bad_stop_at_raises():
    b = NamespaceBuilder.from_dict(_SIMPLE_SPEC)
    with pytest.raises(ValueError, match="not in hierarchy"):
        b.validate_path("anything", stop_at="bogus")


def test_validate_path_full_hierarchy():
    b = NamespaceBuilder.from_dict(_V3_SPEC)
    subject = b.build_path("subject", _V3_VALUES)
    session = b.build_path("session", _V3_VALUES)
    file = b.build_path("file", _V3_VALUES)
    path = Path(subject) / session / file
    result = b.validate_path(path)
    assert result["prefix"] == "s"
    assert result["date"] == "20240502"
    assert result["suffix"] == "msw"


def test_validate_path_level_direct():
    b = NamespaceBuilder.from_dict(_SIMPLE_SPEC)
    vals = b.validate_path_level(
        "session",
        "mouse_01__20260524_143022__task",
        {},
    )
    assert vals["subject"] == "mouse_01"
    assert vals["task"] == "task"


# ---------------------------------------------------------------------------
# to_dict / from_dict round-trip


def test_to_dict_roundtrip():
    b = NamespaceBuilder.from_dict(_SIMPLE_SPEC)
    b2 = NamespaceBuilder.from_dict(b.to_dict())
    assert b2.hierarchy == b.hierarchy
    assert b2.spec.version == b.spec.version


def test_to_dict_roundtrip_v3():
    b = NamespaceBuilder.from_dict(_V3_SPEC)
    b2 = NamespaceBuilder.from_dict(b.to_dict())
    assert b2.hierarchy == b.hierarchy
    assert b.build_path("file", _V3_VALUES) == b2.build_path("file", _V3_VALUES)


# ---------------------------------------------------------------------------
# __repr__ / __str__


def test_repr_contains_hierarchy():
    b = NamespaceBuilder.from_dict(_SIMPLE_SPEC)
    r = repr(b)
    assert "hierarchy" in r


def test_str_is_valid_json():
    b = NamespaceBuilder.from_dict(_SIMPLE_SPEC)
    s = str(b)
    # str() wraps the dict in NamespaceBuilder(...); extract JSON part
    assert s.startswith("NamespaceBuilder(")
    inner = s[len("NamespaceBuilder(") : -1]
    parsed = json.loads(inner)
    assert "hierarchy" in parsed


# ---------------------------------------------------------------------------
# Optional levels


def test_optional_level_skipped_in_generate_path():
    spec = {
        "version": "1.0",
        "description": "",
        "hierarchy": ["subject", "acquisition", "session"],
        "optional_levels": ["acquisition"],
        "levels": {
            "subject": {
                "template": "{subject}",
                "regex": r"(?P<subject>[\w]+)",
                "optional_fields": [],
            },
            "acquisition": {
                "template": "{subject}__{date}",
                "regex": r"(?P<subject>.+)__(?P<date>\d{8})",
                "optional_fields": [],
            },
            "session": {
                "template": "{acquisition}__{paradigm}",
                "regex": r"(?P<acquisition>.+)__(?P<paradigm>\w+)",
                "optional_fields": [],
            },
        },
    }
    b = NamespaceBuilder.from_dict(spec)
    path_with = b.generate_path(
        "session",
        {"subject": "m01", "date": "20260101", "paradigm": "ps"},
        include_optional_levels=True,
    )
    path_without = b.generate_path(
        "session",
        {"subject": "m01", "date": "20260101", "paradigm": "ps"},
        include_optional_levels=False,
    )
    assert path_with.count("/") == 2  # subject / acquisition / session
    assert path_without.count("/") == 1  # subject / session
