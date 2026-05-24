from __future__ import annotations

import acquisition_namespace


def test_version() -> None:
    assert acquisition_namespace.__version__ is not None
    assert isinstance(acquisition_namespace.__version__, str)
