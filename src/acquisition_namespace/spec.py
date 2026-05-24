"""Namespace spec: Pydantic models + YAML-backed NamespaceBuilder.

Load a spec file and build / validate hierarchical acquisition paths:

    builder = NamespaceBuilder.from_yaml("my_namespace.yaml")
    basename = builder.build_path("session", {"subject": "mouse_01", ...})
    parts    = builder.extract_level_values("session", basename)

The spec YAML defines a hierarchy of levels, each with a ``template``
(Python format-string) and a ``regex`` (named capture groups).  Higher
levels may reference lower-level names in their template; the builder
resolves them automatically.
"""

from __future__ import annotations

import json
import logging
import re
import string
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, field_validator

# ---------------------------------------------------------------------------
# Pydantic models


class NamespaceLevelSpec(BaseModel):
    template: str
    regex: str
    optional_fields: list[str] = []

    @field_validator("regex")
    @classmethod
    def _check_regex(cls, v: str) -> str:
        try:
            re.compile(v)
        except re.error as exc:
            raise ValueError(f"Invalid regex {v!r}: {exc}") from exc
        return v


class NamespaceSpec(BaseModel):
    version: str
    description: str = ""
    hierarchy: list[str]
    optional_levels: list[str] = []
    levels: dict[str, NamespaceLevelSpec]

    @field_validator("levels")
    @classmethod
    def _all_hierarchy_levels_present(cls, v: dict, info: Any) -> dict:
        if "hierarchy" in (info.data or {}):
            missing = [h for h in info.data["hierarchy"] if h not in v]
            if missing:
                raise ValueError(
                    f"Hierarchy level(s) {missing} have no entry in 'levels'"
                )
        return v


# ---------------------------------------------------------------------------
# Helper


def _template_fields(template: str) -> list[str]:
    return [t[1] for t in string.Formatter().parse(template) if t[1]]


# ---------------------------------------------------------------------------
# NamespaceBuilder


