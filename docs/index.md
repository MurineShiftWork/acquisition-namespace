# Acquisition Namespace

YAML-driven hierarchical path namespace builder for acquisition data pipelines.

## Installation

```sh
pip install acquisition-namespace
```

## Usage

See [README](https://github.com/larsrollik/acquisition-namespace#readme) for examples.

## Development

```sh
git clone https://github.com/larsrollik/acquisition-namespace.git
cd acquisition-namespace
uv sync --group dev
uv run pre-commit install --hook-type pre-commit --hook-type commit-msg
uv run pytest
```
