import socketio
import logging
import json
import os
import time
import threading

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Define paths relative to this file's location
CONFIG_DIR = os.path.join(os.path.dirname(__file__), '..', 'config')
CONFIG_PATH = os.path.join(CONFIG_DIR, 'config.json')

class YTMClient:
    def __init__(self):
        self.base_url = None
        self.load_config()
        self.sio = socketio.Client(logger=True, engineio_logger=False)
        self.last_known_track_data = None
        self.is_connected = False
        self._data_lock = threading.Lock()
        self._connection_event = threading.Event()

        @self.sio.event
        def connect():
            logging.info(f"Successfully connected to YTM Companion Socket.IO server at {self.base_url}")
            self.is_connected = True
            self._connection_event.set()

        @self.sio.event
        def connect_error(data):
            logging.error(f"YTM Companion Socket.IO connection failed: {data}")
            self.is_connected = False
            self._connection_event.set()

        @self.sio.event
        def disconnect():
            logging.info(f"Disconnected from YTM Companion Socket.IO server at {self.base_url}")
            self.is_connected = False

        @self.sio.on('ytm_track_update')
        def on_track_update(data):
            logging.debug(f"Received track update from YTM Companion: {data}")
            with self._data_lock:
                self.last_known_track_data = data

    def load_config(self):
        default_url = "http://localhost:9863"
        if not os.path.exists(CONFIG_PATH):
            logging.error(f"Config file not found at {CONFIG_PATH}")
            self.base_url = default_url
            logging.warning(f"Using default YTM URL: {self.base_url}")
            return

        try:
            with open(CONFIG_PATH, 'r') as f:
                config_data = json.load(f)
                music_config = config_data.get("music", {})
                self.base_url = music_config.get("YTM_COMPANION_URL", default_url)
                if not self.base_url:
                     logging.warning("YTM_COMPANION_URL missing or empty in config.json music section, using default.")
                     self.base_url = default_url
        except json.JSONDecodeError:
            logging.error(f"Error decoding JSON from {CONFIG_PATH}")
            self.base_url = default_url
        except Exception as e:
            logging.error(f"Error loading YTM config: {e}")
            self.base_url = default_url
        logging.info(f"YTM Companion URL set to: {self.base_url}")
        if self.base_url and self.base_url.startswith("ws://"):
            self.base_url = "http://" + self.base_url[5:]
        elif self.base_url and self.base_url.startswith("wss://"):
            self.base_url = "https://" + self.base_url[6:]

    def _ensure_connected(self, timeout=5):
        if not self.is_connected:
            logging.info(f"Attempting to connect to YTM Socket.IO server: {self.base_url}")
            try:
                self.sio.connect(self.base_url, transports=['websocket'], wait_timeout=timeout)
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
            return self._ensure_connected(timeout=2)
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