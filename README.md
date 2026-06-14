# Acquisition Namespace

[![PyPI](https://img.shields.io/pypi/v/acquisition-namespace.svg)](https://pypi.org/project/acquisition-namespace)

YAML-driven hierarchical path namespace builder for acquisition data pipelines.

**[→ Full documentation](https://murineshiftwork.github.io/acquisition-namespace)**

Define your session directory layout once in a YAML spec; the library builds,
parses, and validates paths at every level of the hierarchy — with zero
hard-coded separators or string constants in your application code.

## Installation

```sh
pip install acquisition-namespace
```

Or with uv:

```sh
uv add acquisition-namespace
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

# Build the full directory path from root to the session level
path = builder.generate_path("session", {...})
# → "mouse_01/mouse_01__20260524_143022_123456__sequence"

# Parse an existing path back into its fields
parts = builder.extract_level_values("session", name)
# → {"subject": "mouse_01", "datetime": "...", "task": "sequence"}
```

### Spec YAML format

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

Higher-level templates may reference lower-level names (e.g. `{session}` in
the `file` template); the builder resolves them automatically.

## Development setup

```sh
git clone https://github.com/murineshiftwork/acquisition-namespace.git
cd acquisition-namespace
uv sync --group dev
uv run pre-commit install --hook-type pre-commit --hook-type commit-msg
uv run pytest
```

## Release workflow

1. Work on a `feature/` or `fix/` branch, committing with `cz commit`
2. Open a PR — CI (lint + tests + secrets scan) must pass before merge
3. Merge to main → version bump and tag are created automatically
4. Tag triggers release: GitHub release + PyPI publish

## License

See [LICENSE](LICENSE).
