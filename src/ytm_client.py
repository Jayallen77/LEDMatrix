import requests
import logging
import json
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Define paths relative to this file's location
CONFIG_DIR = os.path.join(os.path.dirname(__file__), '..', 'config')
CONFIG_PATH = os.path.join(CONFIG_DIR, 'config.json')

class YTMClient:
    def __init__(self):
        self.base_url = None
        self.load_config()

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

    def _make_request(self, endpoint):
        """Helper method to make requests to the companion server."""
        if not self.base_url:
            logging.error("YTM base URL not configured.")
            return None
        try:
            url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
            response = requests.get(url, timeout=1) # Short timeout
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            return response.json()
        except requests.exceptions.ConnectionError:
            # This is expected if the server isn't running
            logging.debug(f"Could not connect to YTM Companion server at {self.base_url}")
            return None
        except requests.exceptions.Timeout:
            logging.warning(f"Timeout connecting to YTM Companion server at {self.base_url}")
            return None
        except requests.exceptions.RequestException as e:
            logging.error(f"Error requesting {endpoint} from YTM: {e}")
            return None

    def is_available(self):
        """Checks if the YTM companion server is reachable."""
        # Use a lightweight endpoint if available, otherwise try main query
        # For now, just try the main query endpoint
        return self._make_request('/query') is not None

    def get_current_track(self):
        """Fetches the currently playing track from the YTM companion server."""
        data = self._make_request('/query')
        # Add more specific error handling or data validation if needed
        if data and 'track' in data and 'player' in data:
            return data
        else:
            logging.debug("Received no or incomplete data from YTM /query")
            return None

# Example Usage (for testing)
# if __name__ == '__main__':
#     client = YTMClient()
#     if client.is_available():
#         print("YTM Server is available.")
#         track = client.get_current_track()
#         if track:
#             print(json.dumps(track, indent=2))
#         else:
#             print("No track currently playing or error fetching.")
#     else:
#         print(f"YTM Server not available at {client.base_url}. Is YTMD running with companion server enabled?") 