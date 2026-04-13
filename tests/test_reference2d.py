from __future__ import annotations

from pathlib import Path

import pytest

from core.reference2d import load_dxf, snap_to_vertex


def test_load_synthetic_reference_fixture() -> None:
    fixture = Path(__file__).parent / "sample_data" / "synthetic_reference.dxf"
    reference = load_dxf(fixture)

    assert reference.units == "mm"
    assert len(reference.layers) >= 2
    assert len(reference.segments) >= 6
    assert reference.extents_min == (0.0, 0.0)
    assert reference.extents_max == (400.0, 300.0)
    assert snap_to_vertex(reference, 1.0, 1.0, tolerance=5.0) == (0.0, 0.0)


def test_load_missing_dxf() -> None:
    with pytest.raises(FileNotFoundError):
        load_dxf(Path(__file__).parent / "sample_data" / "missing_reference.dxf")


def test_load_dwg_rejected() -> None:
    fixture = Path(__file__).parent / "sample_data" / "2026_016_Maerkplan_StGeorg_Berlin.dwg"
    with pytest.raises(ValueError, match=r"Convert.*DXF|DXF first"):
        load_dxf(fixture)
