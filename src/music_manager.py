import time
import threading
from enum import Enum, auto
import logging
import json
import os

# Use relative imports for clients within the same package (src)
from .spotify_client import SpotifyClient
from .ytm_client import YTMClient
# Removed: import config

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Define paths relative to this file's location
CONFIG_DIR = os.path.join(os.path.dirname(__file__), '..', 'config')
CONFIG_PATH = os.path.join(CONFIG_DIR, 'config.json')
# SECRETS_PATH is handled within SpotifyClient

class MusicSource(Enum):
    NONE = auto()
    SPOTIFY = auto()
    YTM = auto()

class MusicManager:
    def __init__(self, update_callback=None):
        self.spotify = None
        self.ytm = None
        self.current_track_info = None
        self.current_source = MusicSource.NONE
        self.update_callback = update_callback
        self.polling_interval = 2 # Default
        self.enabled = False # Default
        self.preferred_source = "auto" # Default
        self.stop_event = threading.Event()
        self._load_config() # Load config first
        self._initialize_clients() # Initialize based on loaded config
        self.poll_thread = None

    def _load_config(self):
        default_interval = 2
        default_preferred_source = "auto"
        self.enabled = False # Assume disabled until config proves otherwise

        if not os.path.exists(CONFIG_PATH):
            logging.warning(f"Config file not found at {CONFIG_PATH}. Music manager disabled.")
            return

        try:
            with open(CONFIG_PATH, 'r') as f:
                config_data = json.load(f)
                music_config = config_data.get("music", {})

                self.enabled = music_config.get("enabled", False)
                self.polling_interval = music_config.get("POLLING_INTERVAL_SECONDS", default_interval)
                self.preferred_source = music_config.get("preferred_source", default_preferred_source).lower()

                if not self.enabled:
                    logging.info("Music manager is disabled in config.json.")
                    return # Don't proceed further if disabled

                logging.info(f"Music manager enabled. Polling interval: {self.polling_interval}s. Preferred source: {self.preferred_source}")

        except json.JSONDecodeError:
            logging.error(f"Error decoding JSON from {CONFIG_PATH}. Music manager disabled.")
            self.enabled = False
        except Exception as e:
            logging.error(f"Error loading music config: {e}. Music manager disabled.")
            self.enabled = False

    def _initialize_clients(self):
        # Only initialize if the manager is enabled
        if not self.enabled:
            self.spotify = None
            self.ytm = None
            return

        logging.info("Initializing music clients...")

        # Initialize Spotify Client if needed
        if self.preferred_source in ["auto", "spotify"]:
            try:
                self.spotify = SpotifyClient()
                if not self.spotify.is_authenticated():
                    logging.warning("Spotify client initialized but not authenticated.")
                    # We still might need manual intervention by the user based on console output
                    auth_url = self.spotify.get_auth_url()
                    if auth_url:
                        print(f"---> Spotify requires authorization. Please visit: {auth_url}")
                        print("---> After authorizing, restart the application.")
                    else:
                         print("---> Could not get Spotify auth URL. Check config/config_secrets.json")
                else:
                    logging.info("Spotify client authenticated.")

            except Exception as e:
                logging.error(f"Failed to initialize Spotify client: {e}")
                self.spotify = None
        else:
            logging.info("Spotify client initialization skipped due to preferred_source setting.")
            self.spotify = None

        # Initialize YTM Client if needed
        if self.preferred_source in ["auto", "ytm"]:
            try:
                self.ytm = YTMClient()
                if not self.ytm.is_available():
                    logging.warning(f"YTM Companion server not reachable at {self.ytm.base_url}. YTM features disabled.")
                    self.ytm = None
                else:
                    logging.info(f"YTM Companion server connected at {self.ytm.base_url}.")
            except Exception as e:
                logging.error(f"Failed to initialize YTM client: {e}")
                self.ytm = None
        else:
            logging.info("YTM client initialization skipped due to preferred_source setting.")
            self.ytm = None

    def _poll_music_data(self):
        """Continuously polls music sources for updates, respecting preferences."""
        if not self.enabled:
             logging.warning("Polling attempted while music manager is disabled. Stopping polling thread.")
             return # Should not happen if start_polling checks enabled, but safety check

        while not self.stop_event.is_set():
            polled_track_info = None
            polled_source = MusicSource.NONE
            is_playing = False

            # Determine which sources to poll based on preference
            poll_spotify = self.preferred_source in ["auto", "spotify"] and self.spotify and self.spotify.is_authenticated()
            poll_ytm = self.preferred_source in ["auto", "ytm"] and self.ytm # Check if ytm object exists

            # --- Try Spotify First (if allowed and available) ---
            if poll_spotify:
                try:
                    spotify_track = self.spotify.get_current_track()
                    if spotify_track and spotify_track.get('is_playing'):
                        polled_track_info = spotify_track
                        polled_source = MusicSource.SPOTIFY
                        is_playing = True
                        logging.debug(f"Polling Spotify: Active track - {spotify_track.get('item', {}).get('name')}")
                    else:
                        logging.debug("Polling Spotify: No active track or player paused.")
                except Exception as e:
                    logging.error(f"Error polling Spotify: {e}")
                    if "token" in str(e).lower():
                        logging.warning("Spotify auth token issue detected during polling.")

            # --- Try YTM if Spotify isn't playing OR if YTM is preferred ---
            # If YTM is preferred, poll it even if Spotify might be playing (config override)
            # If Auto, only poll YTM if Spotify wasn't found playing
            should_poll_ytm_now = poll_ytm and (self.preferred_source == "ytm" or (self.preferred_source == "auto" and not is_playing))

            if should_poll_ytm_now:
                # Re-check availability just before polling
                if self.ytm.is_available():
                    try:
                        ytm_track = self.ytm.get_current_track()
                        if ytm_track and not ytm_track.get('player', {}).get('isPaused'):
                            # If YTM is preferred, it overrides Spotify even if Spotify was playing
                            if self.preferred_source == "ytm" or not is_playing:
                                polled_track_info = ytm_track
                                polled_source = MusicSource.YTM
                                is_playing = True
                                logging.debug(f"Polling YTM: Active track - {ytm_track.get('track', {}).get('title')}")
                        else:
                             logging.debug("Polling YTM: No active track or player paused.")
                    except Exception as e:
                        logging.error(f"Error polling YTM: {e}")
                else:
                     logging.debug("Skipping YTM poll: Server not available.")
                     # Consider setting self.ytm = None if it becomes unavailable repeatedly?

            # --- Consolidate and Check for Changes ---
            simplified_info = self.get_simplified_track_info(polled_track_info, polled_source)
            current_simplified_info = self.get_simplified_track_info(self.current_track_info, self.current_source)

            has_changed = False
            if simplified_info != current_simplified_info:
                has_changed = True
                self.current_track_info = polled_track_info
                self.current_source = polled_source
                display_title = simplified_info.get('title', 'None') if simplified_info else 'None'
                logging.info(f"Track change detected. Source: {self.current_source.name}. Track: {display_title}")
            else:
                logging.debug("No change in simplified track info.")

            if has_changed and self.update_callback:
                try:
                    self.update_callback(simplified_info)
                except Exception as e:
                    logging.error(f"Error executing update callback: {e}")

            time.sleep(self.polling_interval)

    # Modified to accept data and source, making it more testable/reusable
    def get_simplified_track_info(self, track_data, source):
        """Provides a consistent format for track info regardless of source."""
        if source == MusicSource.SPOTIFY and track_data:
            item = track_data.get('item', {})
            if not item: return None
            return {
                'source': 'Spotify',
                'title': item.get('name'),
                'artist': ', '.join([a['name'] for a in item.get('artists', [])]),
                'album': item.get('album', {}).get('name'),
                'album_art_url': item.get('album', {}).get('images', [{}])[0].get('url') if item.get('album', {}).get('images') else None,
                'duration_ms': item.get('duration_ms'),
                'progress_ms': track_data.get('progress_ms'),
                'is_playing': track_data.get('is_playing', False),
            }
        elif source == MusicSource.YTM and track_data:
            video_info = track_data.get('video', {}) # Corrected: song details are in 'video'
            player_info = track_data.get('player', {})

            title = video_info.get('title', 'Unknown Title')
            artist = video_info.get('author', 'Unknown Artist')
            album = video_info.get('album') # Can be null, handled by .get in return
            
            duration_seconds = video_info.get('durationSeconds')
            duration_ms = int(duration_seconds * 1000) if duration_seconds is not None else 0

            # Progress is in player_info.videoProgress (in seconds)
            progress_seconds = player_info.get('videoProgress')
            progress_ms = int(progress_seconds * 1000) if progress_seconds is not None else 0

            # Album art
            thumbnails = video_info.get('thumbnails', [])
            album_art_url = thumbnails[0].get('url') if thumbnails else None

            # Play state: player_info.trackState: -1 Unknown, 0 Paused, 1 Playing, 2 Buffering
            track_state = player_info.get('trackState')
            is_playing = (track_state == 1) # 1 means Playing

            # Check for ad playing, treat as 'paused' for track display purposes
            if player_info.get('adPlaying', False):
                is_playing = False # Or handle as a special state if needed
                logging.debug("YTM: Ad is playing, reporting track as not actively playing.")

            return {
                'source': 'YouTube Music',
                'title': title,
                'artist': artist,
                'album': album if album else '', # Ensure album is not None for display
                'album_art_url': album_art_url,
                'duration_ms': duration_ms,
                'progress_ms': progress_ms,
                'is_playing': is_playing,
            }
        else:
             # Return a default structure for 'nothing playing'
            return {
                'source': 'None',
                'title': 'Nothing Playing',
                'artist': '',
                'album': '',
                'album_art_url': None,
                'duration_ms': 0,
                'progress_ms': 0,
                'is_playing': False,
            }

    def get_current_display_info(self):
        """Returns the latest simplified info for display purposes."""
        # Return default "Nothing Playing" state if manager is disabled
        if not self.enabled:
             return self.get_simplified_track_info(None, MusicSource.NONE)
        return self.get_simplified_track_info(self.current_track_info, self.current_source)

    def start_polling(self):
        # Only start polling if enabled
        if not self.enabled:
            logging.info("Music manager disabled, polling not started.")
            return

        if not self.poll_thread or not self.poll_thread.is_alive():
            # Ensure at least one client is potentially available
            if not self.spotify and not self.ytm:
                 logging.warning("Cannot start polling: No music clients initialized or available.")
                 return

            self.stop_event.clear()
            self.poll_thread = threading.Thread(target=self._poll_music_data, daemon=True)
            self.poll_thread.start()
            logging.info("Music polling started.")

    def stop_polling(self):
        self.stop_event.set()
        if self.poll_thread and self.poll_thread.is_alive():
            self.poll_thread.join() # Wait for thread to finish
        logging.info("Music polling stopped.")

# Example Usage (for testing)
if __name__ == '__main__':
    def print_update(track_info):
        print("-" * 20)
        if track_info and track_info['source'] != 'None':
            print(f"Source: {track_info.get('source')}")
            print(f"Title: {track_info.get('title')}")
            print(f"Artist: {track_info.get('artist')}")
            print(f"Album: {track_info.get('album')}")
            print(f"Playing: {track_info.get('is_playing')}")
            print(f"Duration: {track_info.get('duration_ms')} ms")
            print(f"Progress: {track_info.get('progress_ms')} ms")
            print(f"Art URL: {track_info.get('album_art_url')}")
        else:
            print("Nothing playing or update is None.")
        print("-" * 20)

    manager = MusicManager(update_callback=print_update)
    manager.start_polling()

    try:
        # Keep the main thread alive to allow polling thread to run
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping polling...")
        manager.stop_polling()
        print("Exiting.") 