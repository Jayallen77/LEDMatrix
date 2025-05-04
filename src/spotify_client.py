import spotipy
from spotipy.oauth2 import SpotifyOAuth
import logging
import json
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Define paths relative to this file's location
CONFIG_DIR = os.path.join(os.path.dirname(__file__), '..', 'config')
SECRETS_PATH = os.path.join(CONFIG_DIR, 'config_secrets.json')

class SpotifyClient:
    def __init__(self):
        self.client_id = None
        self.client_secret = None
        self.redirect_uri = None
        self.scope = "user-read-currently-playing user-read-playback-state"
        self.sp = None
        self.load_credentials()
        if self.client_id and self.client_secret and self.redirect_uri:
            self._authenticate()
        else:
            logging.warning("Spotify credentials not loaded. Cannot authenticate.")


    def load_credentials(self):
        if not os.path.exists(SECRETS_PATH):
            logging.error(f"Secrets file not found at {SECRETS_PATH}")
            return

        try:
            with open(SECRETS_PATH, 'r') as f:
                secrets = json.load(f)
                music_secrets = secrets.get("music", {})
                self.client_id = music_secrets.get("SPOTIFY_CLIENT_ID")
                self.client_secret = music_secrets.get("SPOTIFY_CLIENT_SECRET")
                self.redirect_uri = music_secrets.get("SPOTIFY_REDIRECT_URI")
                if not all([self.client_id, self.client_secret, self.redirect_uri]):
                    logging.warning("One or more Spotify credentials missing in config_secrets.json under the 'music' key.")
        except json.JSONDecodeError:
            logging.error(f"Error decoding JSON from {SECRETS_PATH}")
        except Exception as e:
            logging.error(f"Error loading Spotify credentials: {e}")

    def _authenticate(self):
        """Handles the OAuth authentication flow."""
        try:
            # Spotipy handles token caching in .cache file by default
            self.sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
                client_id=self.client_id,
                client_secret=self.client_secret,
                redirect_uri=self.redirect_uri,
                scope=self.scope,
                open_browser=False # Important for headless environments
            ))
            # Try making a call to ensure authentication is working or trigger refresh
            self.sp.current_user()
            logging.info("Spotify authenticated successfully.")
        except Exception as e:
            logging.error(f"Spotify authentication failed: {e}")
            self.sp = None # Ensure sp is None if auth fails

    def is_authenticated(self):
        """Checks if the client is authenticated."""
        # Check if sp object exists and try a lightweight API call
        if not self.sp:
            return False
        try:
            # A simple call to verify token validity
            self.sp.current_user()
            return True
        except Exception as e:
            # Log specific auth errors if needed
            logging.warning(f"Spotify token validation failed: {e}")
            return False

    def get_auth_url(self):
         """Gets the authorization URL for the user."""
         # Create a temporary auth manager just to get the URL
         try:
             auth_manager = SpotifyOAuth(
                 client_id=self.client_id,
                 client_secret=self.client_secret,
                 redirect_uri=self.redirect_uri,
                 scope=self.scope,
                 open_browser=False
             )
             return auth_manager.get_authorize_url()
         except Exception as e:
            logging.error(f"Could not get Spotify auth URL: {e}")
            return None

    def get_current_track(self):
        """Fetches the currently playing track from Spotify."""
        if not self.is_authenticated():
            logging.warning("Spotify not authenticated. Cannot fetch track.")
            # Maybe try re-authenticating?
            self._authenticate()
            if not self.is_authenticated():
                 return None

        try:
            track_info = self.sp.current_playback()
            if track_info and track_info['item']:
                 # Simplify structure slightly if needed, or return raw
                 return track_info
            else:
                 return None # Nothing playing or unavailable
        except Exception as e:
            logging.error(f"Error fetching current track from Spotify: {e}")
            # Check for specific errors like token expiration if spotipy doesn't handle it
            if "expired" in str(e).lower():
                 logging.info("Spotify token might be expired, attempting refresh...")
                 self._authenticate() # Try to refresh/re-authenticate
            return None

# Example Usage (for testing)
# if __name__ == '__main__':
#     client = SpotifyClient()
#     if client.is_authenticated():
#         track = client.get_current_track()
#         if track:
#             print(json.dumps(track, indent=2))
#         else:
#             print("No track currently playing or error fetching.")
#     else:
#         auth_url = client.get_auth_url()
#         if auth_url:
#             print(f"Please authorize here: {auth_url}")
#         else:
#             print("Could not authenticate or get auth URL. Check credentials and config.") 