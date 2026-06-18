"""Namespace spec: Pydantic models + YAML-backed NamespaceBuilder.

Load a spec file and build / validate hierarchical acquisition paths:

    builder = NamespaceBuilder.from_yaml("my_namespace.yaml")
    basename = builder.build_path("session", {"subject": "mouse_01", ...})
    parts    = builder.extract_level_values("session", basename)

The spec YAML defines a hierarchy of levels, each with a ``template``
(Python format-string) and a ``regex`` (named capture groups).  Higher
levels may reference lower-level names in their template; the builder
resolves them automatically.

A ``validators`` dict (optional) holds named field patterns.  Level regexes
may embed ``${name}`` tokens which are expanded to the matching validator
pattern before the regex is compiled.  This keeps field patterns in one
place and lets levels compose structured regexes from reusable fragments.

Example::

    validators:
      subject_id: "[A-Za-z]+[0-9]+"
      animal_id:  "[A-Za-z][0-9]+"
    levels:
      subject:
        template: "{subject}"
        regex: "(?P<subject>${subject_id}_${animal_id})"

Validators are leaf patterns only - they may not reference other validators.
"""

from __future__ import annotations

import copy
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


class NamespaceValidatorSpec(BaseModel):
    """A named regex fragment used as a building block inside level regexes.

    Attributes:
        pattern: Raw regex pattern string (no anchors; embedded via ``${name}``
            in level ``regex`` fields, or used standalone by
            :meth:`NamespaceBuilder.validate_field`).
        description: Optional human-readable description.
    """

    pattern: str
    description: str = ""

    @field_validator("pattern")
    @classmethod
    def _check_pattern(cls, v: str) -> str:
        try:
            re.compile(v)
        except re.error as exc:
            raise ValueError(f"Invalid pattern {v!r}: {exc}") from exc
        return v


