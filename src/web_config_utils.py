from collections.abc import Mapping, MutableMapping
import copy
import json
from typing import Any, Optional


DEFAULT_SPOTIFY_REDIRECT_URI = "http://127.0.0.1:8888/callback"


def merge_dict(target: MutableMapping[str, Any], source: Mapping[str, Any]) -> MutableMapping[str, Any]:
    """Deep merge source into target, copying leaf values."""
    for key, value in source.items():
        if key in target and isinstance(target[key], dict) and isinstance(value, Mapping):
            merge_dict(target[key], value)
        else:
            target[key] = copy.deepcopy(value)
    return target


def apply_config_fragment(existing_config: Mapping[str, Any], config_data_str: Optional[str]) -> dict:
    """Return a merged config after applying a JSON fragment payload."""
    updated_config = copy.deepcopy(existing_config)
    if not config_data_str:
        return updated_config

    new_data = json.loads(config_data_str)
    if not isinstance(new_data, dict):
        raise ValueError("Config data must be a JSON object.")

    merge_dict(updated_config, new_data)
    return updated_config


def build_secrets_fragment_from_form(form_data: Mapping[str, Any]) -> dict:
    """Build a secrets fragment from the v1/v2 form field names."""
    fragment = {}

    if "weather_api_key" in form_data:
        fragment["weather"] = {
            "api_key": form_data.get("weather_api_key", "")
        }

    if "youtube_api_key" in form_data or "youtube_channel_id" in form_data:
        youtube_fragment = {}
        if "youtube_api_key" in form_data:
            youtube_fragment["api_key"] = form_data.get("youtube_api_key", "")
        if "youtube_channel_id" in form_data:
            youtube_fragment["channel_id"] = form_data.get("youtube_channel_id", "")
        fragment["youtube"] = youtube_fragment

    spotify_fields = {"spotify_client_id", "spotify_client_secret", "spotify_redirect_uri"}
    if any(field in form_data for field in spotify_fields):
        music_fragment = {}
        if "spotify_client_id" in form_data:
            music_fragment["SPOTIFY_CLIENT_ID"] = form_data.get("spotify_client_id", "")
        if "spotify_client_secret" in form_data:
            music_fragment["SPOTIFY_CLIENT_SECRET"] = form_data.get("spotify_client_secret", "")
        music_fragment["SPOTIFY_REDIRECT_URI"] = form_data.get(
            "spotify_redirect_uri",
            DEFAULT_SPOTIFY_REDIRECT_URI,
        )
        fragment["music"] = music_fragment

    return fragment


def apply_secrets_update(
    existing_secrets: Optional[Mapping[str, Any]] = None,
    config_data_str: Optional[str] = None,
    form_data: Optional[Mapping[str, Any]] = None,
) -> dict:
    """Return merged secrets after applying a JSON fragment and/or direct form fields."""
    updated_secrets = copy.deepcopy(existing_secrets) if existing_secrets else {}

    if config_data_str:
        new_data = json.loads(config_data_str)
        if not isinstance(new_data, dict):
            raise ValueError("Secrets config data must be a JSON object.")
        merge_dict(updated_secrets, new_data)

    if form_data:
        form_fragment = build_secrets_fragment_from_form(form_data)
        if form_fragment:
            merge_dict(updated_secrets, form_fragment)

    return updated_secrets
