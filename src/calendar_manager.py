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
logger.setLevel(logging.DEBUG)  # Set to DEBUG to see all messages

class CalendarManager:
    def __init__(self, matrix, canvas, config):
        logger.info("Initializing CalendarManager")
        self.matrix = matrix
        self.canvas = canvas
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
        
        # Get display manager instance
        from src.display_manager import DisplayManager
        self.display_manager = DisplayManager._instance
        
        # Get timezone from config
        self.config_manager = ConfigManager()
        timezone_str = self.config_manager.get_timezone()
        try:
            self.timezone = pytz.timezone(timezone_str)
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
            # Only log event details at INFO level when first drawing
            if self.current_event_index == 0:
                logger.info(f"Drawing event: {event.get('summary', 'No title')}")
                logger.info(f"Event details - Date: {self._format_event_date(event)}, Time: {self._format_event_time(event)}, Summary: {event.get('summary', 'No Title')}")
            else:
                logger.debug(f"Drawing event: {event.get('summary', 'No title')}")
            
            # Get event details
            summary = event.get('summary', 'No Title')
            time_str = self._format_event_time(event)
            date_str = self._format_event_date(event)
            
            # Use display manager's font for wrapping
            font = self.display_manager.small_font
            available_width = self.display_manager.matrix.width - 4  # Leave 2 pixel margin on each side
            
            # Wrap title text
            title_lines = self._wrap_text(summary, available_width, font)
            logger.debug(f"Wrapped title into {len(title_lines)} lines: {title_lines}")

            # Calculate total height needed
            date_height = 8 # Approximate height for date string
            time_height = 8 # Approximate height for time string
            title_height = len(title_lines) * 8 # Approximate height for title lines
            # Height = date + time + title + spacing between each
            total_height = date_height + time_height + title_height + ( (1 + len(title_lines)) * 2 ) 
            
            # Calculate starting y position to center vertically
            y_pos = (self.display_manager.matrix.height - total_height) // 2
            y_pos = max(1, y_pos) # Ensure it doesn't start above the top edge
            logger.debug(f"Starting y position: {y_pos}, Total height: {total_height}")

            # Draw date in grey
            logger.debug(f"Drawing date at y={y_pos}: {date_str}")
            self.display_manager.draw_text(date_str, y=y_pos, color=self.date_color, small_font=True)
            y_pos += date_height + 2 # Move down for the time

            # Draw time in green
            logger.debug(f"Drawing time at y={y_pos}: {time_str}")
            self.display_manager.draw_text(time_str, y=y_pos, color=self.time_color, small_font=True)
            y_pos += time_height + 2 # Move down for the title
            
            # Draw title lines
            for i, line in enumerate(title_lines):
                logger.debug(f"Drawing title line {i+1} at y={y_pos}: {line}")
                if y_pos >= self.display_manager.matrix.height - 8: # Stop if we run out of space
                    logger.debug("Stopping title drawing - reached bottom of display")
                    break
                self.display_manager.draw_text(line, y=y_pos, color=self.text_color, small_font=True)
                y_pos += 8 + 2 # Move down for the next line, add 2px spacing
            return True # Return True on successful drawing

        except Exception as e:
            logger.error(f"Error drawing calendar event: {str(e)}", exc_info=True)
            return False # Return False on error

    def _wrap_text(self, text, max_width, font):
        """Wrap text to fit within max_width using the provided font."""
        if not text:
            return [""]
            
        lines = []
        words = text.split()
        current_line = []

        for word in words:
            test_line = ' '.join(current_line + [word])
            # Use textlength for accurate width calculation
            text_width = self.display_manager.draw.textlength(test_line, font=font)
            
            if text_width <= max_width:
                current_line.append(word)
            else:
                # If the word itself is too long, add it on its own line (or handle differently if needed)
                if not current_line:
                    lines.append(word) 
                else:
                    lines.append(' '.join(current_line))
                current_line = [word]
                # Recheck if the new line with just this word is too long
                if self.display_manager.draw.textlength(word, font=font) > max_width:
                     # Handle very long words if necessary (e.g., truncate)
                     pass 
        
        if current_line:
            lines.append(' '.join(current_line))
            
        return lines

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
            else:
                dt = datetime.strptime(start, '%Y-%m-%d')
                # Make date object timezone-aware (assume UTC if no tz info)
                dt = pytz.utc.localize(dt)
            
            local_dt = dt.astimezone(self.timezone) # Use configured timezone
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
            local_dt = dt.astimezone(self.timezone) # Use configured timezone
            return local_dt.strftime("%I:%M %p")
        except ValueError as e:
            logging.error(f"Could not parse time string: {start} - {e}")
            return "Invalid Time"

    def display(self, force_clear=False):
        """Display the current calendar event on the matrix"""
        if not self.enabled:
            logger.debug("Calendar manager is disabled, skipping display")
            return
            
        if not self.events:
            # Display "No Events" message if the list is empty
            logger.debug("No calendar events to display")
            if force_clear:
                self.display_manager.clear()
            self.display_manager.draw_text("No Events", small_font=True, color=self.text_color)
            self.display_manager.update_display()
            return

        # Get the event to display
        if self.current_event_index >= len(self.events):
            self.current_event_index = 0 # Wrap around
        event_to_display = self.events[self.current_event_index]
        
        # Only log at INFO level when switching to calendar or when force_clear is True
        if force_clear:
            logger.info(f"CalendarManager displaying event index {self.current_event_index}: {event_to_display.get('summary')}")
        else:
            logger.debug(f"CalendarManager displaying event index {self.current_event_index}: {event_to_display.get('summary')}")
        
        # Only clear if forced or if this is a new event
        if force_clear:
            self.display_manager.clear()

        # Draw the event
        draw_successful = self.draw_event(event_to_display)

        if draw_successful:
            # Update the display
            self.display_manager.update_display()
            logger.debug("CalendarManager event display updated.")
        else:
            # Draw failed (error logged in draw_event), show debug message
            logger.warning("Failed to draw calendar event")
            if force_clear:
                self.display_manager.clear()
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