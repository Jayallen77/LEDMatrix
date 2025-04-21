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

class CalendarManager:
    def __init__(self, matrix, canvas, config):
        self.matrix = matrix
        self.canvas = canvas
        self.config = config
        self.calendar_config = config.get('calendar', {})
        self.enabled = self.calendar_config.get('enabled', False)
        self.update_interval = self.calendar_config.get('update_interval', 300)
        self.max_events = self.calendar_config.get('max_events', 3)
        self.calendars = self.calendar_config.get('calendars', ['primary'])
        self.last_update = 0
        self.events = []
        self.service = None
        
        # Get display manager instance
        from src.display_manager import DisplayManager
        self.display_manager = DisplayManager._instance
        
        # Get timezone from config
        self.config_manager = ConfigManager()
        timezone_str = self.config_manager.get_timezone()
        try:
            self.timezone = pytz.timezone(timezone_str)
        except pytz.UnknownTimeZoneError:
            logging.warning(f"Unknown timezone '{timezone_str}' in config, defaulting to UTC.")
            self.timezone = pytz.utc
        
        if self.enabled:
            self.authenticate()
        
        # Display properties
        self.text_color = (255, 255, 255)  # White
        self.time_color = (0, 255, 0)      # Green
        self.date_color = (200, 200, 200)  # Light Grey
        
        # State management
        self.current_event_index = 0

    def authenticate(self):
        """Authenticate with Google Calendar API."""
        creds = None
        token_file = self.calendar_config.get('token_file', 'token.pickle')
        
        if os.path.exists(token_file):
            with open(token_file, 'rb') as token:
                creds = pickle.load(token)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                logging.error("Calendar credentials not found or invalid. Please run calendar_registration.py first.")
                self.enabled = False
                return
        
        try:
            self.service = build('calendar', 'v3', credentials=creds)
            logging.info("Successfully authenticated with Google Calendar")
        except Exception as e:
            logging.error(f"Error building calendar service: {str(e)}")
            self.enabled = False
    
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
        """Draw a single calendar event on the canvas."""
        try:
            # Get event details
            summary = event.get('summary', 'No Title')
            time_str = self._format_event_time(event)
            date_str = self._format_event_date(event)
            
            # Use display manager's font for wrapping
            font = self.display_manager.small_font
            available_width = self.display_manager.matrix.width - 4  # Leave 2 pixel margin on each side
            
            # Wrap title text
            title_lines = self._wrap_text(summary, available_width, font)

            # Calculate total height needed
            date_height = 8 # Approximate height for date string
            time_height = 8 # Approximate height for time string
            title_height = len(title_lines) * 8 # Approximate height for title lines
            # Height = date + time + title + spacing between each
            total_height = date_height + time_height + title_height + ( (1 + len(title_lines)) * 2 ) 
            
            # Calculate starting y position to center vertically
            y_pos = (self.display_manager.matrix.height - total_height) // 2
            y_pos = max(1, y_pos) # Ensure it doesn't start above the top edge

            # Draw date in grey
            self.display_manager.draw_text(date_str, y=y_pos, color=self.date_color, small_font=True)
            y_pos += date_height + 2 # Move down for the time

            # Draw time in green
            self.display_manager.draw_text(time_str, y=y_pos, color=self.time_color, small_font=True)
            y_pos += time_height + 2 # Move down for the title
            
            # Draw title lines
            for line in title_lines:
                if y_pos >= self.display_manager.matrix.height - 8: # Stop if we run out of space
                    break
                self.display_manager.draw_text(line, y=y_pos, color=self.text_color, small_font=True)
                y_pos += 8 + 2 # Move down for the next line, add 2px spacing

        except Exception as e:
            logging.error(f"Error drawing calendar event: {str(e)}", exc_info=True)

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
        """Update calendar display if needed."""
        if not self.enabled:
            return
        
        if current_time - self.last_update >= self.update_interval:
            self.events = self.get_events()
            self.last_update = current_time
            
            # Clear the display
            self.display_manager.clear()
            
            # Draw each event
            y_pos = 1
            for event in self.events:
                y_pos = self.draw_event(event, y_pos)
                if y_pos >= self.matrix.height - 8:  # Leave some space at the bottom
                    break
            
            # Update the display
            self.display_manager.update_display()

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

    def display(self):
        """Display calendar events on the matrix"""
        if not self.enabled or not self.events:
            # Optionally display a 'No events' message here
            # self.display_manager.clear()
            # self.display_manager.draw_text("No Events", small_font=True)
            # self.display_manager.update_display()
            return

        # Clear the display
        self.display_manager.clear()

        # Get current event to display
        if self.current_event_index >= len(self.events):
            self.current_event_index = 0
        event = self.events[self.current_event_index]

        # Draw the event centered vertically
        self.draw_event(event)

        # Update the display
        self.display_manager.update_display()

        # Increment event index for next display
        self.current_event_index += 1 