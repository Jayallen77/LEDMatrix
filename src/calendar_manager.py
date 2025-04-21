from datetime import datetime, timedelta
import pickle
import os.path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from rgbmatrix import graphics
import pytz

class CalendarManager:
    def __init__(self, matrix, canvas, config):
        self.matrix = matrix
        self.canvas = canvas
        self.config = config.get('calendar', {})
        self.enabled = self.config.get('enabled', False)
        self.update_interval = self.config.get('update_interval', 300)
        self.max_events = self.config.get('max_events', 3)
        self.token_file = self.config.get('token_file', 'token.pickle')
        
        # Display properties
        self.font = graphics.Font()
        self.font.LoadFont("assets/fonts/7x13.bdf")
        self.text_color = graphics.Color(255, 255, 255)
        self.date_color = graphics.Color(0, 255, 0)
        
        # State management
        self.last_update = None
        self.events = []
        self.service = None
        self.current_event_index = 0
        
        # Initialize the calendar service
        self._initialize_service()

    def _initialize_service(self):
        """Initialize the Google Calendar service with stored credentials"""
        if not os.path.exists(self.token_file):
            print(f"No token file found at {self.token_file}")
            print("Please run calendar_registration.py first")
            self.enabled = False
            return

        try:
            with open(self.token_file, 'rb') as token:
                creds = pickle.load(token)

            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                    # Save the refreshed credentials
                    with open(self.token_file, 'wb') as token:
                        pickle.dump(creds, token)
                else:
                    print("Invalid credentials. Please run calendar_registration.py")
                    self.enabled = False
                    return

            self.service = build('calendar', 'v3', credentials=creds)
        except Exception as e:
            print(f"Error initializing calendar service: {e}")
            self.enabled = False

    def _fetch_events(self):
        """Fetch upcoming events from Google Calendar"""
        if not self.service:
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
            return events_result.get('items', [])
        except Exception as e:
            print(f"Error fetching calendar events: {e}")
            return []

    def update(self):
        """Update calendar events if needed"""
        if not self.enabled:
            return

        current_time = datetime.now()
        if (self.last_update is None or 
            (current_time - self.last_update).seconds > self.update_interval):
            self.events = self._fetch_events()
            self.last_update = current_time

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

        # Clear the canvas
        self.canvas.Clear()

        # Get current event to display
        if self.current_event_index >= len(self.events):
            self.current_event_index = 0
        event = self.events[self.current_event_index]

        # Display event time
        time_str = self._format_event_time(event)
        graphics.DrawText(self.canvas, self.font, 1, 12, self.date_color, time_str)

        # Display event title (with scrolling if needed)
        title = event['summary']
        if len(title) > 10:  # Implement scrolling for long titles
            # Add scrolling logic here
            pass
        else:
            graphics.DrawText(self.canvas, self.font, 1, 25, self.text_color, title)

        # Increment event index for next display
        self.current_event_index += 1 