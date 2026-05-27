# Getting Started

## Installation

```sh
pip install acquisition-namespace
```

Or with uv:

```sh
uv add acquisition-namespace
```

## First steps

Create a YAML spec file describing your session hierarchy:

```yaml
# my_namespace.yaml
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

Then load it and build paths:

```python
from acquisition_namespace import NamespaceBuilder

builder = NamespaceBuilder.from_yaml("my_namespace.yaml")

name = builder.build_path("session", {
    "subject": "mouse_01",
    "datetime": "20260524_143022_123456",
    "task": "sequence",
})
# → "mouse_01__20260524_143022_123456__sequence"

path = builder.generate_path("session", {
    "subject": "mouse_01",
    "datetime": "20260524_143022_123456",
    "task": "sequence",
})
# → "mouse_01/mouse_01__20260524_143022_123456__sequence"
```

Parse an existing path back into its fields:

```python
parts = builder.extract_level_values("session", name)
# → {"subject": "mouse_01", "datetime": "20260524_143022_123456", "task": "sequence"}
```

## Examples

The `examples/` directory contains ready-to-run scripts and YAML specs:

| File | Description |
|---|---|
| `namespace_simple.yaml` | Flat hierarchy: subject → session → file |
| `namespace_with_optional_acquisition.yaml` | Four-level hierarchy; acquisition is optional |
| `namespace_full.yaml` | Four-level hierarchy; all levels required |
| `namespace_msw.yaml` | MSW-specific: session → file with `.msw.` artifact separator |
| `basic_usage.py` | Runnable example covering the full API |

## Development setup

```sh
git clone https://github.com/murineshiftwork/acquisition-namespace.git
cd acquisition-namespace
uv sync --extra dev
uv run pre-commit install --hook-type pre-commit --hook-type commit-msg
uv run pytest
```
