"""Exercise preview PNGs with real images and fake matrix hardware."""
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
with patch.dict(sys.modules, {
    "rgbmatrix": types.SimpleNamespace(RGBMatrix=Mock(), RGBMatrixOptions=Mock()),
    "freetype": types.ModuleType("freetype"),
}):
    import src.display_manager as display_module
    from src.display_manager import DisplayManager


class DisplayPreviewTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "preview.png"
        self.manager = object.__new__(DisplayManager)
        self.manager._snapshot_path = str(self.path)
        self.manager._snapshot_min_interval_sec = 0.2
        self.manager._last_snapshot_ts = 0.0
        self.manager._snapshot_force_next = False
        self.manager.matrix = Mock(width=64, height=64)
        self.manager.offscreen_canvas = Mock()
        self.manager.current_canvas = Mock()
        self.manager.image = Image.new("RGB", (64, 64), "red")
        self.manager.draw = ImageDraw.Draw(self.manager.image)
        self.now = 1000.0
        timer = patch.object(display_module.time, "time", side_effect=lambda: self.now)
        timer.start()
        self.addCleanup(timer.stop)
        sleeper = patch.object(display_module.time, "sleep")
        sleeper.start()
        self.addCleanup(sleeper.stop)

    def preview_pixel(self):
        with Image.open(self.path) as image:
            self.assertEqual(image.size, (64, 64))
            return image.getpixel((0, 0))

    def test_first_completed_frame_after_clear_is_captured(self):
        self.manager.clear()
        self.manager.image = Image.new("RGB", (64, 64), "green")
        self.manager.update_display()
        self.assertEqual(self.preview_pixel(), (0, 128, 0))

    def test_transient_clear_does_not_replace_existing_preview(self):
        self.manager.update_display()
        self.now += 1
        self.manager.clear()
        self.assertEqual(self.preview_pixel(), (255, 0, 0))
        # Both hardware buffers still receive the original clearing sequence.
        self.assertEqual(self.manager.matrix.SwapOnVSync.call_count, 3)
        self.manager.matrix.Clear.assert_called_once()

    def test_static_screen_transition_within_throttle_captures_completed_frame(self):
        self.manager.update_display()
        self.now += 0.01
        self.manager.clear()
        self.manager.image = Image.new("RGB", (64, 64), "blue")
        self.manager.update_display()
        self.assertEqual(self.preview_pixel(), (0, 0, 255))

    def test_animated_updates_remain_throttled_after_transition(self):
        self.manager.clear()
        self.manager.image = Image.new("RGB", (64, 64), "green")
        self.manager.update_display()
        self.now += 0.05
        self.manager.image = Image.new("RGB", (64, 64), "blue")
        self.manager.update_display()
        self.assertEqual(self.preview_pixel(), (0, 128, 0))
        self.now += 0.2
        self.manager.update_display()
        self.assertEqual(self.preview_pixel(), (0, 0, 255))

    def test_intentional_shutdown_publishes_black_immediately(self):
        self.manager.update_display()
        self.now += 0.01
        self.manager.clear(publish_preview=True)
        self.assertEqual(self.preview_pixel(), (0, 0, 0))

    def test_fallback_captures_completed_frame_after_clear(self):
        self.manager.matrix = None
        self.manager.update_display()
        self.now += 0.01
        self.manager.clear()
        self.manager.image = Image.new("RGB", (64, 64), "blue")
        self.manager.update_display()
        self.assertEqual(self.preview_pixel(), (0, 0, 255))

    def test_failed_capture_retries_without_losing_transition(self):
        self.manager.clear()
        self.manager.image = Image.new("RGB", (64, 64), "blue")
        with patch.object(self.manager.image, "save", side_effect=OSError("unavailable")):
            self.manager.update_display()
        self.assertFalse(self.path.exists())
        self.manager.update_display()
        self.assertEqual(self.preview_pixel(), (0, 0, 255))


if __name__ == "__main__":
    unittest.main()
