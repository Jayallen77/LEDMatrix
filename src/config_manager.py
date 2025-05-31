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

    def _strip_secrets_recursive(self, data_to_filter: Dict[str, Any], secrets: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively remove secret keys from a dictionary."""
        result = {}
        for key, value in data_to_filter.items():
            if key in secrets:
                if isinstance(value, dict) and isinstance(secrets[key], dict):
                    # This key is a shared group, recurse
                    stripped_sub_dict = self._strip_secrets_recursive(value, secrets[key])
                    if stripped_sub_dict: # Only add if there's non-secret data left
                        result[key] = stripped_sub_dict
                # Else, it's a secret key at this level, so we skip it
            else:
                # This key is not in secrets, so we keep it
                result[key] = value
        return result

    def save_config(self, new_config_data: Dict[str, Any]) -> None:
        """Save configuration to the main JSON file, stripping out secrets."""
        secrets_content = {}
        if os.path.exists(self.secrets_path):
            try:
                with open(self.secrets_path, 'r') as f_secrets:
                    secrets_content = json.load(f_secrets)
            except Exception as e:
                print(f"Warning: Could not load secrets file {self.secrets_path} during save: {e}")
                # Continue without stripping if secrets can't be loaded, or handle as critical error
                # For now, we'll proceed cautiously and save the full new_config_data if secrets are unreadable
                # to prevent accidental data loss if the secrets file is temporarily corrupt.
                # A more robust approach might be to fail the save or use a cached version of secrets.

        config_to_write = self._strip_secrets_recursive(new_config_data, secrets_content)

        try:
            with open(self.config_path, 'w') as f:
                json.dump(config_to_write, f, indent=4)
            
            # Update the in-memory config to the new state (which includes secrets for runtime)
            self.config = new_config_data 
            print(f"Configuration successfully saved to {os.path.abspath(self.config_path)}")
            if secrets_content:
                 print("Secret values were preserved in memory and not written to the main config file.")

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