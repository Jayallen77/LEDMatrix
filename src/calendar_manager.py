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
        
        if self.enabled:
            self.authenticate()
        
        # Display properties
        self.text_color = (255, 255, 255)  # White
        self.date_color = (0, 255, 0)      # Green
        
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
    
    def draw_event(self, event, y_position):
        """Draw a single calendar event on the canvas."""
        try:
            # Get event details
            summary = event.get('summary', 'No Title')
            start = event.get('start', {}).get('dateTime', event.get('start', {}).get('date'))
            if start:
                start_time = datetime.fromisoformat(start.replace('Z', '+00:00'))
                time_str = start_time.strftime('%H:%M')
            else:
                time_str = 'All Day'
            
            # Create text to display
            text = f"{time_str} {summary}"
            
            # Draw text using display manager
            self.display_manager.draw_text(text, y=y_position, color=self.text_color, small_font=True)
            
            return y_position + 8  # Return next y position
        except Exception as e:
            logging.error(f"Error drawing calendar event: {str(e)}")
            return y_position
    
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

    def _format_event_time(self, event):
        """Format event time for display"""
        start = event['start'].get('dateTime', event['start'].get('date'))
        if 'T' in start:  # DateTime
            dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
            local_dt = dt.astimezone(pytz.local)
            return local_dt.strftime("%I:%M %p")
        else:  # All-day event
            return "All Day"

    def display(self):
        """Display calendar events on the matrix"""
        if not self.enabled or not self.events:
            return

        # Clear the display
        self.display_manager.clear()

        # Get current event to display
        if self.current_event_index >= len(self.events):
            self.current_event_index = 0
        event = self.events[self.current_event_index]

        # Display event time
        time_str = self._format_event_time(event)
        self.display_manager.draw_text(time_str, y=12, color=self.date_color, small_font=True)

        # Display event title (with scrolling if needed)
        title = event['summary']
        if len(title) > 10:  # Implement scrolling for long titles
            # Add scrolling logic here
            pass
        else:
            self.display_manager.draw_text(title, y=25, color=self.text_color, small_font=True)

        # Update the display
        self.display_manager.update_display()

        # Increment event index for next display
        self.current_event_index += 1 