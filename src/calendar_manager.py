import logging
import os
import pickle
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import pytz
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from PIL import Image, ImageDraw


logger = logging.getLogger(__name__)


class CalendarManager:
    """Read-only next-event display for a 64x64 matrix."""

    SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

    def __init__(self, display_manager, config: Dict[str, Any]):
        self.display_manager = display_manager
        self.config = config
        self.calendar_config = config.get("calendar", {})
        self.enabled = self.calendar_config.get("enabled", False)
        self.update_interval = int(
            self.calendar_config.get("update_interval", 3600)
        )
        self.max_events = int(self.calendar_config.get("max_events", 3))
        self.calendars = self.calendar_config.get("calendars", ["primary"])
        self.credentials_file = self.calendar_config.get(
            "credentials_file",
            "credentials.json",
        )
        self.token_file = self.calendar_config.get("token_file", "token.pickle")
        self.timezone = self._load_timezone(config.get("timezone", "UTC"))
        self.last_update = 0.0
        self.events: List[Dict[str, Any]] = []
        self.service = None
        self.auth_status = "disabled" if not self.enabled else "unavailable"
        self.current_event_index = 0

        if self.enabled:
            self.authenticate()
            self.update(time.time())

    @staticmethod
    def _load_timezone(name: str):
        try:
            return pytz.timezone(name)
        except pytz.UnknownTimeZoneError:
            logger.warning("Unknown calendar timezone '%s'; using UTC", name)
            return pytz.utc

    def authenticate(self) -> bool:
        """Use an existing token without starting interactive OAuth."""
        self.service = None
        if not os.path.exists(self.token_file):
            self.auth_status = "token_missing"
            logger.info(
                "Calendar token is unavailable; run calendar_registration.py "
                "to authorize calendar access."
            )
            return False

        try:
            with open(self.token_file, "rb") as token_handle:
                credentials = pickle.load(token_handle)
        except Exception as exc:
            self.auth_status = "token_invalid"
            logger.warning("Calendar token could not be loaded: %s", exc)
            return False

        try:
            if not credentials.valid:
                if credentials.expired and credentials.refresh_token:
                    credentials.refresh(Request())
                    with open(self.token_file, "wb") as token_handle:
                        pickle.dump(credentials, token_handle)
                else:
                    self.auth_status = "reauth_required"
                    logger.warning(
                        "Calendar authorization requires manual renewal."
                    )
                    return False
            self.service = build(
                "calendar",
                "v3",
                credentials=credentials,
                cache_discovery=False,
            )
            self.auth_status = "ready"
            return True
        except Exception as exc:
            self.auth_status = "unavailable"
            logger.warning("Calendar authentication failed: %s", exc)
            return False

    def get_events(self) -> List[Dict[str, Any]]:
        if not self.enabled or not self.service:
            return []
        try:
            now = datetime.now(pytz.utc).isoformat()
            result = (
                self.service.events()
                .list(
                    calendarId="primary",
                    timeMin=now,
                    maxResults=max(1, self.max_events),
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
            return result.get("items", [])
        except Exception as exc:
            logger.warning("Calendar event refresh failed: %s", exc)
            return []

    def update(self, current_time: Optional[float] = None) -> bool:
        if not self.enabled:
            return False
        now = current_time if current_time is not None else time.time()
        if now - self.last_update < self.update_interval:
            return False
        if not self.service and not self.authenticate():
            self.events = []
            self.last_update = now
            return False
        self.events = self.get_events()
        self.current_event_index = 0
        self.last_update = now
        return bool(self.events)

    def has_display_content(self) -> bool:
        return bool(self.enabled and self.service and self.events)

    def _event_datetime(self, event: Dict[str, Any]) -> Optional[datetime]:
        raw = event.get("start", {}).get(
            "dateTime",
            event.get("start", {}).get("date"),
        )
        if not raw:
            return None
        try:
            if "T" not in raw:
                return self.timezone.localize(datetime.strptime(raw, "%Y-%m-%d"))
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = self.timezone.localize(parsed)
            return parsed.astimezone(self.timezone)
        except (TypeError, ValueError):
            return None

    def _format_event_date(self, event: Dict[str, Any]) -> str:
        event_time = self._event_datetime(event)
        return event_time.strftime("%a %-m/%-d") if event_time else ""

    def _format_event_time(self, event: Dict[str, Any]) -> str:
        raw = event.get("start", {}).get("dateTime")
        if not raw:
            return "ALL DAY"
        event_time = self._event_datetime(event)
        return event_time.strftime("%-I:%M%p") if event_time else ""

    def _wrap_text(
        self,
        text: str,
        max_width: int,
        max_lines: int,
    ) -> List[str]:
        font = getattr(
            self.display_manager,
            "extra_small_font",
            self.display_manager.small_font,
        )
        words = text.split()
        lines: List[str] = []
        current = ""
        while words and len(lines) < max_lines:
            word = words.pop(0)
            candidate = f"{current} {word}".strip()
            if self.display_manager.get_text_width(candidate, font) <= max_width:
                current = candidate
            elif current:
                lines.append(current)
                current = word
            else:
                current = word
                while (
                    current
                    and self.display_manager.get_text_width(
                        current + "...",
                        font,
                    )
                    > max_width
                ):
                    current = current[:-1]
                lines.append(current + "...")
                current = ""
        if current and len(lines) < max_lines:
            lines.append(current)
        if words and lines:
            last = lines[-1]
            while (
                last
                and self.display_manager.get_text_width(last + "...", font)
                > max_width
            ):
                last = last[:-1]
            lines[-1] = last + "..."
        return lines

    def _render_event(self, event: Dict[str, Any]) -> Image.Image:
        width = int(getattr(self.display_manager, "width", 64))
        height = int(getattr(self.display_manager, "height", 64))
        image = Image.new("RGB", (width, height), (0, 0, 0))
        draw = ImageDraw.Draw(image)
        font = getattr(
            self.display_manager,
            "extra_small_font",
            self.display_manager.small_font,
        )

        date_text = self._format_event_date(event).upper()
        time_text = self._format_event_time(event)
        heading = f"{date_text} {time_text}".strip()
        heading_width = self.display_manager.get_text_width(heading, font)
        draw.text(
            ((width - heading_width) // 2, 1),
            heading,
            font=font,
            fill=(80, 180, 255),
        )
        draw.line((2, 9, width - 3, 9), fill=(80, 180, 255))

        title = str(event.get("summary", "Untitled event"))
        title_lines = self._wrap_text(title, width - 4, 4)
        for index, line in enumerate(title_lines):
            draw.text(
                (2, 13 + index * 8),
                line,
                font=font,
                fill=(255, 255, 255),
            )

        location = str(event.get("location", "")).strip()
        if location:
            location_line = self._wrap_text(location, width - 4, 1)[0]
            draw.text(
                (2, 54),
                location_line,
                font=font,
                fill=(180, 180, 180),
            )
        return image

    def draw_event(self, event: Dict[str, Any], y_position: int = 2) -> bool:
        del y_position
        self.display_manager.image = self._render_event(event)
        self.display_manager.draw = ImageDraw.Draw(self.display_manager.image)
        return True

    def display(self, force_clear: bool = False) -> bool:
        if not self.has_display_content():
            return False
        if force_clear:
            self.display_manager.clear()
        self.draw_event(self.events[0])
        self.display_manager.update_display()
        return True

    def advance_event(self) -> None:
        # The 64x64 calendar intentionally shows only the next upcoming event.
        self.current_event_index = 0
