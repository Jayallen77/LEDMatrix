import time
import threading
from enum import Enum, auto
import logging
import json
import os
from io import BytesIO
import requests
from PIL import Image, ImageEnhance
import queue # Added import

# Use relative imports for clients within the same package (src)
from .spotify_client import SpotifyClient
from .ytm_client import YTMClient
# Removed: import config

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Define paths relative to this file's location
CONFIG_DIR = os.path.join(os.path.dirname(__file__), '..', 'config')
CONFIG_PATH = os.path.join(CONFIG_DIR, 'config.json')
# SECRETS_PATH is handled within SpotifyClient

class MusicSource(Enum):
    NONE = auto()
    SPOTIFY = auto()
    YTM = auto()

class MusicManager:
    def __init__(self, display_manager, config, update_callback=None):
        self.display_manager = display_manager
        self.config = config
        self.spotify = None
        self.ytm = None
        self.current_track_info = None
        self.current_source = MusicSource.NONE
        self.update_callback = update_callback
        self.polling_interval = 2 # Default
        self.enabled = False # Default
        self.preferred_source = "spotify" # Default changed from "auto"
        self.stop_event = threading.Event()
        self.track_info_lock = threading.Lock() # Added lock

        # Display related attributes moved from DisplayController
        self.album_art_image = None
        self.last_album_art_url = None
        self.scroll_position_title = 0
        self.scroll_position_artist = 0
        self.title_scroll_tick = 0
        self.artist_scroll_tick = 0
        self.is_music_display_active = False # New state variable
        self.is_currently_showing_nothing_playing = False # To prevent flashing
        self._needs_immediate_full_refresh = False # Flag for forcing refresh from YTM updates
        self.ytm_event_data_queue = queue.Queue(maxsize=1) # Queue for event data
        
        self._load_config() # Load config first
        self._initialize_clients() # Initialize based on loaded config
        self.poll_thread = None

    def _load_config(self):
        default_interval = 2
        # default_preferred_source = "auto" # Removed
        self.enabled = False # Assume disabled until config proves otherwise

        if not os.path.exists(CONFIG_PATH):
            logging.warning(f"Config file not found at {CONFIG_PATH}. Music manager disabled.")
            return

        try:
            with open(CONFIG_PATH, 'r') as f:
                config_data = json.load(f)
                music_config = config_data.get("music", {})

                self.enabled = music_config.get("enabled", False)
                if not self.enabled:
                    logging.info("Music manager is disabled in config.json (top level 'enabled': false).")
                    return # Don't proceed further if disabled

                self.polling_interval = music_config.get("POLLING_INTERVAL_SECONDS", default_interval)
                configured_source = music_config.get("preferred_source", "spotify").lower()

                if configured_source in ["spotify", "ytm"]:
                    self.preferred_source = configured_source
                    logging.info(f"Music manager enabled. Polling interval: {self.polling_interval}s. Preferred source: {self.preferred_source}")
                else:
                    logging.warning(f"Invalid 'preferred_source' ('{configured_source}') in config.json. Must be 'spotify' or 'ytm'. Music manager disabled.")
                    self.enabled = False
                    return

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
        if self.preferred_source == "spotify":
            try:
                self.spotify = SpotifyClient()
                if not self.spotify.is_authenticated():
                    logging.warning("Spotify client initialized but not authenticated. Please run src/authenticate_spotify.py if you want to use Spotify.")
                else:
                    logging.info("Spotify client authenticated.")
            except Exception as e:
                logging.error(f"Failed to initialize Spotify client: {e}")
                self.spotify = None
        else:
            self.spotify = None # Ensure it's None if not preferred

        # Initialize YTM Client if needed
        if self.preferred_source == "ytm":
            try:
                self.ytm = YTMClient(update_callback=self._handle_ytm_direct_update)
                logging.info(f"YTMClient initialized. Connection will be managed on-demand. Configured URL: {self.ytm.base_url}")
            except Exception as e:
                logging.error(f"Failed to initialize YTM client: {e}")
                self.ytm = None
        else:
            self.ytm = None # Ensure it's None if not preferred

    def activate_music_display(self):
        logger.info("Music display activated.")
        self.is_music_display_active = True
        if self.ytm and self.preferred_source == "ytm":
            if not self.ytm.is_connected:
                logger.info("Attempting to connect YTM client due to music display activation.")
                if self.ytm.connect_client(timeout=10):
                    logger.info("YTM client connected successfully on display activation.")
                    # First event from YTM will populate the queue via _handle_ytm_direct_update
                else:
                    logger.warning("YTM client failed to connect on display activation.")
            else:
                logger.debug("YTM client already connected during music display activation.")
                # If already connected, a state update might be useful to ensure queue has latest
                # For now, rely on continuous updates or next explicit song change via YTM events.

    def deactivate_music_display(self):
        logger.info("Music display deactivated.")
        self.is_music_display_active = False
        if self.ytm and self.ytm.is_connected:
            logger.info("Disconnecting YTM client due to music display deactivation.")
            self.ytm.disconnect_client()

    def _handle_ytm_direct_update(self, ytm_data):
        """Handles a direct state update from YTMClient."""
        # Correctly log the title from the ytm_data structure
        raw_title_from_event = ytm_data.get('video', {}).get('title', 'No Title') if isinstance(ytm_data, dict) else 'Data not a dict'
        raw_artist_from_event = ytm_data.get('video', {}).get('author', 'No Author') if isinstance(ytm_data, dict) else 'Data not a dict'
        raw_album_art_from_event = ytm_data.get('video', {}).get('thumbnails', [{}])[0].get('url') if isinstance(ytm_data, dict) and ytm_data.get('video', {}).get('thumbnails') else 'No Album Art'
        raw_track_state_from_event = ytm_data.get('player', {}).get('trackState') if isinstance(ytm_data, dict) else 'No Track State'
        logger.debug(f"MusicManager._handle_ytm_direct_update: RAW EVENT DATA - Title: '{raw_title_from_event}', Artist: '{raw_artist_from_event}', ArtURL: '{raw_album_art_from_event}', TrackState: {raw_track_state_from_event}")

        if not self.enabled or not self.is_music_display_active: # Check if display is active
            logger.debug("Skipping YTM direct update: Manager disabled or music display not active.")
            return

        # Only process if YTM is the preferred source
        if self.preferred_source != "ytm":
            logger.debug(f"Skipping YTM direct update: Preferred source is '{self.preferred_source}', not 'ytm'.")
            return

        ytm_player_info = ytm_data.get('player', {}) if ytm_data else {}
        is_actually_playing_ytm = (ytm_player_info.get('trackState') == 1) and \
                                  not ytm_player_info.get('adPlaying', False)

        simplified_info = self.get_simplified_track_info(ytm_data if is_actually_playing_ytm else None, 
                                                       MusicSource.YTM if is_actually_playing_ytm else MusicSource.NONE)

        # Log simplified_info and current_track_info before comparison
        with self.track_info_lock: # Lock to safely read current_track_info for logging
            current_track_info_before_update_str = json.dumps(self.current_track_info) if self.current_track_info else "None"
        simplified_info_str = json.dumps(simplified_info)
        logger.debug(f"MusicManager._handle_ytm_direct_update: PRE-COMPARE - SimplifiedInfo: {simplified_info_str}, CurrentTrackInfo: {current_track_info_before_update_str}")

        processed_a_meaningful_update = False
        significant_track_change_detected = False # New flag

        with self.track_info_lock:
            # Determine if it's a significant change (title, artist, or album_art_url different)
            # or if current_track_info is None (first update is always significant)
            if self.current_track_info is None:
                significant_track_change_detected = True
            else:
                if (simplified_info.get('title') != self.current_track_info.get('title') or
                    simplified_info.get('artist') != self.current_track_info.get('artist') or
                    simplified_info.get('album_art_url') != self.current_track_info.get('album_art_url')):
                    significant_track_change_detected = True

            if simplified_info != self.current_track_info:
                processed_a_meaningful_update = True
                old_album_art_url = self.current_track_info.get('album_art_url') if self.current_track_info else None
                
                self.current_track_info = simplified_info
                logger.debug(f"MusicManager._handle_ytm_direct_update: POST-UPDATE (inside lock) - self.current_track_info now: {json.dumps(self.current_track_info)}")
                
                if is_actually_playing_ytm and simplified_info.get('source') == 'YouTube Music':
                    self.current_source = MusicSource.YTM
                elif not is_actually_playing_ytm and self.current_source == MusicSource.YTM: # YTM stopped
                    self.current_source = MusicSource.NONE
                # If simplified_info became 'Nothing Playing', current_source would be NONE from get_simplified_track_info

                new_album_art_url = simplified_info.get('album_art_url') if simplified_info else None

                logger.debug(f"[YTM Direct Update] Track info comparison: simplified_info != self.current_track_info was TRUE.")
                logger.debug(f"[YTM Direct Update] Old Album Art URL: {old_album_art_url}, New Album Art URL: {new_album_art_url}")

                if new_album_art_url != old_album_art_url:
                    logger.info("[YTM Direct Update] Album art URL changed. Clearing self.album_art_image to force re-fetch.")
                    self.album_art_image = None
                    self.last_album_art_url = new_album_art_url
                elif not self.last_album_art_url and new_album_art_url:
                    logger.info("[YTM Direct Update] New album art URL appeared (was None). Clearing self.album_art_image.")
                    self.album_art_image = None
                    self.last_album_art_url = new_album_art_url
                elif new_album_art_url is None and old_album_art_url is not None:
                    logger.info("[YTM Direct Update] Album art URL disappeared (became None). Clearing image and URL.")
                    self.album_art_image = None
                    self.last_album_art_url = None
                elif self.current_track_info and self.current_track_info.get('album_art_url') and not self.last_album_art_url:
                    self.last_album_art_url = self.current_track_info.get('album_art_url')
                    self.album_art_image = None
                
                display_title = self.current_track_info.get('title', 'None') if self.current_track_info else 'None'
                logger.info(f"YTM Direct Update: Track info updated. Source: {self.current_source.name}. New Track: {display_title}")
            else:
                # simplified_info IS THE SAME as self.current_track_info
                processed_a_meaningful_update = False
                logger.debug("YTM Direct Update: No change in simplified track info (simplified_info == self.current_track_info).")
                # Even if simplified_info is same, if self.current_track_info was None, it's a first load.
                if self.current_track_info is None and simplified_info.get('title') != 'Nothing Playing':
                    # This edge case might mean the very first update after 'Nothing Playing'
                    # was identical to what was already in simplified_info due to a rapid event.
                    # Consider it a significant change if we are moving from None to something.
                    significant_track_change_detected = True
                    processed_a_meaningful_update = True # Ensure current_track_info gets set
                    self.current_track_info = simplified_info # Explicitly set if it was None
                    logger.info("YTM Direct Update: First valid track data received, marking as significant change.")

        # Always try to update queue and signal refresh if YTM is source and display active
        # This ensures even progress updates (if simplified_info is the same) can trigger a UI refresh if needed.
        # And new songs will definitely pass their data via queue.
        try:
            # Clear previous item if any - we only want the latest
            while not self.ytm_event_data_queue.empty():
                try:
                    self.ytm_event_data_queue.get_nowait()
                except queue.Empty:
                    break # Should not happen with check but good for safety
            self.ytm_event_data_queue.put_nowait(simplified_info) # Pass the LATEST processed info
            logger.debug(f"MusicManager._handle_ytm_direct_update: Put simplified_info (Title: {simplified_info.get('title')}) into ytm_event_data_queue.")
        except queue.Full:
            logger.warning("MusicManager._handle_ytm_direct_update: ytm_event_data_queue was full. This should not happen with maxsize=1 and clearing.")
            # If full, the old item remains, which is fine, display will pick it up.

        if significant_track_change_detected:
            logger.info("YTM Direct Update: Significant track change detected. Signaling for an immediate full refresh of MusicManager display.")
            self._needs_immediate_full_refresh = True
        else:
            logger.debug("YTM Direct Update: No significant track change. UI will update progress/state without full refresh.")
            # Ensure _needs_immediate_full_refresh is False if no significant change,
            # in case it was somehow set by a rapid previous event that didn't get consumed.
            # self._needs_immediate_full_refresh = False # This might be too aggressive, display() consumes it.

        if self.update_callback:
            # Callback to DisplayController still useful to signal generic music update
            # DisplayController uses it to set its own force_clear, ensuring sync
            try:
                # Send a copy of what's now in current_track_info for consistency with polling path
                # Or send simplified_info if we want DisplayController to log the absolute latest event data.
                # Let's send simplified_info to make it consistent with what's put on the queue.
                self.update_callback(simplified_info, significant_track_change_detected) 
            except Exception as e:
                logger.error(f"Error executing DisplayController update callback from YTM direct update: {e}")

    def _fetch_and_resize_image(self, url: str, target_size: tuple[int, int]) -> Image.Image | None:
        """Fetches an image from a URL, resizes it, and returns a PIL Image object."""
        if not url:
            return None
        try:
            response = requests.get(url, timeout=5) # 5-second timeout for image download
            response.raise_for_status() # Raise an exception for bad status codes
            img_data = BytesIO(response.content)
            img = Image.open(img_data)
            
            # Ensure image is RGB for compatibility with the matrix
            img = img.convert("RGB") 
            
            img.thumbnail(target_size, Image.Resampling.LANCZOS)

            # Enhance contrast
            enhancer_contrast = ImageEnhance.Contrast(img)
            img = enhancer_contrast.enhance(1.3) # Adjust 1.3 as needed

            # Enhance saturation (Color)
            enhancer_saturation = ImageEnhance.Color(img)
            img = enhancer_saturation.enhance(1.3) # Adjust 1.3 as needed
            
            final_img = Image.new("RGB", target_size, (0,0,0)) # Black background
            paste_x = (target_size[0] - img.width) // 2
            paste_y = (target_size[1] - img.height) // 2
            final_img.paste(img, (paste_x, paste_y))
            
            return final_img
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching image from {url}: {e}")
            return None
        except IOError as e:
            logger.error(f"Error processing image from {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching/processing image {url}: {e}")
            return None

    def _poll_music_data(self):
        """Continuously polls music sources for updates, respecting preferences."""
        if not self.enabled:
             logging.warning("Polling attempted while music manager is disabled. Stopping polling thread.")
             return

        while not self.stop_event.is_set():
            polled_track_info_data = None
            polled_source = MusicSource.NONE
            is_playing_from_poll = False # Renamed to avoid conflict

            if self.preferred_source == "spotify" and self.spotify and self.spotify.is_authenticated():
                try:
                    spotify_track = self.spotify.get_current_track()
                    if spotify_track and spotify_track.get('is_playing'):
                        polled_track_info_data = spotify_track
                        polled_source = MusicSource.SPOTIFY
                        is_playing_from_poll = True
                        logging.debug(f"Polling Spotify: Active track - {spotify_track.get('item', {}).get('name')}")
                    else:
                        logging.debug("Polling Spotify: No active track or player paused.")
                except Exception as e:
                    logging.error(f"Error polling Spotify: {e}")
                    if "token" in str(e).lower():
                        logging.warning("Spotify auth token issue detected during polling.")
            
            elif self.preferred_source == "ytm" and self.ytm and self.ytm.is_connected:
                try:
                    ytm_track_data = self.ytm.get_current_track() # Data from YTMClient's cache
                    if ytm_track_data and ytm_track_data.get('player') and \
                       not ytm_track_data.get('player', {}).get('isPaused') and \
                       not ytm_track_data.get('player',{}).get('adPlaying', False):
                        polled_track_info_data = ytm_track_data
                        polled_source = MusicSource.YTM
                        is_playing_from_poll = True # YTM is now considered playing
                        logger.debug(f"Polling YTM: Active track - {ytm_track_data.get('track', {}).get('title')}")
                    else:
                        # logger.debug("Polling YTM: No active track or player paused (or track data missing player info).") # Potentially noisy
                        pass # Keep it quiet if no track or paused via polling
                except Exception as e:
                    logging.error(f"Error polling YTM: {e}")
            elif self.preferred_source == "ytm" and self.ytm and not self.ytm.is_connected:
                 logging.debug("Skipping YTM poll: Client not connected. Will attempt reconnect on next cycle if display active.")
                 # Attempt to reconnect YTM if music display is active and it's the preferred source
                 if self.is_music_display_active:
                     logger.info("YTM is preferred and display active, attempting reconnect during poll cycle.")
                     if self.ytm.connect_client(timeout=5):
                         logger.info("YTM reconnected during poll cycle.")
                     else:
                         logger.warning("YTM failed to reconnect during poll cycle.")

            simplified_info_poll = self.get_simplified_track_info(polled_track_info_data, polled_source)

            has_changed_poll = False
            with self.track_info_lock:
                if simplified_info_poll != self.current_track_info:
                    has_changed_poll = True
                    old_album_art_url_poll = self.current_track_info.get('album_art_url') if self.current_track_info else None
                    new_album_art_url_poll = simplified_info_poll.get('album_art_url') if simplified_info_poll else None

                    self.current_track_info = simplified_info_poll
                    self.current_source = polled_source

                    logger.debug(f"[Poll Update] Old Album Art URL: {old_album_art_url_poll}, New Album Art URL: {new_album_art_url_poll}")
                    if new_album_art_url_poll != old_album_art_url_poll:
                        logger.info("[Poll Update] Album art URL changed. Clearing self.album_art_image to force re-fetch.")
                        self.album_art_image = None
                        self.last_album_art_url = new_album_art_url_poll
                    elif not self.last_album_art_url and new_album_art_url_poll: # Case where old was None, new is something
                        logger.info("[Poll Update] New album art URL appeared (was None). Clearing self.album_art_image.")
                        self.album_art_image = None
                        self.last_album_art_url = new_album_art_url_poll
                    elif new_album_art_url_poll is None and old_album_art_url_poll is not None:
                        logger.info("[Poll Update] Album art URL disappeared (became None). Clearing image and URL.")
                        self.album_art_image = None
                        self.last_album_art_url = None
                    elif self.current_track_info and self.current_track_info.get('album_art_url') and not self.last_album_art_url:
                         self.last_album_art_url = self.current_track_info.get('album_art_url')
                         self.album_art_image = None # Ensure image is cleared if URL was just populated from None
                    
                    display_title_poll = self.current_track_info.get('title', 'None') if self.current_track_info else 'None'
                    logger.debug(f"Poll Update: Track change detected. Source: {self.current_source.name}. Track: {display_title_poll}")
                else:
                    logger.debug("Poll Update: No change in simplified track info.")

            if has_changed_poll and self.update_callback:
                try:
                    with self.track_info_lock:
                        track_info_copy_poll = self.current_track_info.copy() if self.current_track_info else None
                    self.update_callback(track_info_copy_poll, True) # Poll changes are considered significant
                except Exception as e:
                    logger.error(f"Error executing update callback from poll: {e}")
            
            time.sleep(self.polling_interval)

    # Modified to accept data and source, making it more testable/reusable
    def get_simplified_track_info(self, track_data, source):
        """Provides a consistent format for track info regardless of source."""
        
        # Default "Nothing Playing" structure
        nothing_playing_info = {
            'source': 'None',
            'title': 'Nothing Playing',
            'artist': '',
            'album': '',
            'album_art_url': None,
            'duration_ms': 0,
            'progress_ms': 0,
            'is_playing': False,
        }

        if source == MusicSource.SPOTIFY and track_data:
            item = track_data.get('item', {})
            is_playing_spotify = track_data.get('is_playing', False)

            if not item or not is_playing_spotify:
                return nothing_playing_info.copy()

            return {
                'source': 'Spotify',
                'title': item.get('name'),
                'artist': ', '.join([a['name'] for a in item.get('artists', [])]),
                'album': item.get('album', {}).get('name'),
                'album_art_url': item.get('album', {}).get('images', [{}])[0].get('url') if item.get('album', {}).get('images') else None,
                'duration_ms': item.get('duration_ms'),
                'progress_ms': track_data.get('progress_ms'),
                'is_playing': is_playing_spotify, # Should be true here
            }
        elif source == MusicSource.YTM and track_data:
            video_info = track_data.get('video', {})
            player_info = track_data.get('player', {})

            title = video_info.get('title') 
            artist = video_info.get('author')
            
            track_state = player_info.get('trackState')
            is_playing_ytm = (track_state == 1) 

            if player_info.get('adPlaying', False):
                is_playing_ytm = False 
                logging.debug("YTM: Ad is playing, reporting track as not actively playing.")
            
            logger.debug(f"[get_simplified_track_info YTM] Title: {title}, Artist: {artist}, TrackState: {track_state}, IsPlayingYTM: {is_playing_ytm}, AdPlaying: {player_info.get('adPlaying')}")

            if not title or not artist or not is_playing_ytm: 
                logger.debug("[get_simplified_track_info YTM] Condition met for Nothing Playing.")
                return nothing_playing_info.copy()

            logger.debug("[get_simplified_track_info YTM] Proceeding to return full track details.")
            album = video_info.get('album')
            duration_seconds = video_info.get('durationSeconds')
            duration_ms = int(duration_seconds * 1000) if duration_seconds is not None else 0
            progress_seconds = player_info.get('videoProgress')
            progress_ms = int(progress_seconds * 1000) if progress_seconds is not None else 0
            thumbnails = video_info.get('thumbnails', [])
            album_art_url = thumbnails[0].get('url') if thumbnails else None

            return {
                'source': 'YouTube Music',
                'title': title,
                'artist': artist,
                'album': album if album else '',
                'album_art_url': album_art_url,
                'duration_ms': duration_ms,
                'progress_ms': progress_ms,
                'is_playing': is_playing_ytm, # Should be true here
            }
        else:
            # This covers cases where source is NONE, or track_data is None for Spotify/YTM
            return nothing_playing_info.copy()

    def get_current_display_info(self):
        """Returns the currently stored track information for display."""
        with self.track_info_lock:
            return self.current_track_info.copy() if self.current_track_info else None

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
        """Stops the music polling thread."""
        logger.info("Music manager: Stopping polling thread...")
        self.stop_event.set()
        if self.poll_thread and self.poll_thread.is_alive():
            self.poll_thread.join(timeout=self.polling_interval + 1) # Wait for thread to finish
        if self.poll_thread and self.poll_thread.is_alive():
            logger.warning("Music manager: Polling thread did not terminate cleanly.")
        else:
            logger.info("Music manager: Polling thread stopped.")
        self.poll_thread = None # Clear the thread object
        # Also ensure YTM client is disconnected when polling stops completely
        if self.ytm:
            logger.info("MusicManager: Shutting down YTMClient resources.")
            if self.ytm.is_connected:
                 self.ytm.disconnect_client()
            self.ytm.shutdown() # Call the new shutdown method for the executor

    # Method moved from DisplayController and renamed
    def display(self, force_clear: bool = False):
        perform_full_refresh_this_cycle = force_clear 
        data_from_event_queue = None

        if self._needs_immediate_full_refresh:
            logger.debug("MusicManager.display: _needs_immediate_full_refresh is True.")
            perform_full_refresh_this_cycle = True
            self._needs_immediate_full_refresh = False # Consume the flag
            try:
                data_from_event_queue = self.ytm_event_data_queue.get_nowait()
                logger.info(f"MusicManager.display: Got data from ytm_event_data_queue (Title: {data_from_event_queue.get('title') if data_from_event_queue else 'None'}).")
            except queue.Empty:
                logger.warning("MusicManager.display: _needs_immediate_full_refresh was true, but ytm_event_data_queue was empty. Falling back to current_track_info.")
        
        current_track_info_snapshot = None
        if data_from_event_queue:
            # Priority to data from the event queue that signaled this refresh
            current_track_info_snapshot = data_from_event_queue
            # Also, make sure self.current_track_info reflects this event data if it's what we're displaying.
            # This is important if an event was so fast it didn't get written to self.current_track_info
            # by the _handle_ytm_direct_update's main path before display() runs with queue data.
            # However, _handle_ytm_direct_update already updates self.current_track_info under lock.
            # So, if queue has data, self.current_track_info should ideally match it or be about to.
            # For simplicity, we'll primarily use the queued data for *this render* if available.
            # The main self.current_track_info is updated by the callback thread.
            logger.debug(f"MusicManager.display: Using data_from_event_queue for snapshot.")
        else:
            # Fallback or standard operation (e.g. polling update, or regular display cycle without fresh event)
            with self.track_info_lock: 
                current_track_info_snapshot = self.current_track_info.copy() if self.current_track_info else None
            logger.debug(f"MusicManager.display: Using self.current_track_info for snapshot.")

        if perform_full_refresh_this_cycle:
            snapshot_title_for_log = current_track_info_snapshot.get('title', 'N/A') if current_track_info_snapshot else 'N/A'
            logger.debug(f"MusicManager.display (Full Refresh): Using track_info_snapshot - Title: '{snapshot_title_for_log}'")

        if perform_full_refresh_this_cycle:
            self.display_manager.clear()
            self.activate_music_display() 

        with self.track_info_lock:
            current_track_info_snapshot = self.current_track_info.copy() if self.current_track_info else None
            # Get the URL of the currently cached image and the image itself
            art_url_currently_in_cache = self.last_album_art_url
            image_currently_in_cache = self.album_art_image

        if not current_track_info_snapshot or current_track_info_snapshot.get('title') == 'Nothing Playing':
            if not hasattr(self, '_last_nothing_playing_log_time') or \
               time.time() - getattr(self, '_last_nothing_playing_log_time', 0) > 30:
                logger.debug("Music Screen (MusicManager): Nothing playing or info explicitly 'Nothing Playing'.")
                self._last_nothing_playing_log_time = time.time()

            if not self.is_currently_showing_nothing_playing or perform_full_refresh_this_cycle:
                if perform_full_refresh_this_cycle or not self.is_currently_showing_nothing_playing:
                    self.display_manager.clear()
                
                text_width = self.display_manager.get_text_width("Nothing Playing", self.display_manager.regular_font)
                x_pos = (self.display_manager.matrix.width - text_width) // 2
                y_pos = (self.display_manager.matrix.height // 2) - 4
                self.display_manager.draw_text("Nothing Playing", x=x_pos, y=y_pos, font=self.display_manager.regular_font)
                self.display_manager.update_display()
                self.is_currently_showing_nothing_playing = True

            with self.track_info_lock: 
                self.scroll_position_title = 0
                self.scroll_position_artist = 0
                self.title_scroll_tick = 0
                self.artist_scroll_tick = 0
                # If showing "Nothing Playing", ensure no stale art is cached for an invalid URL
                if self.album_art_image is not None or self.last_album_art_url is not None:
                    logger.debug("Clearing album art cache as 'Nothing Playing' is displayed.")
                    self.album_art_image = None
                    self.last_album_art_url = None
            return

        # If we're here, we are displaying actual music info.
        self.is_currently_showing_nothing_playing = False 

        # Reset scroll positions if force_clear was true (now stored in should_reset_scroll_for_music)
        # and we are about to display a new track.
        if perform_full_refresh_this_cycle and not self.is_currently_showing_nothing_playing : # only reset if showing actual music
            title_being_displayed = current_track_info_snapshot.get('title','N/A') if current_track_info_snapshot else "N/A"
            logger.debug(f"MusicManager: Resetting scroll positions for track '{title_being_displayed}' due to full refresh signal.")
            self.scroll_position_title = 0
            self.scroll_position_artist = 0

        if not self.is_music_display_active: 
            self.activate_music_display()

        if not perform_full_refresh_this_cycle: # if not force_clear (which clears whole screen)
            self.display_manager.draw.rectangle([0, 0, self.display_manager.matrix.width, self.display_manager.matrix.height], fill=(0, 0, 0))

        matrix_height = self.display_manager.matrix.height
        album_art_size = matrix_height - 2 
        album_art_target_size = (album_art_size, album_art_size)
        album_art_x = 1
        album_art_y = 1
        text_area_x_start = album_art_x + album_art_size + 2 
        text_area_width = self.display_manager.matrix.width - text_area_x_start - 1 

        # Album art logic using the snapshot and careful cache updates
        image_to_render_this_cycle = None
        target_art_url_for_current_track = current_track_info_snapshot.get('album_art_url')

        if target_art_url_for_current_track:
            if image_currently_in_cache and art_url_currently_in_cache == target_art_url_for_current_track:
                # Cached image is valid for the track we are rendering
                image_to_render_this_cycle = image_currently_in_cache
                logger.debug(f"Using cached album art for {target_art_url_for_current_track}")
            else:
                # No valid cached image; need to fetch.
                logger.info(f"MusicManager: Fetching album art for: {target_art_url_for_current_track}")
                fetched_image = self._fetch_and_resize_image(target_art_url_for_current_track, album_art_target_size)
                if fetched_image:
                    logger.info(f"MusicManager: Album art for {target_art_url_for_current_track} fetched successfully.")
                    with self.track_info_lock:
                        # Critical check: Before updating shared cache, ensure this URL is STILL the latest one.
                        # self.current_track_info (the live one) might have updated again during the fetch.
                        latest_known_art_url_in_live_info = self.current_track_info.get('album_art_url') if self.current_track_info else None
                        if target_art_url_for_current_track == latest_known_art_url_in_live_info:
                            self.album_art_image = fetched_image
                            self.last_album_art_url = target_art_url_for_current_track # Mark cache as valid for this URL
                            image_to_render_this_cycle = fetched_image
                            logger.debug(f"Cached and will render new art for {target_art_url_for_current_track}")
                        else:
                            logger.info(f"MusicManager: Discarding fetched art for {target_art_url_for_current_track}; "
                                        f"track changed to '{self.current_track_info.get('title', 'N/A')}' "
                                        f"with art '{latest_known_art_url_in_live_info}' during fetch.")
                            # image_to_render_this_cycle remains None, placeholder will be shown.
                else:
                    logger.warning(f"MusicManager: Failed to fetch or process album art for {target_art_url_for_current_track}.")
                    # If fetch failed, ensure we don't use an older image for this URL.
                    # And mark that we tried for this URL, so we don't immediately retry unless track changes.
                    with self.track_info_lock:
                        if self.last_album_art_url == target_art_url_for_current_track:
                             self.album_art_image = None # Clear any potentially older image for this specific failed URL
                        # self.last_album_art_url is typically already set to target_art_url_for_current_track by update handlers.
                        # So, if fetch fails, self.album_art_image becomes None for this URL.
                        # We won't re-fetch unless target_art_url_for_current_track changes (new song or art update).
        else:
            # No art URL for the current track (current_track_info_snapshot.get('album_art_url') is None).
            logger.debug(f"No album art URL for track: {current_track_info_snapshot.get('title', 'N/A')}. Clearing cache.")
            with self.track_info_lock:
                if self.album_art_image is not None or self.last_album_art_url is not None:
                    self.album_art_image = None
                    self.last_album_art_url = None # Reflects no art is currently desired/available

        if image_to_render_this_cycle:
            self.display_manager.image.paste(image_to_render_this_cycle, (album_art_x, album_art_y))
        else:
            # Display placeholder if no image is to be rendered
            self.display_manager.draw.rectangle([album_art_x, album_art_y, 
                                                 album_art_x + album_art_size -1, album_art_y + album_art_size -1],
                                                 outline=(50,50,50), fill=(10,10,10))

        # Use current_track_info_snapshot for text, which is consistent for this render cycle
        title = current_track_info_snapshot.get('title', ' ')
        artist = current_track_info_snapshot.get('artist', ' ')
        album = current_track_info_snapshot.get('album', ' ') 

        font_title = self.display_manager.small_font
        font_artist_album = self.display_manager.bdf_5x7_font
        line_height_title = 8 
        line_height_artist_album = 7 
        padding_between_lines = 1 

        TEXT_SCROLL_DIVISOR = 5 

        # --- Title --- 
        y_pos_title = 2 
        title_width = self.display_manager.get_text_width(title, font_title)
        current_title_display_text = title
        if title_width > text_area_width:
            if self.scroll_position_title >= len(title):
                self.scroll_position_title = 0
            current_title_display_text = title[self.scroll_position_title:] + "   " + title[:self.scroll_position_title]
        
        self.display_manager.draw_text(current_title_display_text, 
                                     x=text_area_x_start, y=y_pos_title, color=(255, 255, 255), font=font_title)
        if title_width > text_area_width:
            self.title_scroll_tick += 1
            if self.title_scroll_tick % TEXT_SCROLL_DIVISOR == 0:
                self.scroll_position_title = (self.scroll_position_title + 1) % len(title)
                self.title_scroll_tick = 0 
        else:
            self.scroll_position_title = 0
            self.title_scroll_tick = 0

        # --- Artist --- 
        y_pos_artist = y_pos_title + line_height_title + padding_between_lines
        artist_width = self.display_manager.get_text_width(artist, font_artist_album)
        current_artist_display_text = artist
        if artist_width > text_area_width:
            if self.scroll_position_artist >= len(artist):
                self.scroll_position_artist = 0
            current_artist_display_text = artist[self.scroll_position_artist:] + "   " + artist[:self.scroll_position_artist]

        self.display_manager.draw_text(current_artist_display_text, 
                                      x=text_area_x_start, y=y_pos_artist, color=(180, 180, 180), font=font_artist_album)
        if artist_width > text_area_width:
            self.artist_scroll_tick += 1
            if self.artist_scroll_tick % TEXT_SCROLL_DIVISOR == 0:
                self.scroll_position_artist = (self.scroll_position_artist + 1) % len(artist)
                self.artist_scroll_tick = 0
        else:
            self.scroll_position_artist = 0
            self.artist_scroll_tick = 0
            
        # --- Album ---
        y_pos_album = y_pos_artist + line_height_artist_album + padding_between_lines
        if (matrix_height - y_pos_album - 5) >= line_height_artist_album : 
            album_width = self.display_manager.get_text_width(album, font_artist_album)
            if album_width <= text_area_width: 
                 self.display_manager.draw_text(album, x=text_area_x_start, y=y_pos_album, color=(150, 150, 150), font=font_artist_album)

        # --- Progress Bar --- 
        progress_bar_height = 3
        progress_bar_y = matrix_height - progress_bar_height - 1 
        duration_ms = current_track_info_snapshot.get('duration_ms', 0)
        progress_ms = current_track_info_snapshot.get('progress_ms', 0)

        if duration_ms > 0:
            bar_total_width = text_area_width
            filled_ratio = progress_ms / duration_ms
            filled_width = int(filled_ratio * bar_total_width)

            self.display_manager.draw.rectangle([
                text_area_x_start, progress_bar_y, 
                text_area_x_start + bar_total_width -1, progress_bar_y + progress_bar_height -1
            ], outline=(60, 60, 60), fill=(30,30,30)) 
            
            if filled_width > 0:
                self.display_manager.draw.rectangle([
                    text_area_x_start, progress_bar_y, 
                    text_area_x_start + filled_width -1, progress_bar_y + progress_bar_height -1
                ], fill=(200, 200, 200)) 

        self.display_manager.update_display()


# Example usage (for testing this module standalone, if needed)
# def print_update(track_info):
# logging.info(f"Callback: Track update received by dummy callback: {track_info}")

if __name__ == '__main__':
    # This is a placeholder for testing. 
    # To test properly, you'd need a mock DisplayManager and ConfigManager.
    logging.basicConfig(level=logging.DEBUG)
    logger.info("Running MusicManager standalone test (limited)...")

    # Mock DisplayManager and Config objects
    class MockDisplayManager:
        def __init__(self):
            self.matrix = type('Matrix', (), {'width': 64, 'height': 32})() # Mock matrix
            self.image = Image.new("RGB", (self.matrix.width, self.matrix.height))
            self.draw = ImageDraw.Draw(self.image) # Requires ImageDraw
            self.regular_font = None # Needs font loading
            self.small_font = None
            self.extra_small_font = None
            # Add other methods/attributes DisplayManager uses if they are called by MusicManager's display
            # For simplicity, we won't fully mock font loading here.
            # self.regular_font = ImageFont.truetype("path/to/font.ttf", 8) 


        def clear(self): logger.debug("MockDisplayManager: clear() called")
        def get_text_width(self, text, font): return len(text) * 5 # Rough mock
        def draw_text(self, text, x, y, color=(255,255,255), font=None): logger.debug(f"MockDisplayManager: draw_text '{text}' at ({x},{y})")
        def update_display(self): logger.debug("MockDisplayManager: update_display() called")

    class MockConfig:
        def get(self, key, default=None):
            if key == "music":
                return {"enabled": True, "POLLING_INTERVAL_SECONDS": 2, "preferred_source": "auto"}
            return default

    # Need to import ImageDraw for the mock to work if draw_text is complex
    try: from PIL import ImageDraw, ImageFont 
    except ImportError: ImageDraw = None; ImageFont = None; logger.warning("Pillow ImageDraw/ImageFont not fully available for mock")


    mock_display = MockDisplayManager()
    mock_config_main = {"music": {"enabled": True, "POLLING_INTERVAL_SECONDS": 2, "preferred_source": "auto"}}
    
    # The MusicManager expects the overall config, not just the music part directly for its _load_config
    # So we simulate a config object that has a .get('music', {}) method.
    # However, MusicManager's _load_config reads from CONFIG_PATH.
    # For a true standalone test, we might need to mock file IO or provide a test config file.

    # Simplified test:
    # manager = MusicManager(display_manager=mock_display, config=mock_config_main) # This won't work due to file reading
    
    # To truly test, you'd point CONFIG_PATH to a test config.json or mock open()
    # For now, this __main__ block is mostly a placeholder.
    logger.info("MusicManager standalone test setup is complex due to file dependencies for config.")
    logger.info("To test: run the main application and observe logs from MusicManager.")
    # if manager.enabled:
    # manager.start_polling()
    # try:
    # while True:
    #         time.sleep(1)
    #         # In a real test, you might manually call manager.display() after setting some track info
    # except KeyboardInterrupt:
    #         logger.info("Stopping standalone test...")
    # finally:
    # if manager.enabled:
    # manager.stop_polling()
    #         logger.info("Test finished.") 