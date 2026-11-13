"""Opt-in pixel comparison against inspected Windows reference captures.

Run in a separate process per scale, as Qt reads scale before QApplication starts.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest
from PySide6.QtGui import QImage


@pytest.mark.skipif(os.environ.get("PAWZ_VISUAL_TESTS") != "1",
                    reason="Requires reference Qt/platform/fonts; set PAWZ_VISUAL_TESTS=1")
@pytest.mark.parametrize("scale", ["1", "1.25", "1.5"])
def test_visual_scenes_match_references(tmp_path, scale):
    environment = dict(os.environ, QT_SCALE_FACTOR=scale, QT_QPA_PLATFORM="offscreen")
    subprocess.run([sys.executable, str(Path(__file__).with_name("visual_scene.py")), str(tmp_path)],
                   env=environment, check=True, timeout=30)
    references = Path(__file__).parent / "visual" / "reference" / scale
    for name in ("general", "profiles-default", "profiles-custom", "profiles-contexts", "controllers", "controllers-mappings", "main"):
        expected = QImage(str(references / (name + ".png")))
        actual = QImage(str(tmp_path / (name + ".png")))
        assert not expected.isNull(), f"Missing reference for {name} at {scale}"
        assert actual == expected, f"Screenshot differs: {name} at {scale} (actual: {tmp_path})"
