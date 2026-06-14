# Examples

Acquisition Namespace is format-agnostic: the spec YAML describes whatever
hierarchy your data pipeline uses. These examples show how to implement
common conventions.

---

## MSW (Murine Shift Work)

The MSW convention: subject → session → artifact file. Sessions are identified
by `subject__datetime__task`; files carry a `.msw.` separator before the
artifact type.

```yaml
# examples/namespace_msw.yaml
version: "1.0"
description: "MSW session file namespace."
hierarchy:
  - session
  - file
levels:
  session:
    template: "{subject}__{datetime}__{task}"
    regex: "(?P<subject>[\\w\\-]+)__(?P<datetime>\\d{8}_\\d{6}(?:_\\d{6})?)__(?P<task>[\\w\\-]+)"
    optional_fields: []
  file:
    template: "{session}.msw.{artifact}"
    regex: "(?P<session>.+)\\.msw\\.(?P<artifact>.+)"
    optional_fields: []
```

```python
builder = NamespaceBuilder.from_yaml("examples/namespace_msw.yaml")

session_name = builder.build_path("session", {
    "subject": "m0042",
    "datetime": "20260524_143022",
    "task": "sequence",
})
# → "m0042__20260524_143022__sequence"

file_name = builder.build_path("file", {
    "subject": "m0042",
    "datetime": "20260524_143022",
    "task": "sequence",
    "artifact": "df.jsonl",
})
# → "m0042__20260524_143022__sequence.msw.df.jsonl"
```

---

## NeuroBlueprint

[NeuroBlueprint](https://neuroblueprint.neuroinformatics.dev/) is the SWC/NIN
standard for neuroscience data organisation. It follows BIDS-style `sub-` /
`ses-` prefixes with typed datatype folders.

```yaml
# examples/namespace_neuroblueprint.yaml
version: "1.0"
description: "NeuroBlueprint-compatible hierarchy (SWC/NIN standard)."
hierarchy:
  - subject
  - session
  - datatype
  - file
optional_levels:
  - datatype
levels:
  subject:
    template: "sub-{subject_id}"
    regex: "sub-(?P<subject_id>[A-Za-z0-9]+)"
    optional_fields: []
  session:
    template: "ses-{session_id}"
    regex: "ses-(?P<session_id>[A-Za-z0-9]+)"
    optional_fields: []
  datatype:
    template: "{datatype}"
    regex: "(?P<datatype>behav|ephys|funcimg|anat|micr)"
    optional_fields: []
  file:
    template: "sub-{subject_id}_ses-{session_id}_task-{task_name}_{suffix}.{extension}"
    regex: "sub-(?P<subject_id>[A-Za-z0-9]+)_ses-(?P<session_id>[A-Za-z0-9]+)_task-(?P<task_name>[A-Za-z0-9]+)_(?P<suffix>[A-Za-z0-9]+)\\.(?P<extension>[A-Za-z0-9]+)"
    optional_fields: []
```

```python
builder = NamespaceBuilder.from_yaml("examples/namespace_neuroblueprint.yaml")

# Full path including datatype folder
path = builder.generate_path("datatype", {
    "subject_id": "001",
    "session_id": "20260524",
    "datatype": "ephys",
})
# → "sub-001/ses-20260524/ephys"

# Skip datatype: rawdata path only
path = builder.generate_path(
    "session",
    {"subject_id": "001", "session_id": "20260524"},
)
# → "sub-001/ses-20260524"
```

---

## Four-level hierarchy with optional acquisition

For rigs with an intermediate `acquisition` grouping (e.g. multi-probe
recordings), declare it optional so legacy sessions without it still parse.

```yaml
# examples/namespace_with_optional_acquisition.yaml
version: "1.0"
description: "Four-level hierarchy; acquisition is optional."
hierarchy:
  - subject
  - session
  - acquisition
  - file
optional_levels:
  - acquisition
levels:
  subject:
    template: "{subject}"
    regex: "(?P<subject>[\\w\\-]+)"
    optional_fields: []
  session:
    template: "{subject}__{datetime}__{task}"
    regex: "(?P<subject>[\\w\\-]+)__(?P<datetime>\\d{8}_\\d{6}(?:_\\d{6})?)__(?P<task>[\\w\\-]+)"
    optional_fields: []
  acquisition:
    template: "{acquisition_name}"
    regex: "(?P<acquisition_name>[\\w\\-]+)"
    optional_fields: []
  file:
    template: "{session}.{suffix}.{extension}"
    regex: "(?P<session>.+)\\.(?P<suffix>\\w+)\\.(?P<extension>\\w+)"
    optional_fields: []
```

```python
builder = NamespaceBuilder.from_yaml("examples/namespace_with_optional_acquisition.yaml")

# Include acquisition level
path = builder.generate_path("file", {
    "subject": "m0042",
    "datetime": "20260524_143022",
    "task": "sequence",
    "acquisition_name": "probe_a",
    "suffix": "spikes",
    "extension": "npy",
})
# → "m0042/m0042__20260524_143022__sequence/probe_a/m0042__20260524_143022__sequence.spikes.npy"

# Skip acquisition level
path = builder.generate_path(
    "file",
    {...},
    include_optional_levels=False,
)
# → "m0042/m0042__20260524_143022__sequence/m0042__20260524_143022__sequence.spikes.npy"
```

---

## Implementing your own convention

Any hierarchy that can be expressed as format strings and named-group regexes
can be represented as a spec. General rules:

1. Each level's `template` and `regex` must use the same field names.
2. If a template field matches a higher hierarchy level name, the builder
   resolves it automatically: you do not need to pre-compute parent strings.
3. The `regex` must uniquely parse the output of `template`: test with
   `extract_level_values(level, build_path(level, values)) == values`.
4. Use `optional_levels` for levels that may or may not be present in
   existing data rather than removing them from the hierarchy.
