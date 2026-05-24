"""Tests for NamespaceBuilder — spec loading, path building, parsing."""

from __future__ import annotations

from pathlib import Path

import pytest

from acquisition_namespace import NamespaceBuilder, NamespaceLevelSpec, NamespaceSpec

# ---------------------------------------------------------------------------
# Fixtures

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


# ---------------------------------------------------------------------------
# NamespaceLevelSpec validation


def test_level_spec_invalid_regex_raises():
    with pytest.raises(Exception):
        NamespaceLevelSpec(template="{x}", regex="(?P<x>[")


# ---------------------------------------------------------------------------
# NamespaceSpec validation


def test_spec_missing_hierarchy_level_raises():
    with pytest.raises(Exception):
        NamespaceSpec(
            version="0",
            hierarchy=["a", "b"],
            levels={"a": NamespaceLevelSpec(template="{a}", regex=r"(?P<a>.+)")},
        )


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
    values = {"subject": "mouse_01", "datetime": "20260524_143022_123456", "task": "sequence"}
    assert b2.build_path("session", values) == b.build_path("session", values)


# ---------------------------------------------------------------------------
# build_path


def test_build_path_session():
    b = NamespaceBuilder.from_dict(_SIMPLE_SPEC)
    result = b.build_path("session", {
        "subject": "mouse_01",
        "datetime": "20260524_143022_123456",
        "task": "sequence",
    })
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


# ---------------------------------------------------------------------------
# extract_level_values


def test_extract_session_values():
    b = NamespaceBuilder.from_dict(_SIMPLE_SPEC)
    vals = b.extract_level_values("session", "mouse_01__20260524_143022_123456__sequence")
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


# ---------------------------------------------------------------------------
# to_dict / from_dict round-trip


def test_to_dict_roundtrip():
    b = NamespaceBuilder.from_dict(_SIMPLE_SPEC)
    b2 = NamespaceBuilder.from_dict(b.to_dict())
    assert b2.hierarchy == b.hierarchy
    assert b2.spec.version == b.spec.version


# ---------------------------------------------------------------------------
# Optional levels


def test_optional_level_skipped_in_generate_path():
    spec = {
        "version": "1.0",
        "description": "",
        "hierarchy": ["subject", "acquisition", "session"],
        "optional_levels": ["acquisition"],
        "levels": {
            "subject": {"template": "{subject}", "regex": r"(?P<subject>[\w]+)", "optional_fields": []},
            "acquisition": {"template": "{subject}__{date}", "regex": r"(?P<subject>.+)__(?P<date>\d{8})", "optional_fields": []},
            "session": {"template": "{acquisition}__{paradigm}", "regex": r"(?P<acquisition>.+)__(?P<paradigm>\w+)", "optional_fields": []},
        },
    }
    b = NamespaceBuilder.from_dict(spec)
    path_with = b.generate_path("session", {"subject": "m01", "date": "20260101", "paradigm": "ps"}, include_optional_levels=True)
    path_without = b.generate_path("session", {"subject": "m01", "date": "20260101", "paradigm": "ps"}, include_optional_levels=False)
    assert path_with.count("/") == 2   # subject / acquisition / session
    assert path_without.count("/") == 1  # subject / session
