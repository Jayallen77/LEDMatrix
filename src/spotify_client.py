import spotipy
from spotipy.oauth2 import SpotifyOAuth
import logging
import json
import os
import time

try:
    from src.spotify_auth_utils import (
        ensure_spotify_cache_access,
        get_expected_runtime_user,
        get_spotify_cache_path,
        log_spotify_cache_diagnostics,
    )
except ImportError:
    from spotify_auth_utils import (  # type: ignore
        ensure_spotify_cache_access,
        get_expected_runtime_user,
        get_spotify_cache_path,
        log_spotify_cache_diagnostics,
    )

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Define paths relative to this file's location
CONFIG_DIR = os.path.join(os.path.dirname(__file__), '..', 'config')
SECRETS_PATH = os.path.join(CONFIG_DIR, 'config_secrets.json')
SPOTIFY_AUTH_CACHE_PATH = get_spotify_cache_path()

# Resolve to absolute paths
CONFIG_DIR = os.path.abspath(CONFIG_DIR)
SECRETS_PATH = os.path.abspath(SECRETS_PATH)
SPOTIFY_AUTH_CACHE_PATH = os.path.abspath(SPOTIFY_AUTH_CACHE_PATH)

class SpotifyClient:
    STATE_READY = "ready"
    STATE_RETRYABLE = "retryable"
    STATE_REAUTH_REQUIRED = "reauth_required"

    INITIAL_RETRY_DELAY_SECONDS = 2
    MAX_RETRY_DELAY_SECONDS = 60

    def __init__(self):
        self.client_id = None
        self.client_secret = None
        self.redirect_uri = None
        self.scope = "user-read-currently-playing user-read-playback-state"
        self.sp = None
        self.auth_manager = None
        self.state = self.STATE_RETRYABLE
        self.retry_attempts = 0
        self.next_retry_at = 0.0
        self.last_error = None
        self.load_credentials()
        if self.client_id and self.client_secret and self.redirect_uri:
            self._authenticate()
        else:
            self._mark_reauth_required("Spotify credentials are missing.")

    def load_credentials(self):
        if not os.path.exists(SECRETS_PATH):
            logging.error(f"Secrets file not found at {SECRETS_PATH}. Spotify features will be unavailable.")
            return

        try:
            with open(SECRETS_PATH, 'r') as f:
                secrets = json.load(f)
                music_secrets = secrets.get("music", {})
                self.client_id = music_secrets.get("SPOTIFY_CLIENT_ID")
                self.client_secret = music_secrets.get("SPOTIFY_CLIENT_SECRET")
                self.redirect_uri = music_secrets.get("SPOTIFY_REDIRECT_URI")
                if not all([self.client_id, self.client_secret, self.redirect_uri]):
                    logging.warning("One or more Spotify credentials missing in config_secrets.json. Spotify will be unavailable.")
        except json.JSONDecodeError:
            logging.error(f"Error decoding JSON from {SECRETS_PATH}. Spotify will be unavailable.")
        except Exception as e:
            logging.error(f"Error loading Spotify credentials: {e}. Spotify will be unavailable.")

    def _authenticate(self):
        """Initializes Spotipy with SpotifyOAuth, relying on a cached token."""
        if not self.client_id or not self.client_secret or not self.redirect_uri:
            self._mark_reauth_required("Cannot authenticate Spotify: credentials are missing.")
            return

        logger.info(
            "SpotifyClient using cache path: %s (expected runtime user: %s)",
            SPOTIFY_AUTH_CACHE_PATH,
            get_expected_runtime_user(),
        )
        diagnostics = log_spotify_cache_diagnostics(SPOTIFY_AUTH_CACHE_PATH, logger=logger)

        try:
            self.auth_manager = SpotifyOAuth(
                client_id=self.client_id,
                client_secret=self.client_secret,
                redirect_uri=self.redirect_uri,
                scope=self.scope,
                cache_path=SPOTIFY_AUTH_CACHE_PATH,
                open_browser=False
            )

            cached_token = self._get_cached_token()
            if not cached_token or not cached_token.get("access_token"):
                if diagnostics.get("exists") and not diagnostics.get("readable", False):
                    self._mark_retryable("Spotify auth cache exists but is not readable.")
                else:
                    self._mark_reauth_required(
                        "No valid Spotify playback token was found in the cache."
                    )
                return

            self._get_access_token()
            ensure_spotify_cache_access(SPOTIFY_AUTH_CACHE_PATH, logger=logger)
            log_spotify_cache_diagnostics(SPOTIFY_AUTH_CACHE_PATH, logger=logger)
            self.sp = spotipy.Spotify(auth_manager=self.auth_manager)
            self._mark_ready()
            logger.info("Spotify client initialized and authenticated using cached token.")
        except Exception as exc:
            self.sp = None
            if self._is_reauth_error(exc):
                self._mark_reauth_required(
                    f"Spotify rejected the cached authorization: {exc}"
                )
            else:
                self._mark_retryable(
                    f"Spotify initialization failed and will be retried: {exc}"
                )

    def _get_cached_token(self):
        if not self.auth_manager:
            return None

        cache_handler = getattr(self.auth_manager, "cache_handler", None)
        if cache_handler and hasattr(cache_handler, "get_cached_token"):
            return cache_handler.get_cached_token()
        if hasattr(self.auth_manager, "get_cached_token"):
            return self.auth_manager.get_cached_token()
        return None

    def _get_access_token(self):
        try:
            return self.auth_manager.get_access_token(as_dict=False)
        except TypeError:
            return self.auth_manager.get_access_token()

    def _mark_ready(self):
        self.state = self.STATE_READY
        self.retry_attempts = 0
        self.next_retry_at = 0.0
        self.last_error = None

    def _mark_retryable(self, message):
        self.state = self.STATE_RETRYABLE
        self.last_error = str(message)
        self.retry_attempts = min(self.retry_attempts + 1, 6)
        delay = min(
            self.MAX_RETRY_DELAY_SECONDS,
            self.INITIAL_RETRY_DELAY_SECONDS * (2 ** (self.retry_attempts - 1)),
        )
        self.next_retry_at = time.time() + delay
        logger.warning("%s Retrying in %s seconds.", message, delay)

    def _mark_reauth_required(self, message):
        self.state = self.STATE_REAUTH_REQUIRED
        self.last_error = str(message)
        self.next_retry_at = 0.0
        self.sp = None
        logger.warning("%s Run src/authenticate_spotify.py to authorize Spotify again.", message)

    @staticmethod
    def _is_reauth_error(exc):
        message = str(exc).lower()
        return any(marker in message for marker in (
            "invalid_grant",
            "invalid_client",
            "invalid client",
            "refresh token revoked",
            "refresh token is invalid",
            "invalid refresh token",
        ))

    def get_state(self):
        return self.state

    def is_authenticated(self):
        """Checks if the client is currently considered authenticated and usable."""
        return self.state == self.STATE_READY and self.sp is not None

    def should_retry(self):
        return self.state == self.STATE_RETRYABLE

    # Removed get_auth_url method - this is now handled by authenticate_spotify.py

    def get_current_track(self):
        """Fetches the currently playing track from Spotify."""
        if self.state == self.STATE_REAUTH_REQUIRED:
            return None

        if self.state == self.STATE_RETRYABLE:
            if time.time() < self.next_retry_at:
                return None
            if self.sp is None:
                self._authenticate()
                if not self.is_authenticated():
                    return None

        try:
            track_info = self.sp.current_playback()
            self._mark_ready()
            if track_info and track_info.get("item"):
                return track_info
            return None
        except spotipy.exceptions.SpotifyException as exc:
            logger.error("Spotify API error when fetching current track: %s", exc)
            if getattr(exc, "http_status", None) == 401:
                return self._refresh_and_retry_current_track()
            if self._is_reauth_error(exc):
                self._mark_reauth_required(f"Spotify authorization was rejected: {exc}")
            else:
                self._mark_retryable(f"Spotify API request failed: {exc}")
            return None
        except Exception as exc:
            if self._is_reauth_error(exc):
                self._mark_reauth_required(f"Spotify authorization was rejected: {exc}")
            else:
                self._mark_retryable(f"Unexpected Spotify request failure: {exc}")
            return None

    def _refresh_and_retry_current_track(self):
        token_info = self._get_cached_token()
        refresh_token = token_info.get("refresh_token") if token_info else None
        if not refresh_token:
            self._mark_reauth_required(
                "Spotify returned 401 and no refresh token is available."
            )
            return None

        try:
            self.auth_manager.refresh_access_token(refresh_token)
            ensure_spotify_cache_access(SPOTIFY_AUTH_CACHE_PATH, logger=logger)
            log_spotify_cache_diagnostics(SPOTIFY_AUTH_CACHE_PATH, logger=logger)
            track_info = self.sp.current_playback()
            self._mark_ready()
            if track_info and track_info.get("item"):
                return track_info
            return None
        except spotipy.exceptions.SpotifyException as exc:
            if getattr(exc, "http_status", None) == 401 or self._is_reauth_error(exc):
                self._mark_reauth_required(
                    f"Spotify refresh was rejected: {exc}"
                )
            else:
                self._mark_retryable(f"Spotify refresh retry failed: {exc}")
            return None
        except Exception as exc:
            if self._is_reauth_error(exc):
                self._mark_reauth_required(f"Spotify refresh was rejected: {exc}")
            else:
                self._mark_retryable(f"Spotify refresh failed: {exc}")
            return None

# Example Usage (for testing, adapt to new auth flow)
# if __name__ == '__main__':
#     # First, ensure you have run authenticate_spotify.py successfully as the user.
#     client = SpotifyClient()
#     if client.is_authenticated():
#         print("Spotify client is authenticated.")
#         track = client.get_current_track()
#         if track:
#             print(json.dumps(track, indent=2))
#         else:
#             print("No track currently playing or error fetching.")
#     else:
#         print("Spotify client not authenticated. Please run src/authenticate_spotify.py as the correct user.") 
