import os
import json
import logging
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import pickle
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from rgbmatrix import graphics
import pytz
from src.config_manager import ConfigManager
import time

# Configure logger for this module
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # Set to INFO to reduce noise

class CalendarManager:
    def __init__(self, display_manager, config):
        logger.info("Initializing CalendarManager")
        self.display_manager = display_manager
        self.config = config
        self.calendar_config = config.get('calendar', {})
        self.enabled = self.calendar_config.get('enabled', False)
        self.update_interval = self.calendar_config.get('update_interval', 300)
        self.max_events = self.calendar_config.get('max_events', 3)
        self.calendars = self.calendar_config.get('calendars', ['birthdays'])
        self.last_update = 0
        self.last_debug_log = 0  # Add timestamp for debug message throttling
        self.events = []
        self.service = None
        
        logger.info(f"Calendar configuration: enabled={self.enabled}, update_interval={self.update_interval}, max_events={self.max_events}, calendars={self.calendars}")
        
        # Get timezone from config
        self.config_manager = ConfigManager()
        timezone_str = self.config_manager.get_timezone()
        logger.info(f"Loading timezone from config: {timezone_str}")
        try:
            self.timezone = pytz.timezone(timezone_str)
            logger.info(f"Successfully loaded timezone: {self.timezone}")
        except pytz.UnknownTimeZoneError:
            logger.warning(f"Unknown timezone '{timezone_str}' in config, defaulting to UTC.")
            self.timezone = pytz.utc
        
        if self.enabled:
            self.authenticate()
        else:
            logger.warning("Calendar manager is disabled in configuration")
        
        # Display properties
        self.text_color = (255, 255, 255)  # White
        self.time_color = (0, 255, 0)      # Green
        self.date_color = (200, 200, 200)  # Light Grey
        
        # State management
        self.current_event_index = 0
        self.force_clear = False

    def authenticate(self):
        """Authenticate with Google Calendar API."""
        logger.info("Starting calendar authentication")
        creds = None
        token_file = self.calendar_config.get('token_file', 'token.pickle')
        
        if os.path.exists(token_file):
            logger.info(f"Loading credentials from {token_file}")
            with open(token_file, 'rb') as token:
                creds = pickle.load(token)
                
        if not creds or not creds.valid:
            logger.info("Credentials not found or invalid")
            if creds and creds.expired and creds.refresh_token:
                logger.info("Refreshing expired credentials")
                creds.refresh(Request())
            else:
                logger.info("Requesting new credentials")
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.calendar_config.get('credentials_file', 'credentials.json'),
                    ['https://www.googleapis.com/auth/calendar.readonly'])
                creds = flow.run_local_server(port=0)
                
            logger.info(f"Saving credentials to {token_file}")
            with open(token_file, 'wb') as token:
                pickle.dump(creds, token)
                
        self.service = build('calendar', 'v3', credentials=creds)
        logger.info("Calendar service built successfully")
    
    def get_events(self):
        """Fetch upcoming calendar events."""
        if not self.enabled or not self.service:
            return []
        
        try:
            now = datetime.utcnow().isoformat() + 'Z'
            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=now,
                maxResults=self.max_events,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            return events
        except Exception as e:
            logging.error(f"Error fetching calendar events: {str(e)}")
            return []
    
    def draw_event(self, event, y_start=1):
        """Draw a single calendar event on the canvas. Returns True on success, False on error."""
        try:
            # Only log event details at INFO level when first switching to calendar display
            if self.force_clear:
                logger.info(f"CalendarManager displaying event: {event.get('summary', 'No title')}")
                logger.info(f"Event details - Date: {self._format_event_date(event)}, Time: {self._format_event_time(event)}, Summary: {event.get('summary', 'No Title')}")
            else:
                logger.debug(f"Drawing event: {event.get('summary', 'No title')}")
            
            # Get event details
            summary = event.get('summary', 'No Title')
            time_str = self._format_event_time(event)
            date_str = self._format_event_date(event)
            
            # Use display manager's small font for date/time and calendar font for summary
            datetime_font = self.display_manager.small_font
            summary_font = self.display_manager.calendar_font
            logger.debug(f"Using datetime font: {datetime_font}")
            logger.debug(f"Using summary font: {summary_font}")
            available_width = self.display_manager.matrix.width - 4  # Leave 2 pixel margin on each side
            
            # Draw date and time on top line
            datetime_str = f"{date_str} {time_str}"
            self.display_manager.draw_text(datetime_str, y=2, color=self.text_color, small_font=True)
            
            # Wrap summary text for two lines using calendar font
            title_lines = self._wrap_text(summary, available_width, summary_font, max_lines=2)
            
            # Draw summary lines
            y_pos = 12  # Start position for summary (below date/time)
            for line in title_lines:
                # Use draw_text with custom font for summary
                self.display_manager.draw_text(line, y=y_pos, color=self.text_color, font=summary_font)
                y_pos += 8  # Move down for next line
                
            return True

        except Exception as e:
            logger.error(f"Error drawing calendar event: {str(e)}", exc_info=True)
            return False

    def _wrap_text(self, text, max_width, font, max_lines=2):
        """Wrap text to fit within max_width using the provided font."""
        if not text:
            return [""]
            
        lines = []
        current_line = []
        words = text.split()
        
        for word in words:
            # Try adding the word to the current line
            test_line = ' '.join(current_line + [word]) if current_line else word
            bbox = self.display_manager.draw.textbbox((0, 0), test_line, font=font)
            text_width = bbox[2] - bbox[0]
            
            if text_width <= max_width:
                # Word fits, add it to current line
                current_line.append(word)
            else:
                # Word doesn't fit, start a new line
                if current_line:
                    lines.append(' '.join(current_line))
                    current_line = [word]
                else:
                    # Single word too long, truncate it
                    truncated = word
                    while len(truncated) > 0:
                        bbox = self.display_manager.draw.textbbox((0, 0), truncated + "...", font=font)
                        if bbox[2] - bbox[0] <= max_width:
                            lines.append(truncated + "...")
                            break
                        truncated = truncated[:-1]
                    if not truncated:
                        lines.append(word[:10] + "...")
            
            # Check if we've filled all lines
            if len(lines) >= max_lines:
                break
        
        # Handle any remaining text in current_line
        if current_line and len(lines) < max_lines:
            remaining_text = ' '.join(current_line)
            if len(words) > len(current_line):  # More words remain
                # Try to fit with ellipsis
                while len(remaining_text) > 0:
                    bbox = self.display_manager.draw.textbbox((0, 0), remaining_text + "...", font=font)
                    if bbox[2] - bbox[0] <= max_width:
                        lines.append(remaining_text + "...")
                        break
                    remaining_text = remaining_text[:-1]
            else:
                lines.append(remaining_text)
        
        # Ensure we have exactly max_lines
        while len(lines) < max_lines:
            lines.append("")
            
        return lines[:max_lines]

    def update(self, current_time):
        """Update calendar events if needed."""
        if not self.enabled:
            logger.debug("Calendar manager is disabled, skipping update")
            return
        
        if current_time - self.last_update > self.update_interval:
            logger.info("Updating calendar events")
            self.events = self.get_events()
            self.last_update = current_time
            if not self.events:
                 logger.info("No upcoming calendar events found.")
            else:
                 logger.info(f"Fetched {len(self.events)} calendar events.")
            # Reset index if events change
            self.current_event_index = 0 
        else:
            # Only log debug message every 5 seconds
            if current_time - self.last_debug_log > 5:
                logger.debug("Skipping calendar update - not enough time has passed")
                self.last_debug_log = current_time

    def _format_event_date(self, event):
        """Format event date for display"""
        start = event.get('start', {}).get('dateTime', event.get('start', {}).get('date'))
        if not start:
            return ""
            
        try:
            # Handle both date and dateTime formats
            if 'T' in start:
                dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                logger.debug(f"Parsed datetime from event: {dt} (UTC)")
            else:
                dt = datetime.strptime(start, '%Y-%m-%d')
                # Make date object timezone-aware (assume UTC if no tz info)
                dt = pytz.utc.localize(dt)
                logger.debug(f"Parsed date from event: {dt} (UTC)")
            
            local_dt = dt.astimezone(self.timezone) # Use configured timezone
            logger.debug(f"Converted to local timezone: {local_dt} ({self.timezone})")
            return local_dt.strftime("%a %-m/%-d") # e.g., "Mon 4/21"
        except ValueError as e:
            logging.error(f"Could not parse date string: {start} - {e}")
            return ""

    def _format_event_time(self, event):
        """Format event time for display"""
        start = event.get('start', {}).get('dateTime', event.get('start', {}).get('date'))
        if not start or 'T' not in start: # Only show time for dateTime events
            return "All Day"
            
        try:
            dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
            logger.debug(f"Parsed time from event: {dt} (UTC)")
            local_dt = dt.astimezone(self.timezone) # Use configured timezone
            logger.debug(f"Converted to local timezone: {local_dt} ({self.timezone})")
            return local_dt.strftime("%I:%M %p")
        except ValueError as e:
            logging.error(f"Could not parse time string: {start} - {e}")
            return "Invalid Time"

    def display(self, force_clear=False):
        """Display the current calendar event on the matrix"""
        if not self.enabled:
            logger.debug("Calendar manager is disabled, skipping display")
            return
            
        # Only clear if force_clear is True (mode switch) or no events are drawn
        if force_clear:
            self.display_manager.clear()
            
        if not self.events:
            # Display "No Events" message if the list is empty
            logger.debug("No calendar events to display")
            self.display_manager.draw_text("No Events", small_font=True, color=self.text_color)
            self.display_manager.update_display()
            return

        # Get the event to display
        if self.current_event_index >= len(self.events):
            self.current_event_index = 0 # Wrap around
        event_to_display = self.events[self.current_event_index]
        
        # Set force_clear flag for logging
        self.force_clear = force_clear
        
        # Draw the event
        draw_successful = self.draw_event(event_to_display)

        if draw_successful:
            # Update the display
            self.display_manager.update_display()
            logger.debug("CalendarManager event display updated.")
        else:
            # Draw failed (error logged in draw_event), show debug message
            logger.warning("Failed to draw calendar event")
            self.display_manager.draw_text("Calendar Error", small_font=True, color=self.text_color)
            self.display_manager.update_display()

    def advance_event(self):
        """Advance to the next event. Called by DisplayManager when calendar display time is up."""
        if not self.enabled:
            logger.debug("Calendar manager is disabled, skipping event advance")
            return
        self.current_event_index += 1
        if self.current_event_index >= len(self.events):
            self.current_event_index = 0
        logger.debug(f"CalendarManager advanced to event index {self.current_event_index}") 