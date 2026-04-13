from __future__ import annotations

from pathlib import Path

import pytest

from core.image import load_image


@pytest.mark.parametrize(
    "image_path",
    sorted((Path(__file__).parent / "sample_data").glob("*.JPG")),
)
def test_load_real_sample_jpgs(image_path: Path) -> None:
    image = load_image(image_path)
    assert image.shape[0] > 0
    assert image.shape[1] > 0
