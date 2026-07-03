import datetime
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class FakeImage:
    def __init__(self, size):
        self.size = size
        self.width, self.height = size


class FakeDraw:
    def __init__(self, image):
        self.image = image

    def text(self, *args, **kwargs):
        pass

    def line(self, *args, **kwargs):
        pass


def install_dependency_stubs():
    if "PIL" not in sys.modules:
        pil = types.ModuleType("PIL")
        image_module = types.ModuleType("PIL.Image")
        image_module.Image = FakeImage
        image_module.new = lambda mode, size, color=None: FakeImage(size)
        draw_module = types.ModuleType("PIL.ImageDraw")
        draw_module.Draw = FakeDraw
        pil.Image = image_module
        pil.ImageDraw = draw_module
        sys.modules["PIL"] = pil
        sys.modules["PIL.Image"] = image_module
        sys.modules["PIL.ImageDraw"] = draw_module

    if "pytz" not in sys.modules:
        pytz = types.ModuleType("pytz")
        pytz.utc = datetime.timezone.utc
        pytz.UnknownTimeZoneError = ValueError
        pytz.timezone = lambda name: datetime.timezone.utc
        sys.modules["pytz"] = pytz

    google = types.ModuleType("google")
    auth = types.ModuleType("google.auth")
    transport = types.ModuleType("google.auth.transport")
    auth_requests = types.ModuleType("google.auth.transport.requests")
    auth_requests.Request = Mock
    api_client = types.ModuleType("googleapiclient")
    discovery = types.ModuleType("googleapiclient.discovery")
    discovery.build = Mock()
    sys.modules.setdefault("google", google)
    sys.modules.setdefault("google.auth", auth)
    sys.modules.setdefault("google.auth.transport", transport)
    sys.modules.setdefault("google.auth.transport.requests", auth_requests)
    sys.modules.setdefault("googleapiclient", api_client)
    sys.modules.setdefault("googleapiclient.discovery", discovery)


install_dependency_stubs()
from src import calendar_manager


class FakeDisplay:
    width = 64
    height = 64
    extra_small_font = object()
    small_font = object()

    @staticmethod
    def get_text_width(text, font):
        del font
        return len(text) * 4

    def clear(self):
        pass

    def update_display(self):
        pass


class CalendarManagerTests(unittest.TestCase):
    def make_manager(self, enabled=False):
        return calendar_manager.CalendarManager(
            FakeDisplay(),
            {
                "timezone": "UTC",
                "calendar": {
                    "enabled": enabled,
                    "credentials_file": "credentials.json",
                    "token_file": "token.pickle",
                    "update_interval": 3600,
                    "max_events": 3,
                },
            },
        )

    def test_missing_token_does_not_start_interactive_oauth(self):
        with patch.object(calendar_manager.os.path, "exists", return_value=False):
            manager = self.make_manager(enabled=True)

        self.assertEqual(manager.auth_status, "token_missing")
        self.assertIsNone(manager.service)
        self.assertFalse(manager.has_display_content())

    def test_startup_defers_calendar_authentication_and_network(self):
        with (
            patch.object(calendar_manager.os.path, "exists", return_value=True),
            patch.object(
                calendar_manager.CalendarManager,
                "authenticate",
                return_value=True,
            ) as authenticate,
        ):
            manager = self.make_manager(enabled=True)

        authenticate.assert_not_called()
        self.assertIsNone(manager.service)
        self.assertFalse(manager.has_display_content())

    def test_renders_only_next_event_as_64_square(self):
        manager = self.make_manager()
        manager.enabled = True
        manager.service = Mock()
        manager.events = [
            {
                "summary": "Project planning session",
                "location": "Conference room",
                "start": {"dateTime": "2026-06-10T09:30:00+00:00"},
            },
            {
                "summary": "Later event",
                "start": {"dateTime": "2026-06-11T10:00:00+00:00"},
            },
        ]

        image = manager._render_event(manager.events[0])

        self.assertEqual(image.size, (64, 64))
        self.assertTrue(manager.has_display_content())


if __name__ == "__main__":
    unittest.main()
