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
        
        # Scrolling state
        self.scroll_position = 0
        self.scroll_direction = 1  # 1 for down, -1 for up
        self.scroll_speed = 1  # pixels per frame
        self.scroll_delay = 0.1  # seconds between scroll updates
        self.last_scroll_time = 0
        self.scroll_enabled = False
        self.scroll_reset_time = 3  # seconds to wait before resetting scroll position
        
        logger.info(f"Calendar configuration: enabled={self.enabled}, update_interval={self.update_interval}, max_events={self.max_events}, calendars={self.calendars}")
        
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
            
            # Apply scroll offset
            y_pos -= self.scroll_position
            
            # Check if scrolling is needed
            if total_height > self.display_manager.matrix.height:
                self.scroll_enabled = True
            else:
                self.scroll_enabled = False
                self.scroll_position = 0

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
        max_lines = 3  # Maximum number of lines to display

        for word in words:
            test_line = ' '.join(current_line + [word])
            # Use textbbox for accurate width calculation
            bbox = self.display_manager.draw.textbbox((0, 0), test_line, font=font)
            text_width = bbox[2] - bbox[0]
            
            if text_width <= max_width:
                current_line.append(word)
            else:
                # If the word itself is too long, split it
                if not current_line:
                    # Check if the word itself is too long
                    bbox = self.display_manager.draw.textbbox((0, 0), word, font=font)
                    if bbox[2] - bbox[0] > max_width:
                        # Split long word into chunks that fit
                        chunks = []
                        current_chunk = ""
                        for char in word:
                            test_chunk = current_chunk + char
                            bbox = self.display_manager.draw.textbbox((0, 0), test_chunk, font=font)
                            if bbox[2] - bbox[0] <= max_width:
                                current_chunk = test_chunk
                            else:
                                chunks.append(current_chunk)
                                current_chunk = char
                        if current_chunk:
                            chunks.append(current_chunk)
                        lines.extend(chunks)
                    else:
                        lines.append(word)
                else:
                    lines.append(' '.join(current_line))
                current_line = [word]
                
                # If we've reached the maximum number of lines, add ellipsis to the last line
                if len(lines) >= max_lines:
                    last_line = lines[-1]
                    # Add ellipsis if there's room
                    bbox = self.display_manager.draw.textbbox((0, 0), last_line + "...", font=font)
                    if bbox[2] - bbox[0] <= max_width:
                        lines[-1] = last_line + "..."
                    else:
                        # If no room for ellipsis, remove last word and add ellipsis
                        words = last_line.split()
                        while words:
                            test_line = ' '.join(words[:-1]) + "..."
                            bbox = self.display_manager.draw.textbbox((0, 0), test_line, font=font)
                            if bbox[2] - bbox[0] <= max_width:
                                lines[-1] = test_line
                                break
                            words = words[:-1]
                    break
        
        if current_line and len(lines) < max_lines:
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
            
        # Only clear if force_clear is True (mode switch) or no events are drawn
        if force_clear:
            self.display_manager.clear()
            self.scroll_position = 0
            self.last_scroll_time = time.time()
            
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
        
        # Only log at INFO level when switching to calendar or when force_clear is True
        if force_clear:
            logger.info(f"CalendarManager displaying event index {self.current_event_index}: {event_to_display.get('summary')}")
            logger.info(f"CalendarManager displaying event: {event_to_display.get('summary')}")
            logger.info(f"Event details - Date: {self._format_event_date(event_to_display)}, Time: {self._format_event_time(event_to_display)}, Summary: {event_to_display.get('summary', 'No Title')}")
        else:
            logger.debug(f"CalendarManager displaying event index {self.current_event_index}: {event_to_display.get('summary')}")

        # Handle scrolling if enabled
        current_time = time.time()
        if self.scroll_enabled:
            if current_time - self.last_scroll_time >= self.scroll_delay:
                self.scroll_position += self.scroll_speed * self.scroll_direction
                
                # Check if we need to reverse direction
                if self.scroll_position <= 0:
                    self.scroll_direction = 1
                    self.scroll_position = 0
                elif self.scroll_position >= self.display_manager.matrix.height:
                    self.scroll_direction = -1
                    self.scroll_position = self.display_manager.matrix.height
                
                self.last_scroll_time = current_time

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