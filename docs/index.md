# Acquisition Namespace

YAML-driven hierarchical path namespace builder for acquisition data pipelines.

Define your directory layout once in a YAML spec; the library builds, parses,
and validates paths at every hierarchy level — with zero hard-coded separators
or string constants in application code.

## Installation

```sh
pip install acquisition-namespace
```

## Quick start

```python
from acquisition_namespace import NamespaceBuilder

builder = NamespaceBuilder.from_yaml("my_namespace.yaml")

# Build the session basename from component values
name = builder.build_path("session", {
    "subject": "mouse_01",
    "datetime": "20260524_143022_123456",
    "task": "sequence",
})
# → "mouse_01__20260524_143022_123456__sequence"

# Build the full directory path from root to session
path = builder.generate_path("session", {
    "subject": "mouse_01",
    "datetime": "20260524_143022_123456",
    "task": "sequence",
})
# → "mouse_01/mouse_01__20260524_143022_123456__sequence"

# Parse an existing string back into its fields
parts = builder.extract_level_values("session", name)
# → {"subject": "mouse_01", "datetime": "...", "task": "sequence"}
```

## Spec YAML format

A spec file defines a hierarchy of levels. Each level has a `template` (Python
format-string for construction) and a `regex` (named-group pattern for parsing).
Higher-level templates may reference lower-level names; the builder resolves
them automatically.

```yaml
version: "1.0"
description: "My acquisition namespace."
hierarchy:
  - subject
  - session
  - file
optional_levels: []
levels:
  subject:
    template: "{subject}"
    regex: "(?P<subject>[\\w\\-]+)"
    optional_fields: []
  session:
    template: "{subject}__{datetime}__{task}"
    regex: "(?P<subject>[\\w\\-]+)__(?P<datetime>\\d{8}_\\d{6}(?:_\\d{6})?)__(?P<task>[\\w\\-]+)"
    optional_fields: []
  file:
    template: "{session}.{suffix}.{extension}"
    regex: "(?P<session>.+)\\.(?P<suffix>\\w+)\\.(?P<extension>\\w+)"
    optional_fields: []
```

### Fields

| Field | Type | Description |
|---|---|---|
| `version` | string | Spec version for your own tracking. |
| `description` | string | Human-readable description. |
| `hierarchy` | list[str] | Ordered level names from root to leaf. |
| `optional_levels` | list[str] | Levels that may be omitted in `generate_path`. |
| `levels` | dict | Per-level spec (see below). |

Each entry in `levels`:

| Field | Type | Description |
|---|---|---|
| `template` | string | Python format-string. Fields in `{}` are filled from values or parent levels. |
| `regex` | string | Named-group regex. Groups become the parsed field dict. |
| `optional_fields` | list[str] | Fields that may be absent (informational; builder does not skip them automatically). |

### Parent-level resolution

When a template references a name that is itself a hierarchy level (e.g.
`{session}` in the `file` template), the builder resolves it by building the
parent level first. This resolution is recursive and memoised within a single
`build_path` / `generate_path` call.

## API reference

### `NamespaceBuilder`

#### Construction

```python
NamespaceBuilder.from_yaml(config_path)   # Load from a YAML file
NamespaceBuilder.from_dict(data)          # Build from a plain dict
```

#### Serialisation

```python
builder.to_dict()               # → dict (round-trips through from_dict)
builder.write_yaml(path)        # Write the spec back to a YAML file
```

#### Path building

```python
builder.build_path(level, values)
```

Returns the path **segment** string for `level` constructed from `values`.
Parent levels referenced in the template are resolved automatically.

```python
builder.generate_path(level, values, include_optional_levels=True)
```

Returns the **full filesystem path** from root up to (and including) `level`.
Joins each hierarchy level with `pathlib.Path`. Pass
`include_optional_levels=False` to skip levels listed in `optional_levels`.

#### Parsing / validation

```python
builder.extract_level_values(level, name)
```

Parse a single level string and return a dict of template-field values.
Raises `ValueError` if the string does not match the level's regex.

```python
builder.validate_path(path, stop_at=None)
```

Walk a filesystem path level by level and return all captured values.
Pass `stop_at` to stop after a specific hierarchy level.

```python
builder.validate_path_level(level, segment, known_values)
```

Match a single segment against the regex for `level`. `known_values` are
substituted into the pattern before matching.

### `NamespaceSpec`

Pydantic model. Fields: `version`, `description`, `hierarchy`,
`optional_levels`, `levels` (dict of `NamespaceLevelSpec`).

### `NamespaceLevelSpec`

Pydantic model. Fields: `template`, `regex`, `optional_fields`.

## Examples

The `examples/` directory contains:

| File | Description |
|---|---|
| `namespace_simple.yaml` | Flat hierarchy: subject → session → file |
| `namespace_with_optional_acquisition.yaml` | Four-level hierarchy; acquisition is optional |
| `namespace_full.yaml` | Four-level hierarchy; all levels required |
| `namespace_msw.yaml` | MSW-specific: session → file with `.msw.` artifact separator |
| `basic_usage.py` | Runnable example covering the full API |

## Development

```sh
git clone https://github.com/larsrollik/acquisition-namespace.git
cd acquisition-namespace
pip install -e ".[dev]"
pre-commit install --hook-type pre-commit --hook-type commit-msg
pytest
```
