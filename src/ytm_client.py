import socketio
import logging
import json
import os
import time
import threading
import requests # Added for HTTP requests during auth

# Ensure application-level logging is configured (as it is)
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Reduce verbosity of socketio and engineio libraries
logging.getLogger('socketio.client').setLevel(logging.WARNING)
logging.getLogger('socketio.server').setLevel(logging.WARNING)
logging.getLogger('engineio.client').setLevel(logging.WARNING)
logging.getLogger('engineio.server').setLevel(logging.WARNING)

# Define paths relative to this file's location
CONFIG_DIR = os.path.join(os.path.dirname(__file__), '..', 'config')
CONFIG_PATH = os.path.join(CONFIG_DIR, 'config.json')
# Resolve to an absolute path
CONFIG_PATH = os.path.abspath(CONFIG_PATH)

# Path for the separate YTM authentication token file
YTM_AUTH_CONFIG_PATH = os.path.join(CONFIG_DIR, 'ytm_auth.json')
YTM_AUTH_CONFIG_PATH = os.path.abspath(YTM_AUTH_CONFIG_PATH)

# YTM Companion App Constants
YTM_APP_ID = "ledmatrixcontroller"
YTM_APP_NAME = "LEDMatrixController"
YTM_APP_VERSION = "1.0.0"

