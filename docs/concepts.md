# Concepts

## Hierarchy and levels

A namespace spec defines an ordered list of hierarchy levels from root to leaf.
Each level has a `template` (Python format-string for construction) and a
`regex` (named-group pattern for parsing). The library resolves each level
independently so paths can be built or parsed at any depth.

```
subject/
└── subject__datetime__task/        ← session level
    └── subject__datetime__task.df.jsonl   ← file level
```

## Templates and regex

A `template` is a Python format-string. Fields in `{}` are filled from the
values dict passed to `build_path`. If a field name matches a higher-level
hierarchy name (e.g. `{session}` in the `file` template), the builder resolves
it recursively: you do not need to pre-compute parent level strings.

A `regex` is a named-group Python regex. Group names become the keys of the
dict returned by `extract_level_values`. The same field names should appear in
both the template and the regex so that `build_path` → `extract_level_values`
round-trips cleanly.

## Optional levels

Levels listed in `optional_levels` are skipped during `generate_path` when
`include_optional_levels=False`. This is useful for rigs that omit an
intermediate level (e.g. no `acquisition` folder in simple setups).

## Spec YAML format

| Field | Type | Description |
|---|---|---|
| `version` | string | Spec version string for your own tracking. |
| `description` | string | Human-readable description. |
| `hierarchy` | list[str] | Ordered level names from root to leaf. |
| `optional_levels` | list[str] | Levels that may be omitted in `generate_path`. |
| `levels` | dict | Per-level spec (see below). |

Each entry in `levels`:

| Field | Type | Description |
|---|---|---|
| `template` | string | Python format-string. Fields in `{}` are filled from values or resolved parent levels. |
| `regex` | string | Named-group regex. Groups become the parsed field dict. |
| `optional_fields` | list[str] | Fields that may be absent (informational). |

## Parent-level resolution

When a template references a name that is itself a hierarchy level, the builder
constructs that level first and substitutes its result as a string. Resolution
is recursive and memoised within a single `build_path` / `generate_path` call.

Example: `file` template `{session}.{suffix}.{extension}`:

1. Builder sees `{session}` is a hierarchy level name.
2. It calls `build_path("session", values)` to get the session string.
3. That result is substituted into the file template.