class NamespaceLevelSpec(BaseModel):
    """Spec for one level in the acquisition namespace hierarchy.

    Attributes:
        template: Python format-string used to construct the level's path
            segment (e.g. ``"{subject}_{session_date}"``).
        regex: Named-group regular expression used to parse and validate a
            segment string.  Must be compilable by :mod:`re`.
        optional_fields: Template fields that may be absent; the builder
            will not raise if their values are missing.
    """

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
    """Full namespace specification loaded from a YAML config file.

    Attributes:
        version: Semver string identifying the spec revision.
        description: Human-readable summary of this namespace (optional).
        hierarchy: Ordered list of level names from root to leaf
            (e.g. ``["subject", "session", "recording"]``).
        optional_levels: Subset of ``hierarchy`` names that may be omitted
            when generating paths.
        levels: Mapping from level name to its :class:`NamespaceLevelSpec`.
            Every name in ``hierarchy`` must appear here.
        validators: Named field patterns used as building blocks.
            ``${name}`` tokens in level regexes are expanded to the
            corresponding pattern before compilation.
    """

    version: str
    description: str = ""
    hierarchy: list[str]
    optional_levels: list[str] = []
    levels: dict[str, NamespaceLevelSpec]
    validators: dict[str, NamespaceValidatorSpec] = {}

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
        """Initialise from a validated :class:`NamespaceSpec`."""
        self.spec = spec
        self.hierarchy: list[str] = spec.hierarchy
        self.optional_levels: list[str] = spec.optional_levels
        self._compiled: dict[str, re.Pattern] = {
            name: re.compile(level.regex) for name, level in spec.levels.items()
        }
        self._validators: dict[str, re.Pattern] = {
            name: re.compile(f"^{v.pattern}$") for name, v in spec.validators.items()
        }

    # ------------------------------------------------------------------
    # Construction

    @staticmethod
    def _expand_validator_refs(data: dict) -> dict:
        """Expand ``${name}`` tokens in level regexes using the validators dict.

        Operates on a shallow copy of *data* so the original is not mutated.
        Raises :class:`ValueError` if a ``${name}`` token references an
        unknown validator.
        """
        raw: dict[str, str] = {
            name: spec["pattern"] for name, spec in data.get("validators", {}).items()
        }
        if not raw:
            return data

        data = copy.deepcopy(data)

        def _sub(m: re.Match, level_name: str) -> str:
            name = m.group(1)
            if name not in raw:
                raise ValueError(
                    f"Level {level_name!r} regex references unknown validator"
                    f" ${{'{name}'}}. Available: {sorted(raw)}"
                )
            return raw[name]

        for level_name, level in data.get("levels", {}).items():
            if "${" in level.get("regex", ""):

                def _repl(m: re.Match[str], _ln: str = level_name) -> str:
                    return _sub(m, _ln)

                level["regex"] = re.sub(r"\$\{(\w+)\}", _repl, level["regex"])
        return data

    @classmethod
    def from_yaml(cls, config_path: str | Path) -> NamespaceBuilder:
        """Load a :class:`NamespaceSpec` from *config_path* and return a builder."""
        path = Path(config_path)
        with path.open() as f:
            data = yaml.safe_load(f)
        data = cls._expand_validator_refs(data)
        spec = NamespaceSpec.model_validate(data)
        logging.debug("Loaded NamespaceSpec v%s from %s", spec.version, path)
        return cls(spec)

    @classmethod
    def from_dict(cls, data: dict) -> NamespaceBuilder:
        """Build from a plain dict (e.g. after :meth:`to_dict`)."""
        return cls(NamespaceSpec.model_validate(cls._expand_validator_refs(data)))

    # ------------------------------------------------------------------
    # Serialisation

    def to_dict(self) -> dict[str, Any]:
        """Return the spec as a plain dict suitable for serialisation."""
        return self.spec.model_dump()

    def __str__(self) -> str:
        return f"NamespaceBuilder({json.dumps(self.to_dict())})"

    def __repr__(self) -> str:
        return f"NamespaceBuilder({self.to_dict()})"

    def write_yaml(self, path: str | Path) -> None:
        """Serialise the spec back to a YAML file."""
        data = self.spec.model_dump()
        if not data.get("validators"):
            data.pop("validators", None)
        with Path(path).open("w") as f:
            yaml.dump(
                data,
                f,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            )
        logging.info("NamespaceSpec written to %s", path)

    # ------------------------------------------------------------------
    # Path building

    def _build_one(
        self, level_name: str, values: dict[str, str], parts: dict[str, str]
    ) -> str:
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

    def build_path(self, level: str, values: dict[str, str]) -> str:
        """Return the path segment string for *level* constructed from *values*.

        Parent levels referenced in the template are resolved automatically.
        """
        if level not in self.spec.levels:
            raise ValueError(f"Unknown level: {level!r}")
        return self._build_one(level, values, {})

    def generate_path(
        self,
        level: str,
        values: dict[str, str],
        include_optional_levels: bool = True,
        level_overrides: dict[str, str] | None = None,
    ) -> str:
        """Return the full path from root up to (and including) *level*.

        Always joins with forward slashes so the result is a portable logical
        path: identical on Linux/macOS/Windows, safe to store in session files
        and use for cross-system data alignment.

        Args:
            level: Hierarchy level name to stop at (inclusive).
            values: Template field values for building each level segment.
            include_optional_levels: If ``False``, skip optional levels.
            level_overrides: Pre-built segment strings keyed by level name.
                When a level appears here its value is used verbatim instead
                of being constructed from *values*. Use this when a segment
                comes from an external system (e.g. an OE acquisition name).
        """
        if level not in self.hierarchy:
            raise ValueError(f"Unknown level: {level!r}")
        overrides = level_overrides or {}
        parts: dict[str, str] = {}
        segments: list[str] = []
        for name in self.hierarchy:
            if name in self.optional_levels and not include_optional_levels:
                continue
            if name in overrides:
                segment = overrides[name]
                parts[name] = segment
            else:
                segment = self._build_one(name, values, parts)
            segments.append(segment)
            if name == level:
                break
        return Path(*segments).as_posix()

    # ------------------------------------------------------------------
    # Parsing / validation

    def _match_level(
        self, level_name: str, segment: str, known_values: dict[str, str]
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
        self, level: str, segment: str, known_values: dict[str, str]
    ) -> dict[str, str]:
        """Match *segment* against the regex for *level* and return captured groups.

        Args:
            level: Hierarchy level name whose regex is applied.
            segment: Single path component string to match.
            known_values: Previously captured field values; used to substitute
                literal values into the regex before matching, tightening the
                match for levels whose regex contains back-references to parent
                field values.

        Returns:
            Dict of named capture groups extracted from *segment*.

        Raises:
            ValueError: If *segment* does not match the level's regex.
        """
        return self._match_level(level, segment, known_values)

    def validate_path(
        self, path: str | Path, stop_at: str | None = None
    ) -> dict[str, str]:
        """Walk *path* level by level and return all captured values.

        Args:
            path: Filesystem path to validate (absolute or relative).
            stop_at: Stop after matching this hierarchy level. If ``None``,
                walks the entire hierarchy.

        Returns:
            Dict mapping each hierarchy level name to its captured field values.

        Raises:
            ValueError: If any segment does not match the expected regex.
        """
        if stop_at and stop_at not in self.hierarchy:
            raise ValueError(f"stop_at level {stop_at!r} is not in hierarchy")
        max_depth = (
            self.hierarchy.index(stop_at) + 1 if stop_at else len(self.hierarchy)
        )
        segments = Path(path).parts
        result: dict[str, str] = {}
        for i, (segment, level_name) in enumerate(
            zip(segments, self.hierarchy, strict=False)
        ):
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

        Raises:
            ValueError: If *level* is not in the hierarchy, or *name* does not
                match the level's regex.
        """
        if level not in self.hierarchy:
            raise ValueError(f"Unknown level: {level!r}")
        match = self._compiled[level].match(name.strip())
        if not match:
            raise ValueError(f"Name {name!r} does not match regex for level {level!r}")
        fields = _template_fields(self.spec.levels[level].template)
        return {f: match.groupdict().get(f, "") for f in fields}

    def validate_field(self, name: str, value: str) -> str:
        """Validate *value* against the named validator pattern.

        Args:
            name: Key in the ``validators`` dict of the loaded spec.
            value: String to validate.

        Returns:
            *value* unchanged if it matches the pattern.

        Raises:
            ValueError: If *name* is not a known validator, or *value* does
                not fully match the pattern.
        """
        if name not in self._validators:
            raise ValueError(
                f"Unknown validator {name!r}. Available: {sorted(self._validators)}"
            )
        if not self._validators[name].fullmatch(value):
            raise ValueError(
                f"Value {value!r} does not match validator {name!r} "
                f"(pattern: {self.spec.validators[name].pattern!r})."
            )
        return value