class YTMClient:
    def __init__(self):
        self.base_url = None
        self.ytm_token = None # To store the auth token
        self.load_config() # This will now load URL from main config and token from ytm_auth.json
        # Explicitly disable internal loggers, rely on global config above
        self.sio = socketio.Client(logger=False, engineio_logger=False)
        self.last_known_track_data = None
        self.is_connected = False
        self._data_lock = threading.Lock()
        self._connection_event = threading.Event()

        @self.sio.event(namespace='/api/v1/realtime')
        def connect():
            logging.info(f"Successfully connected to YTM Companion Socket.IO server at {self.base_url} on namespace /api/v1/realtime")
            self.is_connected = True
            self._connection_event.set()

        @self.sio.event(namespace='/api/v1/realtime')
        def connect_error(data):
            logging.error(f"YTM Companion Socket.IO connection failed for namespace /api/v1/realtime: {data}")
            self.is_connected = False
            self._connection_event.set()

        @self.sio.event(namespace='/api/v1/realtime')
        def disconnect():
            logging.info(f"Disconnected from YTM Companion Socket.IO server at {self.base_url} on namespace /api/v1/realtime")
            self.is_connected = False

        @self.sio.on('ytm_track_update', namespace='/api/v1/realtime')
        def on_track_update(data):
            logging.debug(f"Received track update from YTM Companion on /api/v1/realtime: {data}")
            with self._data_lock:
                self.last_known_track_data = data

    def load_config(self):
        default_url = "http://localhost:9863"
        loaded_config = {} # To store the whole config for saving later
        
        # Load base_url from main config.json
        if not os.path.exists(CONFIG_PATH):
            logging.error(f"Main config file not found at {CONFIG_PATH}")
            # We can still try to load a token if ytm_auth.json exists
            # and use default URL
        else:
            try:
                with open(CONFIG_PATH, 'r') as f:
                    loaded_config = json.load(f)
                    music_config = loaded_config.get("music", {})
                    self.base_url = music_config.get("YTM_COMPANION_URL", default_url)
                    if not self.base_url:
                        logging.warning("YTM_COMPANION_URL missing or empty in config.json music section, using default.")
                        self.base_url = default_url
            except json.JSONDecodeError:
                logging.error(f"Error decoding JSON from main config {CONFIG_PATH}")
            except Exception as e:
                logging.error(f"Error loading YTM_COMPANION_URL from main config {CONFIG_PATH}: {e}")

        if not self.base_url: # If main config was missing or URL not found
            self.base_url = default_url
            logging.warning(f"Using default YTM URL: {self.base_url}")

        # Load ytm_token from ytm_auth.json
        self.ytm_token = None # Reset token before trying to load
        if os.path.exists(YTM_AUTH_CONFIG_PATH):
            try:
                with open(YTM_AUTH_CONFIG_PATH, 'r') as f:
                    auth_data = json.load(f)
                    self.ytm_token = auth_data.get("YTM_COMPANION_TOKEN")
            except json.JSONDecodeError:
                logging.error(f"Error decoding JSON from YTM auth file {YTM_AUTH_CONFIG_PATH}")
            except Exception as e:
                logging.error(f"Error loading YTM auth config {YTM_AUTH_CONFIG_PATH}: {e}")
        
        logging.info(f"YTM Companion URL set to: {self.base_url}")
        if self.ytm_token:
            logging.info(f"YTM Companion token loaded from {YTM_AUTH_CONFIG_PATH}.")
        else:
            logging.info(f"No YTM Companion token found in {YTM_AUTH_CONFIG_PATH}. Will attempt to register.")

        if self.base_url and self.base_url.startswith("ws://"):
            self.base_url = "http://" + self.base_url[5:]
        elif self.base_url and self.base_url.startswith("wss://"):
            self.base_url = "https://" + self.base_url[6:]
        
        # Store the loaded config for potential saving later
        self._loaded_config_data = loaded_config # Still keep main config data if needed elsewhere, but not for token saving

    def _save_ytm_token(self):
        """Saves the YTM token to ytm_auth.json."""
        if not self.ytm_token:
            logging.warning("No YTM token to save.")
            return

        if not os.path.exists(CONFIG_DIR):
            try:
                os.makedirs(CONFIG_DIR)
                logging.info(f"Created config directory: {CONFIG_DIR}")
            except OSError as e:
                logging.error(f"Could not create config directory {CONFIG_DIR}: {e}")
                return

        token_data = {"YTM_COMPANION_TOKEN": self.ytm_token}

        try:
            with open(YTM_AUTH_CONFIG_PATH, 'w') as f:
                json.dump(token_data, f, indent=4)
            logging.info(f"YTM Companion token saved to {YTM_AUTH_CONFIG_PATH}")
        except Exception as e:
            logging.error(f"Error saving YTM token to {YTM_AUTH_CONFIG_PATH}: {e}")

    def _request_auth_code(self):
        """Requests an authentication code from the YTM Companion server."""
        url = f"{self.base_url}/api/v1/auth/requestcode"
        payload = {
            "appId": YTM_APP_ID,
            "appName": YTM_APP_NAME,
            "appVersion": YTM_APP_VERSION
        }
        try:
            logging.info(f"Requesting auth code from {url} with appId: {YTM_APP_ID}")
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status() # Raise an exception for HTTP errors (4XX, 5XX)
            data = response.json()
            logging.info(f"Received auth code: {data.get('code')}")
            return data.get('code')
        except requests.exceptions.RequestException as e:
            logging.error(f"Error requesting YTM auth code: {e}")
            return None
        except json.JSONDecodeError:
            logging.error("Error decoding JSON response when requesting auth code.")
            return None

    def _request_auth_token(self, code):
        """Requests an authentication token using the provided code."""
        if not code:
            return None
        url = f"{self.base_url}/api/v1/auth/request"
        payload = {
            "appId": YTM_APP_ID,
            "code": code
        }
        try:
            logging.info("Requesting auth token. PLEASE CHECK YOUR YTM DESKTOP APP TO APPROVE THIS REQUEST.")
            logging.info("You have 30 seconds to approve in the YTM Desktop App.")
            # The API docs say this can take up to 30 seconds due to user interaction
            response = requests.post(url, json=payload, timeout=35) 
            response.raise_for_status()
            data = response.json()
            token = data.get('token')
            if token:
                logging.info("Successfully received YTM auth token.")
            else:
                logging.warning("Auth token not found in response.")
            return token
        except requests.exceptions.Timeout:
            logging.error("Timeout waiting for YTM auth token. Did you approve the request in YTM Desktop App?")
            return None
        except requests.exceptions.RequestException as e:
            logging.error(f"Error requesting YTM auth token: {e}")
            return None
        except json.JSONDecodeError:
            logging.error("Error decoding JSON response when requesting auth token.")
            return None

    def _perform_initial_authentication(self):
        """Performs the full authentication flow if no token is present."""
        if self.ytm_token:
            logging.info("Token already loaded. Skipping initial authentication.")
            return True

        logging.info("Attempting to perform initial YTM authentication...")
        code = self._request_auth_code()
        if not code:
            logging.error("Failed to get YTM auth code. Cannot proceed with authentication.")
            return False
        
        token = self._request_auth_token(code)
        if token:
            self.ytm_token = token
            self._save_ytm_token() # Save the new token to ytm_auth.json
            return True
        else:
            logging.error("Failed to get YTM auth token.")
            return False

    def _ensure_connected(self, timeout=5):
        if not self.ytm_token: # Check for token first
            if not self._perform_initial_authentication():
                logging.warning("YTM authentication failed. Cannot connect to Socket.IO.")
                self.is_connected = False
                return False
            # After successful auth, ytm_token should be set

        if not self.is_connected:
            logging.info(f"Attempting to connect to YTM Socket.IO server: {self.base_url} on namespace /api/v1/realtime")
            auth_payload = None
            if self.ytm_token:
                auth_payload = {"token": self.ytm_token}
            else:
                # This case should ideally not be reached if _perform_initial_authentication was called and failed
                logging.error("No YTM token available for Socket.IO connection after auth attempt. This should not happen.")
                self.is_connected = False
                return False

            try:
                self.sio.connect(
                    self.base_url, 
                    transports=['websocket'], 
                    wait_timeout=timeout, 
                    namespaces=['/api/v1/realtime'],
                    auth=auth_payload
                )
                self._connection_event.clear()
                if not self._connection_event.wait(timeout=timeout):
                    logging.warning(f"YTM Socket.IO connection attempt timed out after {timeout}s.")
                    return False
                return self.is_connected
            except socketio.exceptions.ConnectionError as e:
                logging.error(f"YTM Socket.IO connection error: {e}")
                self.is_connected = False
                return False
            except Exception as e:
                logging.error(f"Unexpected error during YTM Socket.IO connection: {e}")
                self.is_connected = False
                return False
        return True

    def is_available(self):
        if not self.is_connected:
            # Increase timeout for initial availability check to allow connection to establish
            return self._ensure_connected(timeout=10) 
        return True

    def get_current_track(self):
        if not self._ensure_connected():
            logging.warning("YTM client not connected, cannot get current track.")
            return None

        with self._data_lock:
            if self.last_known_track_data:
                return self.last_known_track_data
            else:
                logging.debug("No track data received yet from YTM Companion Socket.IO.")
                return None

    def disconnect_client(self):
        if self.is_connected:
            self.sio.disconnect()
            logging.info("YTM Socket.IO client disconnected.")

# Example Usage (for testing - needs to be adapted for Socket.IO async nature)
# if __name__ == '__main__':
# client = YTMClient()
# if client.connect_client(): # Assuming connect_client is the new public method to initiate
# print("YTM Server is available (Socket.IO).")
# try:
# for _ in range(10): # Poll for a few seconds
# track = client.get_current_track()
# if track:
# print(json.dumps(track, indent=2))
# else:
# print("No track currently playing or error fetching (Socket.IO).")
# time.sleep(2)
# finally:
# client.disconnect_client()
# else:
# print(f"YTM Server not available at {client.base_url} (Socket.IO). Is YTMD running with companion server enabled?")

# It's important to note that a long-running application would typically
# keep the socketio client running in a background thread if sio.wait() is used,
# or integrate with an asyncio event loop. The above __main__ is simplified.
# The MusicManager's polling thread will interact with this client. 