class NamespaceBuilder:
    """Build and validate hierarchical acquisition paths from a YAML spec.

    Each level in the hierarchy has a template (for construction) and a regex
    (for parsing/validation).  Higher levels may reference lower-level names
    in their template; the builder resolves them recursively.

    Typical usage::

        b = NamespaceBuilder.from_yaml("my_namespace.yaml")

        # Build a path segment for a given level
        name = b.build_path("session", {"subject": "m01", "datetime": "20260101"})

        # Build the full directory path from root to a level
        path = b.generate_path("session", values)

        # Parse an existing path back into its component values
        parts = b.validate_path(path, stop_at="session")

        # Extract values from a single level's string
        parts = b.extract_level_values("session", name)
    """

    def __init__(self, spec: NamespaceSpec) -> None:
        self.spec = spec
        self.hierarchy: list[str] = spec.hierarchy
        self.optional_levels: list[str] = spec.optional_levels
        self._compiled: dict[str, re.Pattern] = {
            name: re.compile(level.regex) for name, level in spec.levels.items()
        }

    # ------------------------------------------------------------------
    # Construction

    @classmethod
    def from_yaml(cls, config_path: str | Path) -> NamespaceBuilder:
        """Load a :class:`NamespaceSpec` from *config_path* and return a builder."""
        path = Path(config_path)
        with path.open() as f:
            data = yaml.safe_load(f)
        spec = NamespaceSpec.model_validate(data)
        logging.debug("Loaded NamespaceSpec v%s from %s", spec.version, path)
        return cls(spec)

    @classmethod
    def from_dict(cls, data: dict) -> NamespaceBuilder:
        """Build from a plain dict (e.g. after :meth:`to_dict`)."""
        return cls(NamespaceSpec.model_validate(data))

    # ------------------------------------------------------------------
    # Serialisation

    def to_dict(self) -> dict:
        return self.spec.model_dump()

    def __str__(self) -> str:
        return f"NamespaceBuilder({json.dumps(self.to_dict())})"

    def __repr__(self) -> str:
        return f"NamespaceBuilder({self.to_dict()})"

    def write_yaml(self, path: str | Path) -> None:
        """Serialise the spec back to a YAML file."""
        with Path(path).open("w") as f:
            yaml.dump(
                self.spec.model_dump(),
                f,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            )
        logging.info("NamespaceSpec written to %s", path)

    # ------------------------------------------------------------------
    # Path building

    def _build_one(self, level_name: str, values: dict, parts: dict) -> str:
        if level_name in parts:
            return parts[level_name]
        level = self.spec.levels[level_name]
        fields = _template_fields(level.template)
        for field in fields:
            if field in self.hierarchy and field not in parts and field != level_name:
                parts[field] = self._build_one(field, values, parts)
            elif field not in values and field not in parts:
                raise ValueError(
                    f"Missing value for field '{field}' in level '{level_name}'"
                )
        fmt = {k: parts.get(k, values.get(k, "")) for k in fields}
        result = level.template.format(**fmt)
        parts[level_name] = result
        return result

    def build_path(self, level: str, values: dict) -> str:
        """Return the path segment string for *level* constructed from *values*.

        Parent levels referenced in the template are resolved automatically.
        """
        if level not in self.spec.levels:
            raise ValueError(f"Unknown level: {level!r}")
        return self._build_one(level, values, {})

    def generate_path(
        self,
        level: str,
        values: dict,
        include_optional_levels: bool = True,
    ) -> str:
        """Return the full filesystem path from root up to (and including) *level*.

        Joins each hierarchy level with :func:`pathlib.Path` so the result
        uses the platform separator.
        """
        if level not in self.hierarchy:
            raise ValueError(f"Unknown level: {level!r}")
        parts: dict[str, str] = {}
        segments: list[str] = []
        for name in self.hierarchy:
            if name in self.optional_levels and not include_optional_levels:
                continue
            segments.append(self._build_one(name, values, parts))
            if name == level:
                break
        return str(Path(*segments))

    # ------------------------------------------------------------------
    # Parsing / validation

    def _match_level(
        self, level_name: str, segment: str, known_values: dict
    ) -> dict[str, str]:
        level = self.spec.levels[level_name]
        pattern = level.regex
        for k, v in known_values.items():
            if v is not None:
                pattern = pattern.replace("{" + k + "}", re.escape(str(v)))
        m = re.match(pattern, segment.strip())
        if not m:
            raise ValueError(
                f"Segment {segment!r} did not match regex for level {level_name!r}"
            )
        return m.groupdict()

    def validate_path_level(
        self, level: str, segment: str, known_values: dict
    ) -> dict[str, str]:
        """Match *segment* against the regex for *level*, return captured groups."""
        return self._match_level(level, segment, known_values)

    def validate_path(
        self, path: str | Path, stop_at: str | None = None
    ) -> dict[str, str]:
        """Walk *path* level by level and return all captured values.

        Parameters
        ----------
        path:
            Filesystem path to validate (may be absolute or relative).
        stop_at:
            Stop after matching this hierarchy level.  If ``None``, walks
            the entire hierarchy.

        Raises
        ------
        ValueError
            If any segment does not match the expected regex.
        """
        if stop_at and stop_at not in self.hierarchy:
            raise ValueError(f"stop_at level {stop_at!r} is not in hierarchy")
        max_depth = (
            self.hierarchy.index(stop_at) + 1 if stop_at else len(self.hierarchy)
        )
        segments = Path(path).parts
        result: dict[str, str] = {}
        for i, (segment, level_name) in enumerate(zip(segments, self.hierarchy)):
            if i >= max_depth:
                break
            result.update(self._match_level(level_name, segment, result))
            if level_name == stop_at:
                break
        return result

    def extract_level_values(self, level: str, name: str) -> dict[str, str]:
        """Parse *name* as a *level* segment and return template-field values.

        Unlike :meth:`validate_path` (which walks a directory path), this
        matches a single string against a single level's regex.

        Raises
        ------
        ValueError
            If *level* is not in the hierarchy, or *name* does not match.
        """
        if level not in self.hierarchy:
            raise ValueError(f"Unknown level: {level!r}")
        match = self._compiled[level].match(name.strip())
        if not match:
            raise ValueError(f"Name {name!r} does not match regex for level {level!r}")
        fields = _template_fields(self.spec.levels[level].template)
        return {f: match.groupdict().get(f, "") for f in fields}
