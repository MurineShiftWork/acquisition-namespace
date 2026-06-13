# API Reference

## NamespaceBuilder

The main interface. Wraps a `NamespaceSpec` and provides all path operations.

### Construction

```python
NamespaceBuilder.from_yaml(config_path)   # Load from a YAML file
NamespaceBuilder.from_dict(data)          # Build from a plain dict
```

### Serialisation

```python
builder.to_dict()               # → dict (round-trips through from_dict)
builder.write_yaml(path)        # Write the spec back to a YAML file
```

### Path building

```python
builder.build_path(level, values)
```

Returns the path **segment** string for `level` constructed from `values`.
Parent levels referenced in the template are resolved automatically.

```python
builder.generate_path(level, values, include_optional_levels=True)
```

Returns the **full filesystem path** from root up to and including `level`,
joining each hierarchy level with `pathlib.Path`. Pass
`include_optional_levels=False` to skip optional levels.

### Parsing and validation

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

---

## NamespaceSpec

Pydantic v2 model holding the parsed YAML spec.

| Field | Type |
|---|---|
| `version` | `str` |
| `description` | `str` |
| `hierarchy` | `list[str]` |
| `optional_levels` | `list[str]` |
| `levels` | `dict[str, NamespaceLevelSpec]` |

---

## NamespaceLevelSpec

Pydantic v2 model for a single hierarchy level.

| Field | Type |
|---|---|
| `template` | `str` |
| `regex` | `str` |
| `optional_fields` | `list[str]` |

---

## Auto-generated reference

::: acquisition_namespace.NamespaceBuilder

::: acquisition_namespace.NamespaceSpec

::: acquisition_namespace.NamespaceLevelSpec
