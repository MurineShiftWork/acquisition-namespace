# Acquisition Namespace

[![PyPI](https://img.shields.io/pypi/v/acquisition-namespace.svg)](https://pypi.org/project/acquisition-namespace)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

YAML-driven hierarchical path namespace builder for acquisition data pipelines.

Define your session directory layout once in a YAML spec. The library builds,
parses, and validates paths at every level of the hierarchy — with zero
hard-coded separators or string constants in your application code.

## Key features

- **Declarative**: path logic lives in a YAML file, not scattered across Python
- **Bidirectional**: build a path from values; parse any path back to its fields
- **Flexible hierarchy**: 2–N levels; optional levels for simpler rigs or legacy data
- **Parent-level resolution**: templates may reference lower-level names automatically
- **Standards-compatible**: implement NeuroBlueprint, BIDS, or any institutional convention
- **Validated**: Pydantic v2 models check the spec at load time

## Quick start

```python
from acquisition_namespace import NamespaceBuilder

builder = NamespaceBuilder.from_yaml("my_namespace.yaml")

# Build a session path from field values
path = builder.generate_path("session", {
    "subject": "mouse_01",
    "datetime": "20260524_143022",
    "task": "sequence",
})
# → "mouse_01/mouse_01__20260524_143022__sequence"

# Parse an existing path back into its fields
parts = builder.extract_level_values("session", "mouse_01__20260524_143022__sequence")
# → {"subject": "mouse_01", "datetime": "20260524_143022", "task": "sequence"}
```

→ [Getting Started](getting_started.md) for installation and a full walkthrough.

→ [Examples](examples.md) for ready-made specs including NeuroBlueprint and BIDS-like layouts.

→ [API Reference](api.md) for the complete method list.
