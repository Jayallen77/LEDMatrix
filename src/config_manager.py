import json
import os
from typing import Dict, Any

class ConfigManager:
    def __init__(self, config_path: str = None, secrets_path: str = None):
        # Use current working directory as base
        self.config_path = config_path or "config/config.json"
        self.secrets_path = secrets_path or "config/config_secrets.json"
        self.config: Dict[str, Any] = {}

    def load_config(self) -> Dict[str, Any]:
        """Load configuration from JSON files."""
        try:
            # Load main config
            print(f"Attempting to load config from: {os.path.abspath(self.config_path)}")
            with open(self.config_path, 'r') as f:
                self.config = json.load(f)

            # Load and merge secrets if they exist
            if os.path.exists(self.secrets_path):
                with open(self.secrets_path, 'r') as f:
                    secrets = json.load(f)
                    # Deep merge secrets into config
                    self._deep_merge(self.config, secrets)
            
            return self.config
            
        except FileNotFoundError as e:
            if str(e).find('config_secrets.json') == -1:  # Only raise if main config is missing
                print(f"Configuration file not found at {os.path.abspath(self.config_path)}")
                raise
            return self.config
        except json.JSONDecodeError:
            print("Error parsing configuration file")
            raise
        except Exception as e:
            print(f"Error loading configuration: {str(e)}")
            raise

    def save_config(self, config_data: Dict[str, Any]) -> None:
        """Save configuration to the main JSON file."""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(config_data, f, indent=4)
            self.config = config_data  # Update the in-memory config
            print(f"Configuration successfully saved to {os.path.abspath(self.config_path)}")
        except IOError as e:
            print(f"Error writing configuration to file {os.path.abspath(self.config_path)}: {e}")
            raise
        except Exception as e:
            print(f"An unexpected error occurred while saving configuration: {str(e)}")
            raise

    def _deep_merge(self, target: Dict, source: Dict) -> None:
        """Deep merge source dict into target dict."""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._deep_merge(target[key], value)
            else:
                target[key] = value

    def get_timezone(self) -> str:
        """Get the configured timezone."""
        return self.config.get('timezone', 'UTC')

    def get_display_config(self) -> Dict[str, Any]:
        """Get display configuration."""
        return self.config.get('display', {})

    def get_clock_config(self) -> Dict[str, Any]:
        """Get clock configuration."""
        return self.config.get('clock', {}) 