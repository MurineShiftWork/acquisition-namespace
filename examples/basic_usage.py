"""Basic usage of acquisition-namespace.

Run from the examples/ directory:
    python basic_usage.py
"""

import tempfile
from pathlib import Path

from acquisition_namespace import NamespaceBuilder

HERE = Path(__file__).parent

# ---------------------------------------------------------------------------
# 1. Load a spec from YAML

builder = NamespaceBuilder.from_yaml(HERE / "namespace_simple.yaml")
print("Hierarchy:", builder.hierarchy)

# ---------------------------------------------------------------------------
# 2. Build path segments

values = {
    "subject_prefix": "s",
    "subject_id": "082",
    "exp_short_name": "tabfixed",
    "mouse_id": "1099615",
    "ear": "",
    "date": "20240502",
    "time": "131422",
    "modality": "recording",
    "paradigm": "sequence",
    "suffix": "data",
    "extension": "pkl",
}

subject = builder.build_path("subject", values)
print("Subject:", subject)
# → s082_tabfixed_m1099615_

session = builder.build_path("session", values)
print("Session:", session)
# → s082_tabfixed_m1099615___20240502... (subject resolved automatically)

# ---------------------------------------------------------------------------
# 3. Generate the full directory path to a level

full_path = builder.generate_path("session", values)
print("Full path:", full_path)

# ---------------------------------------------------------------------------
# 4. Parse an existing session string back into its fields

parts = builder.extract_level_values("session", session)
print("Extracted:", parts)

# ---------------------------------------------------------------------------
# 5. Optional-level hierarchy (v2)

b2 = NamespaceBuilder.from_yaml(HERE / "namespace_with_optional_acquisition.yaml")
print("\nOptional levels:", b2.optional_levels)

path_with = b2.generate_path("session", values, include_optional_levels=True)
path_without = b2.generate_path("session", values, include_optional_levels=False)
print("With acquisition:", path_with)
print("Without acquisition:", path_without)

# ---------------------------------------------------------------------------
# 6. Serialise back to YAML

with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
    out = Path(f.name)

builder.write_yaml(out)
reloaded = NamespaceBuilder.from_yaml(out)
print("\nReloaded spec version:", reloaded.spec.version)
out.unlink()

# ---------------------------------------------------------------------------
# 7. Validators: standalone field validation

msw = NamespaceBuilder.from_yaml(HERE / "namespace_msw.yaml")
print("\nValidators defined:", list(msw.spec.validators))

# Valid values pass through unchanged.
print(msw.validate_field("subject", "mouse-082"))
# → mouse-082
print(msw.validate_field("task", "tabfixed"))
# → tabfixed
print(msw.validate_field("datetime", "20240502_131422"))
# → 20240502_131422

# Invalid values raise ValueError.
try:
    msw.validate_field("subject", "mouse 082")  # space is not in [\w\-]+
except ValueError as exc:
    print("Rejected:", exc)

# NeuroBlueprint: datatype is an enum, anything else is invalid.
nb = NamespaceBuilder.from_yaml(HERE / "namespace_neuroblueprint.yaml")
print(nb.validate_field("datatype", "ephys"))
# → ephys
try:
    nb.validate_field("datatype", "imaging")  # not in the allowed set
except ValueError as exc:
    print("Rejected:", exc)
