import requests
import json
import time
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Any
try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:
    # Fallback for Python < 3.9 (requires pytz install: pip install pytz)
    from pytz import timezone as ZoneInfo, UnknownTimeZoneError as ZoneInfoNotFoundError

# --- Get Project Root --- 
# Assuming the script is in /path/to/project/src/
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent

# --- Constants ---
CONFIG_FILE = PROJECT_ROOT / "config" / "config.json" # Absolute path
# Default values in case config loading fails
DEFAULT_DISPLAY_WIDTH = 64
DEFAULT_DISPLAY_HEIGHT = 32
DEFAULT_NHL_ENABLED = False
DEFAULT_FAVORITE_TEAMS = []
DEFAULT_NHL_TEST_MODE = False
DEFAULT_UPDATE_INTERVAL = 60
DEFAULT_IDLE_UPDATE_INTERVAL = 3600 # Default 1 hour (was 300)
DEFAULT_CYCLE_GAME_DURATION = 10 # Cycle duration for multiple live games
DEFAULT_LOGO_DIR = PROJECT_ROOT / "assets" / "sports" / "nhl_logos" # Absolute path
DEFAULT_TEST_DATA_FILE = PROJECT_ROOT / "test_nhl_data.json" # Absolute path
DEFAULT_OUTPUT_IMAGE_FILE = PROJECT_ROOT / "nhl_scorebug_output.png" # Absolute path
DEFAULT_TIMEZONE = "UTC"
DEFAULT_NHL_SHOW_ONLY_FAVORITES = False
RECENT_GAME_HOURS = 48 # Updated lookback window

ESPN_NHL_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard"

# --- Global Config Variables ---
# These will be populated by load_config()
DISPLAY_WIDTH = DEFAULT_DISPLAY_WIDTH
DISPLAY_HEIGHT = DEFAULT_DISPLAY_HEIGHT
NHL_ENABLED = DEFAULT_NHL_ENABLED
FAVORITE_TEAMS = DEFAULT_FAVORITE_TEAMS
TEST_MODE = DEFAULT_NHL_TEST_MODE
UPDATE_INTERVAL_SECONDS = DEFAULT_UPDATE_INTERVAL
IDLE_UPDATE_INTERVAL_SECONDS = DEFAULT_IDLE_UPDATE_INTERVAL
LOGO_DIR = DEFAULT_LOGO_DIR
TEST_DATA_FILE = DEFAULT_TEST_DATA_FILE
OUTPUT_IMAGE_FILE = DEFAULT_OUTPUT_IMAGE_FILE
LOCAL_TIMEZONE = None # Will be ZoneInfo object
SHOW_ONLY_FAVORITES = DEFAULT_NHL_SHOW_ONLY_FAVORITES

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Configuration Loading ---
def load_config():
    """Loads configuration from config.json."""
    global DISPLAY_WIDTH, DISPLAY_HEIGHT, NHL_ENABLED, FAVORITE_TEAMS, TEST_MODE, UPDATE_INTERVAL_SECONDS, IDLE_UPDATE_INTERVAL_SECONDS, LOGO_DIR, TEST_DATA_FILE, OUTPUT_IMAGE_FILE, LOCAL_TIMEZONE, SHOW_ONLY_FAVORITES

    try:
        with open(CONFIG_FILE, 'r') as f:
            config_data = json.load(f)

        # Read display dimensions from the 'display' -> 'hardware' section
        display_config = config_data.get("display", {})
        hardware_config = display_config.get("hardware", {})
        # Calculate total width: cols * chain_length
        cols = hardware_config.get("cols", DEFAULT_DISPLAY_WIDTH / hardware_config.get("chain_length", 1) if hardware_config.get("chain_length") else DEFAULT_DISPLAY_WIDTH) # Default handling needs care
        chain = hardware_config.get("chain_length", 1)
        DISPLAY_WIDTH = int(cols * chain) # Ensure integer
        DISPLAY_HEIGHT = hardware_config.get("rows", DEFAULT_DISPLAY_HEIGHT)

        # Load timezone
        tz_string = config_data.get("timezone", DEFAULT_TIMEZONE)
        try:
            LOCAL_TIMEZONE = ZoneInfo(tz_string)
            logging.info(f"Timezone loaded: {tz_string}")
        except ZoneInfoNotFoundError:
            logging.warning(f"Timezone '{tz_string}' not found. Defaulting to {DEFAULT_TIMEZONE}.")
            LOCAL_TIMEZONE = ZoneInfo(DEFAULT_TIMEZONE)

        nhl_config = config_data.get("nhl_scoreboard", {})
        NHL_ENABLED = nhl_config.get("enabled", DEFAULT_NHL_ENABLED)
        FAVORITE_TEAMS = nhl_config.get("favorite_teams", DEFAULT_FAVORITE_TEAMS)
        TEST_MODE = nhl_config.get("test_mode", DEFAULT_NHL_TEST_MODE)
        UPDATE_INTERVAL_SECONDS = nhl_config.get("update_interval_seconds", DEFAULT_UPDATE_INTERVAL)
        IDLE_UPDATE_INTERVAL_SECONDS = nhl_config.get("idle_update_interval_seconds", DEFAULT_IDLE_UPDATE_INTERVAL)
        SHOW_ONLY_FAVORITES = nhl_config.get("show_only_favorites", DEFAULT_NHL_SHOW_ONLY_FAVORITES)

        logging.info("Configuration loaded successfully.")
        logging.info(f"Display: {DISPLAY_WIDTH}x{DISPLAY_HEIGHT}")
        logging.info(f"NHL Enabled: {NHL_ENABLED}")
        logging.info(f"Favorite Teams: {FAVORITE_TEAMS}")
        logging.info(f"Test Mode: {TEST_MODE}")
        logging.info(f"Update Interval: {UPDATE_INTERVAL_SECONDS}s (Active), {IDLE_UPDATE_INTERVAL_SECONDS}s (Idle)")
        logging.info(f"Show Only Favorites: {SHOW_ONLY_FAVORITES}")

    except FileNotFoundError:
        logging.warning(f"Configuration file {CONFIG_FILE} not found. Using default settings.")
    except json.JSONDecodeError:
        logging.error(f"Error decoding configuration file {CONFIG_FILE.name}. Using default settings.") # Use .name
    except Exception as e:
        logging.error(f"An unexpected error occurred loading config: {e}. Using default settings.")

# --- Display Simulation (Uses global config) ---
# (Keep existing function, it now uses global width/height)

# --- Helper Functions ---

def get_espn_data():
    """Fetches scoreboard data from ESPN API or loads test data."""
    try:
        response = requests.get(ESPN_NHL_SCOREBOARD_URL)
        response.raise_for_status()  # Raise an exception for bad status codes
        data = response.json()
        logging.info("Successfully fetched live data from ESPN.")
        # Save live data for testing if needed
        if TEST_MODE:
             # Ensure TEST_DATA_FILE is used
             with open(TEST_DATA_FILE, 'w') as f:
                 json.dump(data, f, indent=2)
             logging.info(f"Saved live data to {TEST_DATA_FILE.name}") # Use .name for logging
        return data
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching data from ESPN: {e}")
        if TEST_MODE:
            logging.warning("Fetching failed, attempting to load test data.")
            try:
                # Ensure TEST_DATA_FILE is used
                with open(TEST_DATA_FILE, 'r') as f:
                    data = json.load(f)
                    logging.info(f"Successfully loaded test data from {TEST_DATA_FILE.name}")
                    return data
            except FileNotFoundError:
                logging.error(f"Test data file {TEST_DATA_FILE.name} not found.")
                return None
            except json.JSONDecodeError:
                logging.error(f"Error decoding test data file {TEST_DATA_FILE.name}.")
                return None
        return None

def find_favorite_game(data):
    """Finds the first game involving a favorite team."""
    if not data or "events" not in data:
        return None

    for event in data["events"]:
        competitions = event.get("competitions", [])
        if not competitions:
            continue
        competition = competitions[0]
        competitors = competition.get("competitors", [])
        if len(competitors) == 2:
            team1_abbr = competitors[0].get("team", {}).get("abbreviation")
            team2_abbr = competitors[1].get("team", {}).get("abbreviation")
            if team1_abbr in FAVORITE_TEAMS or team2_abbr in FAVORITE_TEAMS:
                logging.info(f"Found favorite game: {team1_abbr} vs {team2_abbr}")
                return event # Return the whole event data
    logging.info("No games involving favorite teams found.")
    return None

def find_relevant_favorite_event(data):
    """Finds the most relevant game for favorite teams: Live > Recent Final > Next Upcoming."""
    if not data or "events" not in data:
        return None

    live_event = None
    recent_final_event = None
    next_upcoming_event = None

    now_utc = datetime.now(timezone.utc)
    cutoff_time_utc = now_utc - timedelta(hours=RECENT_GAME_HOURS)

    for event in data["events"]:
        competitions = event.get("competitions", [])
        if not competitions:
            continue
        competition = competitions[0]
        competitors = competition.get("competitors", [])
        if len(competitors) == 2:
            team1_abbr = competitors[0].get("team", {}).get("abbreviation")
            team2_abbr = competitors[1].get("team", {}).get("abbreviation")

            is_favorite = team1_abbr in FAVORITE_TEAMS or team2_abbr in FAVORITE_TEAMS

            if is_favorite:
                details = extract_game_details(event) # Use extract to get parsed date and states
                if not details or not details["start_time_utc"]:
                    continue # Skip if details couldn't be parsed

                # --- Check Categories (Priority Order) ---

                # 1. Live Game?
                if details["is_live"]:
                    logging.debug(f"Found live favorite game: {team1_abbr} vs {team2_abbr}")
                    live_event = event
                    break # Found the highest priority, no need to check further

                # 2. Recent Final?
                if details["is_final"] and details["start_time_utc"] > cutoff_time_utc:
                    # Keep the *most* recent final game
                    if recent_final_event is None or details["start_time_utc"] > extract_game_details(recent_final_event)["start_time_utc"]:
                         logging.debug(f"Found potential recent final: {team1_abbr} vs {team2_abbr}")
                         recent_final_event = event

                # 3. Upcoming Game?
                if details["is_upcoming"] and details["start_time_utc"] > now_utc:
                    # Keep the *soonest* upcoming game
                    if next_upcoming_event is None or details["start_time_utc"] < extract_game_details(next_upcoming_event)["start_time_utc"]:
                        logging.debug(f"Found potential upcoming game: {team1_abbr} vs {team2_abbr}")
                        next_upcoming_event = event

    # Return the highest priority event found
    if live_event:
        logging.info("Displaying live favorite game.")
        return live_event
    elif recent_final_event:
        logging.info("Displaying recent final favorite game.")
        return recent_final_event
    elif next_upcoming_event:
        logging.info("Displaying next upcoming favorite game.")
        return next_upcoming_event
    else:
        logging.info("No relevant (live, recent final, or upcoming) favorite games found.")
        return None

def extract_game_details(game_event):
    """Extracts relevant details for the score bug display."""
    if not game_event:
        return None

    details = {}
    try:
        competition = game_event["competitions"][0]
        status = competition["status"]
        competitors = competition["competitors"]
        game_date_str = game_event["date"] # ISO 8601 format (UTC)

        # Parse game date/time
        try:
            details["start_time_utc"] = datetime.fromisoformat(game_date_str.replace("Z", "+00:00"))
        except ValueError:
            logging.warning(f"Could not parse game date: {game_date_str}")
            details["start_time_utc"] = None

        home_team = next(c for c in competitors if c.get("homeAway") == "home")
        away_team = next(c for c in competitors if c.get("homeAway") == "away")

        details["status_text"] = status["type"]["shortDetail"] # e.g., "7:30 - 1st" or "Final"
        details["period"] = status.get("period", 0)
        details["clock"] = status.get("displayClock", "0:00")
        details["is_live"] = status["type"]["state"] in ("in", "halftime") # 'in' for ongoing
        details["is_final"] = status["type"]["state"] == "post"
        details["is_upcoming"] = status["type"]["state"] == "pre"

        details["home_abbr"] = home_team["team"]["abbreviation"]
        details["home_score"] = home_team.get("score", "0")
        details["home_logo_path"] = LOGO_DIR / f"{details['home_abbr']}.png"

        details["away_abbr"] = away_team["team"]["abbreviation"]
        details["away_score"] = away_team.get("score", "0")
        details["away_logo_path"] = LOGO_DIR / f"{details['away_abbr']}.png"

        # Check if logo files exist
        if not details["home_logo_path"].is_file():
             logging.warning(f"Home logo not found: {details['home_logo_path']}")
             details["home_logo_path"] = None
        if not details["away_logo_path"].is_file():
             logging.warning(f"Away logo not found: {details['away_logo_path']}")
             details["away_logo_path"] = None

        return details

    except (KeyError, IndexError, StopIteration) as e:
        logging.error(f"Error parsing game details: {e} - Data: {game_event}")
        return None

def create_scorebug_image(game_details):
    """Creates an image simulating the NHL score bug."""
    if not game_details:
        # Create a blank or placeholder image if no game data
        img = Image.new('RGB', (DISPLAY_WIDTH, DISPLAY_HEIGHT), color='black')
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("arial.ttf", 10) # Adjust font path/size
        except IOError:
            font = ImageFont.load_default()
        draw.text((5, 10), "No game data", font=font, fill='white')
        return img

    # --- Basic Layout ---
    # This is highly dependent on your desired look and display size.
    # Adjust positions, sizes, fonts accordingly.
    img = Image.new('RGB', (DISPLAY_WIDTH, DISPLAY_HEIGHT), color='black')
    draw = ImageDraw.Draw(img)

    try:
        # Use a common font or specify path if needed
        score_font = ImageFont.truetype("arial.ttf", 12)
        time_font = ImageFont.truetype("arial.ttf", 10)
        team_font = ImageFont.truetype("arial.ttf", 8)
        status_font = ImageFont.truetype("arial.ttf", 9) # For Final/Upcoming status
    except IOError:
        logging.warning("Arial font not found, using default.")
        score_font = ImageFont.load_default()
        time_font = ImageFont.load_default()
        team_font = ImageFont.load_default()


    # --- Element Positions (Example - Needs heavy tuning) ---
    away_logo_pos = (2, 2)
    away_score_pos = (36, 2) # Right of away logo
    home_logo_pos = (DISPLAY_WIDTH - 34, 2) # Positioned from the right
    home_score_pos = (DISPLAY_WIDTH - 34 - 25, 2) # Left of home logo

    time_pos = (DISPLAY_WIDTH // 2, 2) # Centered top
    period_pos = (DISPLAY_WIDTH // 2, 15) # Centered below time

    logo_size = (30, 30) # Max logo size

    # --- Draw Away Team ---
    if game_details["away_logo_path"]:
        try:
            away_logo_rgba = Image.open(game_details["away_logo_path"]).convert("RGBA")
            # Resize and reassign, instead of in-place thumbnail
            away_logo_rgba = away_logo_rgba.resize(logo_size, Image.Resampling.LANCZOS)

            paste_x = away_logo_pos[0]
            paste_y = (DISPLAY_HEIGHT - away_logo_rgba.height) // 2

            # Manual pixel paste (robust alternative)
            for x in range(away_logo_rgba.width):
                for y in range(away_logo_rgba.height):
                    r, g, b, a = away_logo_rgba.getpixel((x, y))
                    if a > 128: # Check alpha threshold
                        target_x = paste_x + x
                        target_y = paste_y + y
                        # Ensure target pixel is within image bounds
                        if 0 <= target_x < img.width and 0 <= target_y < img.height:
                            img.putpixel((target_x, target_y), (r, g, b))

        except Exception as e:
            logging.error(f"Error loading/pasting away logo {game_details['away_logo_path']}: {e}")
            # Draw placeholder text if logo fails
            draw.text(away_logo_pos, game_details["away_abbr"], font=team_font, fill="white")
    else:
        # Draw abbreviation if no logo path
        draw.text(away_logo_pos, game_details["away_abbr"], font=team_font, fill="white")

    draw.text(away_score_pos, str(game_details["away_score"]), font=score_font, fill='white')

    # --- Draw Home Team ---
    if game_details["home_logo_path"]:
         try:
            home_logo_rgba = Image.open(game_details["home_logo_path"]).convert("RGBA")
            # Resize and reassign, instead of in-place thumbnail
            home_logo_rgba = home_logo_rgba.resize(logo_size, Image.Resampling.LANCZOS)

            paste_x = home_logo_pos[0]
            paste_y = (DISPLAY_HEIGHT - home_logo_rgba.height) // 2

            # Manual pixel paste (robust alternative)
            for x in range(home_logo_rgba.width):
                for y in range(home_logo_rgba.height):
                    r, g, b, a = home_logo_rgba.getpixel((x, y))
                    if a > 128: # Check alpha threshold
                        target_x = paste_x + x
                        target_y = paste_y + y
                        # Ensure target pixel is within image bounds
                        if 0 <= target_x < img.width and 0 <= target_y < img.height:
                            img.putpixel((target_x, target_y), (r, g, b))

         except Exception as e:
            logging.error(f"Error loading/pasting home logo {game_details['home_logo_path']}: {e}")
            draw.text(home_logo_pos, game_details["home_abbr"], font=team_font, fill="white")
    else:
        draw.text((home_logo_pos[0] + 5, home_logo_pos[1] + 5), game_details["home_abbr"], font=team_font, fill="white", anchor="lt")


    draw.text(home_score_pos, str(game_details["home_score"]), font=score_font, fill='white')

    # --- Draw Time and Period / Status ---
    if game_details["is_live"]:
        period_str = f"{game_details['period']}{'st' if game_details['period']==1 else 'nd' if game_details['period']==2 else 'rd' if game_details['period']==3 else 'th'}".upper() if game_details['period'] > 0 else "OT" if game_details['period'] > 3 else "" # Basic period formatting
        # Check for Intermission specifically (adjust key if needed based on API)
        status_name = game_details.get("status_type_name", "") # Need status name if possible
        if status_name == "STATUS_HALFTIME":
        # if "intermission" in game_details["status_text"].lower(): # Alternative check
            period_str = "INTER" # Or "INT"
            game_details["clock"] = "" # No clock during intermission

        draw.text(time_pos, game_details["clock"], font=time_font, fill='yellow', anchor="mt") # anchor middle-top
        draw.text(period_pos, period_str, font=time_font, fill='yellow', anchor="mt")

    elif game_details["is_final"]:
        # Display Final score status
        draw.text(time_pos, "FINAL", font=status_font, fill='red', anchor="mt")
        # Optionally add final period if available (e.g., "FINAL/OT")
        period_str = f"/{game_details['period']}{'st' if game_details['period']==1 else 'nd' if game_details['period']==2 else 'rd' if game_details['period']==3 else 'th'}".upper() if game_details['period'] > 3 else "/OT" if game_details['period'] > 3 else ""
        if game_details['period'] > 3:
             draw.text(period_pos, f"OT{game_details['period'] - 3 if game_details['period'] < 7 else ''}", font=time_font, fill='red', anchor="mt") # Display OT period number
        elif game_details['period'] == 0: # Check if shootout indicated differently?
             draw.text(period_pos, "SO", font=time_font, fill='red', anchor="mt")

    elif game_details["is_upcoming"] and game_details["start_time_utc"]:
        # Display Upcoming game time/date
        start_local = game_details["start_time_utc"].astimezone(LOCAL_TIMEZONE)
        now_local = datetime.now(LOCAL_TIMEZONE)
        today_local = now_local.date()
        start_date_local = start_local.date()

        if start_date_local == today_local:
            date_str = "Today"
        elif start_date_local == today_local + timedelta(days=1):
            date_str = "Tomorrow"
        else:
            date_str = start_local.strftime("%a %b %d") # e.g., "Mon Jan 15"

        time_str = start_local.strftime("%I:%M %p").lstrip('0') # e.g., "7:30 PM"

        draw.text(time_pos, date_str, font=status_font, fill='cyan', anchor="mt")
        draw.text(period_pos, time_str, font=time_font, fill='cyan', anchor="mt")

    else:
        # Fallback for other statuses (Scheduled, Postponed etc.)
        draw.text(time_pos, game_details["status_text"], font=time_font, fill='grey', anchor="mt")

    return img

# --- Main Loop ---
def main():
    """Main execution loop."""
    load_config() # Load config first

    if not NHL_ENABLED:
        logging.info("NHL Scoreboard is disabled in the configuration. Exiting.")
        return

    # --- Matrix Initialization ---
    # options = RGBMatrixOptions()

    # Load options from config (with fallbacks just in case)
    # Note: These need to match the attributes of RGBMatrixOptions
    # try:
    #     # Reload config data here specifically for matrix options
    #     with open(CONFIG_FILE, 'r') as f:
    #         config_data = json.load(f)
    #     display_config = config_data.get("display", {})
    #     hardware_config = display_config.get("hardware", {})
    #     runtime_config = display_config.get("runtime", {})

    #     options.rows = hardware_config.get("rows", 32)
    #     options.cols = hardware_config.get("cols", 64) # Use single panel width
    #     options.chain_length = hardware_config.get("chain_length", 1)
    #     options.parallel = hardware_config.get("parallel", 1)
    #     options.brightness = hardware_config.get("brightness", 60)
    #     options.hardware_mapping = hardware_config.get("hardware_mapping", "adafruit-hat-pwm")
    #     options.scan_mode = 1 if hardware_config.get("scan_mode", "progressive").lower() == "progressive" else 0 # 0 for interlaced
    #     options.pwm_bits = hardware_config.get("pwm_bits", 11)
    #     options.pwm_dither_bits = hardware_config.get("pwm_dither_bits", 0)
    #     options.pwm_lsb_nanoseconds = hardware_config.get("pwm_lsb_nanoseconds", 130)
    #     options.disable_hardware_pulsing = hardware_config.get("disable_hardware_pulsing", False)
    #     options.inverse_colors = hardware_config.get("inverse_colors", False)
    #     options.show_refresh_rate = hardware_config.get("show_refresh_rate", False)
    #     options.limit_refresh_rate_hz = hardware_config.get("limit_refresh_rate_hz", 0) # 0 for no limit

    #     # From runtime config
    #     options.gpio_slowdown = runtime_config.get("gpio_slowdown", 2)

    #     # Set other options if they exist in your config (e.g., led_rgb_sequence, pixel_mapper_config, row_addr_type, multiplexing, panel_type)
    #     if "led_rgb_sequence" in hardware_config:
    #         options.led_rgb_sequence = hardware_config["led_rgb_sequence"]
    #     # Add other specific options as needed

    #     logging.info("RGBMatrix Options configured from config file.")

    # except Exception as e:
    #     logging.error(f"Error reading matrix options from config: {e}. Using default options.")
    #     # Use some safe defaults if config loading fails badly
    #     options.rows = 32
    #     options.cols = 64
    #     options.chain_length = 1
    #     options.parallel = 1
    #     options.hardware_mapping = 'adafruit-hat-pwm'
    #     options.gpio_slowdown = 2

    # # Create matrix instance
    # try:
    #     matrix = RGBMatrix(options = options)
    #     logging.info("RGBMatrix initialized successfully.")
    # except Exception as e:
    #     logging.error(f"Failed to initialize RGBMatrix: {e}")
    #     logging.error("Check hardware connections, configuration, and ensure script is run with sufficient permissions (e.g., sudo or user in gpio group).")
    #     return # Exit if matrix cannot be initialized

    logging.info("Starting NHL Scoreboard...")
    # Logging moved to load_config
    # logging.info(f"Favorite teams: {FAVORITE_TEAMS}")
    logging.info(f"Checking logos in: {LOGO_DIR.resolve()}")
    if not LOGO_DIR.is_dir():
        # Try creating the directory if it doesn't exist
        logging.warning(f"Logo directory {LOGO_DIR} not found. Attempting to create it.")
        try:
            LOGO_DIR.mkdir(parents=True, exist_ok=True)
            logging.info(f"Successfully created logo directory: {LOGO_DIR}")
        except Exception as e:
            logging.error(f"Failed to create logo directory {LOGO_DIR}: {e}. Please create it manually.")
            return # Exit if we can't create it

    while True:
        logging.debug("Fetching latest data...")
        data = get_espn_data()

        game_event = None # Initialize game_event
        if data:
            # Find the most relevant game (Live > Recent Final > Upcoming) for favorites
            game_event = find_relevant_favorite_event(data)

            # Fallback logic only if show_only_favorites is false
            if not game_event and not SHOW_ONLY_FAVORITES and data.get("events"):
                logging.debug("No relevant favorite game found, and show_only_favorites is false. Looking for any live/scheduled game.")
                # Find *any* live game if no favorite is relevant
                live_games = [e for e in data["events"] if e.get("competitions", [{}])[0].get("status", {}).get("type", {}).get("state") == "in"]
                if live_games:
                    logging.info("No favorite game relevant, showing first available live game.")
                    game_event = live_games[0]
                elif data["events"]: # Or just show the first game listed if none are live
                    logging.info("No favorite or live games, showing first scheduled/final game.")
                    game_event = data["events"][0]
            elif not game_event and SHOW_ONLY_FAVORITES:
                logging.info("No relevant favorite game found, and show_only_favorites is true. Skipping display.")
                # game_event remains None

            # Proceed only if we found an event (either favorite or fallback)
            if game_event:
                game_details = extract_game_details(game_event)
                scorebug_image = create_scorebug_image(game_details)
            else:
                # Handle case where no event should be shown (e.g., show_only_favorites is true and none found)
                scorebug_image = create_scorebug_image(None) # Create the 'No game data' image

            # --- Display Output --- 
            try:
                # Convert Pillow image to RGB format expected by matrix
                rgb_image = scorebug_image.convert('RGB') 
                
                # Send image to matrix
                # matrix.SetImage(rgb_image)
                logging.debug("Image sent to matrix.")

                # --- Optional: Using a Canvas for smoother updates --- 
                # canvas.SetImage(rgb_image)
                # canvas = matrix.SwapOnVSync(canvas)
                # logging.debug("Canvas swapped on VSync.")
                
            except Exception as e:
                logging.error(f"Failed to set image on matrix: {e}")

            # Save simulation image (optional now)
            try:
                scorebug_image.save(OUTPUT_IMAGE_FILE)
                logging.info(f"Scorebug image saved to {OUTPUT_IMAGE_FILE.name}")
            except Exception as e:
                logging.error(f"Failed to save scorebug image: {e}")

        else:
            logging.warning("No data received, skipping update cycle.")
            # Optionally display an error message on the matrix
            error_image = create_scorebug_image(None) # Or a custom error message
            try:
                # matrix.SetImage(error_image.convert('RGB'))
                error_image.save(OUTPUT_IMAGE_FILE) # Also save error state to file
            except Exception as e:
                 logging.error(f"Failed to set/save error image: {e}")

        logging.debug(f"Sleeping for {UPDATE_INTERVAL_SECONDS} seconds...")
        time.sleep(UPDATE_INTERVAL_SECONDS)


if __name__ == "__main__":
    main() 

class NHLScoreboardManager:
    def __init__(self, config: dict, display_manager):
        """Initializes the NHLScoreboardManager."""
        self.display_manager = display_manager
        self.config = config
        self.nhl_config = config.get("nhl_scoreboard", {})
        self.is_enabled = self.nhl_config.get("enabled", DEFAULT_NHL_ENABLED)

        # Load settings
        self.favorite_teams = self.nhl_config.get("favorite_teams", DEFAULT_FAVORITE_TEAMS)
        self.test_mode = self.nhl_config.get("test_mode", DEFAULT_NHL_TEST_MODE)
        self.update_interval = self.nhl_config.get("update_interval_seconds", DEFAULT_UPDATE_INTERVAL)
        self.idle_update_interval = self.nhl_config.get("idle_update_interval_seconds", DEFAULT_IDLE_UPDATE_INTERVAL)
        self.cycle_duration = self.nhl_config.get("cycle_game_duration_seconds", DEFAULT_CYCLE_GAME_DURATION)
        self.show_only_favorites = self.nhl_config.get("show_only_favorites", DEFAULT_NHL_SHOW_ONLY_FAVORITES)
        self.logo_dir = DEFAULT_LOGO_DIR
        self.test_data_file = DEFAULT_TEST_DATA_FILE

        # Timezone handling
        tz_string = config.get("timezone", DEFAULT_TIMEZONE)
        try:
            self.local_timezone = ZoneInfo(tz_string)
        except ZoneInfoNotFoundError:
            logging.warning(f"[NHL] Timezone '{tz_string}' not found. Defaulting to {DEFAULT_TIMEZONE}.")
            self.local_timezone = ZoneInfo(DEFAULT_TIMEZONE)

        # State variables
        self.last_data_fetch_time = 0
        self.last_logic_update_time = 0
        self.relevant_events: List[Dict[str, Any]] = [] # ALL relevant events (live, upcoming today, recent final)
        self.current_event_index: int = 0
        self.last_cycle_time: float = 0
        self.current_display_details: Optional[Dict[str, Any]] = None
        self.needs_redraw: bool = True

        # Get display dimensions
        if hasattr(display_manager, 'width') and hasattr(display_manager, 'height'):
            self.display_width = display_manager.width
            self.display_height = display_manager.height
        else: # Fallback
            display_config = config.get("display", {})
            hardware_config = display_config.get("hardware", {})
            cols = hardware_config.get("cols", 64)
            chain = hardware_config.get("chain_length", 1)
            self.display_width = int(cols * chain)
            self.display_height = hardware_config.get("rows", 32)

        self.fonts = self._load_fonts()
        self._log_initial_settings()

    def _log_initial_settings(self):
        logging.info("[NHL] NHLScoreboardManager Initialized.")
        logging.info(f"[NHL] Enabled: {self.is_enabled}")
        logging.info(f"[NHL] Favorite Teams: {self.favorite_teams}")
        logging.info(f"[NHL] Test Mode: {self.test_mode}")
        logging.info(f"[NHL] Show Only Favorites: {self.show_only_favorites}")
        logging.info(f"[NHL] Update Interval: {self.update_interval}s (Active), {self.idle_update_interval}s (Idle)")
        logging.info(f"[NHL] Live Game Cycle Duration: {self.cycle_duration}s")
        logging.info(f"[NHL] Display Size: {self.display_width}x{self.display_height}")

    def _load_fonts(self):
        """Loads fonts used by the scoreboard."""
        fonts = {}
        # Basic font loading, adjust paths/sizes as needed
        try:
            fonts['score'] = ImageFont.truetype("arial.ttf", 12)
            fonts['time'] = ImageFont.truetype("arial.ttf", 10)
            fonts['team'] = ImageFont.truetype("arial.ttf", 8)
            fonts['status'] = ImageFont.truetype("arial.ttf", 9)
            fonts['upcoming_main'] = ImageFont.truetype("arial.ttf", 10) # Font for TODAY/TIME
            fonts['upcoming_vs'] = ImageFont.truetype("arial.ttf", 9) # Font for VS
            fonts['placeholder'] = ImageFont.truetype("arial.ttf", 10) # Font for No Game msg
            fonts['default'] = fonts['time']
        except IOError:
            logging.warning("[NHL] Arial font not found, using default PIL font.")
            fonts['score'] = ImageFont.load_default()
            fonts['time'] = ImageFont.load_default()
            fonts['team'] = ImageFont.load_default()
            fonts['status'] = ImageFont.load_default()
            fonts['upcoming_main'] = ImageFont.load_default()
            fonts['upcoming_vs'] = ImageFont.load_default()
            fonts['placeholder'] = ImageFont.load_default()
            fonts['default'] = ImageFont.load_default()
        return fonts

    def _extract_game_details(self, game_event):
        """Extracts relevant details for the score bug display."""
        if not game_event:
            return None

        details = {}
        try:
            competition = game_event["competitions"][0]
            status = competition["status"]
            competitors = competition["competitors"]
            game_date_str = game_event["date"] # ISO 8601 format (UTC)

            # Parse game date/time
            try:
                details["start_time_utc"] = datetime.fromisoformat(game_date_str.replace("Z", "+00:00"))
            except ValueError:
                logging.warning(f"[NHL] Could not parse game date: {game_date_str}")
                details["start_time_utc"] = None

            home_team = next(c for c in competitors if c.get("homeAway") == "home")
            away_team = next(c for c in competitors if c.get("homeAway") == "away")

            # Extract status name if possible for better logic later
            details["status_type_name"] = status.get("type", {}).get("name") # e.g., STATUS_IN_PROGRESS

            details["status_text"] = status["type"]["shortDetail"] # e.g., "7:30 - 1st" or "Final"
            details["period"] = status.get("period", 0)
            details["clock"] = status.get("displayClock", "0:00")
            details["is_live"] = status["type"]["state"] in ("in", "halftime") # 'in' for ongoing
            details["is_final"] = status["type"]["state"] == "post"
            details["is_upcoming"] = status["type"]["state"] == "pre"

            details["home_abbr"] = home_team["team"]["abbreviation"]
            details["home_score"] = home_team.get("score", "0")
            details["home_logo_path"] = self.logo_dir / f"{details['home_abbr']}.png" # Use self.logo_dir

            details["away_abbr"] = away_team["team"]["abbreviation"]
            details["away_score"] = away_team.get("score", "0")
            details["away_logo_path"] = self.logo_dir / f"{details['away_abbr']}.png" # Use self.logo_dir

            # Check if logo files exist
            if not details["home_logo_path"].is_file():
                logging.warning(f"[NHL] Home logo not found: {details['home_logo_path']}")
                details["home_logo_path"] = None
            if not details["away_logo_path"].is_file():
                logging.warning(f"[NHL] Away logo not found: {details['away_logo_path']}")
                details["away_logo_path"] = None

            return details

        except (KeyError, IndexError, StopIteration, TypeError) as e: # Added TypeError
            logging.error(f"[NHL] Error parsing game details: {e} - Data: {game_event}")
            return None

    def _fetch_data_for_dates(self, dates):
        """Fetches and combines data for a list of dates (YYYYMMDD)."""
        combined_events = []
        event_ids = set()
        success = False

        for date_str in dates:
            data = self._fetch_data(date_str=date_str)
            if data and "events" in data:
                success = True # Mark success if at least one fetch works
                for event in data["events"]:
                    if event["id"] not in event_ids:
                        combined_events.append(event)
                        event_ids.add(event["id"])
            time.sleep(0.1) # Small delay between API calls

        if success:
            self.last_data_fetch_time = time.time() # Update time only if some data was fetched

        # Sort combined events by date just in case
        try:
            combined_events.sort(key=lambda x: datetime.fromisoformat(x["date"].replace("Z", "+00:00")))
        except (KeyError, ValueError):
            logging.warning("[NHL] Could not sort combined events by date during fetch.")

        logging.debug(f"[NHL] Fetched and combined {len(combined_events)} events for dates: {dates}")
        return combined_events

    def _fetch_data(self, date_str: str = None) -> dict:
        """Internal helper to fetch scoreboard data for one specific date or default."""
        url = ESPN_NHL_SCOREBOARD_URL
        params = {}
        log_prefix = "[NHL]"
        fetch_description = "default (today's)"
        if date_str:
            params['dates'] = date_str
            log_prefix = f"[NHL {date_str}]"
            fetch_description = f"date {date_str}"

        logging.info(f"{log_prefix} Fetching data for {fetch_description}.")

        try:
            response = requests.get(url, params=params, timeout=10) # Added timeout
            response.raise_for_status()
            data = response.json()
            logging.info(f"{log_prefix} Successfully fetched data.")

            # Save test data only when fetching default/today's view successfully
            if not date_str and self.test_mode:
                try:
                    with open(self.test_data_file, 'w') as f:
                        json.dump(data, f, indent=2)
                    logging.info(f"[NHL] Saved today's live data to {self.test_data_file.name}")
                except Exception as e:
                    logging.error(f"[NHL] Failed to save test data: {e}")

            return data
        except requests.exceptions.RequestException as e:
            logging.error(f"{log_prefix} Error fetching data from ESPN: {e}")
            # Try loading test data only if fetching today's default failed
            if not date_str and self.test_mode:
                logging.warning("[NHL] Fetching default failed, attempting to load test data.")
                try:
                    with open(self.test_data_file, 'r') as f:
                        test_data = json.load(f)
                    logging.info(f"[NHL] Successfully loaded test data from {self.test_data_file.name}")
                    return test_data
                except Exception as load_e:
                    logging.error(f"[NHL] Failed to load test data: {load_e}")
            return None # Return None if fetch fails

    def _find_events_by_criteria(self, all_events: List[Dict[str, Any]],
                                  is_live: bool = False, is_upcoming_today: bool = False,
                                  is_recent_final: bool = False) -> List[Dict[str, Any]]:
        """Helper to find favorite team events matching specific criteria."""
        matches = []
        now_utc = datetime.now(timezone.utc)
        today_local = datetime.now(self.local_timezone).date()
        cutoff_time_utc = now_utc - timedelta(hours=RECENT_GAME_HOURS)

        for event in all_events:
            competitors = event.get("competitions", [{}])[0].get("competitors", [])
            if len(competitors) == 2:
                team1_abbr = competitors[0].get("team", {}).get("abbreviation")
                team2_abbr = competitors[1].get("team", {}).get("abbreviation")
                is_favorite = team1_abbr in self.favorite_teams or team2_abbr in self.favorite_teams
                # Skip non-favorites ONLY if show_only_favorites is true
                if not is_favorite and self.show_only_favorites:
                    continue

                # Apply criteria ONLY if the event involves a favorite team
                if is_favorite:
                    details = self._extract_game_details(event)
                    if not details: continue

                    if is_live and details["is_live"]:
                        matches.append(event)
                        continue

                    if is_upcoming_today and details["is_upcoming"] and details["start_time_utc"]:
                        start_local_date = details["start_time_utc"].astimezone(self.local_timezone).date()
                        if start_local_date == today_local and details["start_time_utc"] > now_utc:
                             matches.append(event)
                             continue

                    if is_recent_final and details["is_final"] and details["start_time_utc"]:
                         if details["start_time_utc"] > cutoff_time_utc:
                             matches.append(event)
                             continue
            # --- NOTE: No fallback logic here yet for non-favorites if show_only_favorites is false ---

        # Sort results appropriately
        if is_live:
             pass # Keep API order for now
        elif is_upcoming_today:
             matches.sort(key=lambda x: self._extract_game_details(x).get("start_time_utc") or datetime.max.replace(tzinfo=timezone.utc)) # Sort by soonest
        elif is_recent_final:
             matches.sort(key=lambda x: self._extract_game_details(x).get("start_time_utc") or datetime.min.replace(tzinfo=timezone.utc), reverse=True) # Sort by most recent

        return matches

    def update(self):
        """Determines the list of events to cycle through based on priority."""
        if not self.is_enabled:
            if self.relevant_events: # Clear if disabled
                self.relevant_events = []
                self.current_event_index = 0
                self.needs_redraw = True
            return

        now = time.time()

        # Determine check interval: Use faster interval ONLY if a live game is active.
        is_live_game_active = False
        if self.relevant_events and self.current_display_details:
            # Check the currently displayed event first for efficiency
            if self.current_display_details.get("is_live"):
                is_live_game_active = True
            else:
                # If current isn't live, check the whole list (less common)
                for event in self.relevant_events:
                    details = self._extract_game_details(event)
                    if details and details.get("is_live"):
                        is_live_game_active = True
                        break # Found a live game

        check_interval = self.update_interval if is_live_game_active else self.idle_update_interval

        if now - self.last_logic_update_time < check_interval:
            return

        logging.info(f"[NHL] Running update logic (Check Interval: {check_interval}s)")
        self.last_logic_update_time = now

        # Fetch data if interval passed
        all_events: List[Dict] = []
        if now - self.last_data_fetch_time > self.update_interval:
            today_local = datetime.now(self.local_timezone)
            dates_to_fetch = {
                 (today_local - timedelta(days=2)).strftime('%Y%m%d'),
                 (today_local - timedelta(days=1)).strftime('%Y%m%d'),
                 today_local.strftime('%Y%m%d'),
                 (today_local + timedelta(days=1)).strftime('%Y%m%d')
            }
            all_events = self._fetch_data_for_dates(sorted(list(dates_to_fetch)))
            if not all_events:
                 logging.warning("[NHL] No events found after fetching.")
                 # Decide how to handle fetch failure - clear existing or keep stale?
                 # Let's clear for now if fetch fails entirely
                 if self.relevant_events: # If we previously had events
                     self.relevant_events = []
                     self.current_event_index = 0
                     self.current_display_details = None
                     self.needs_redraw = True
                 return # Stop update if fetch failed
        else:
            # Data not stale enough for API call, but logic check proceeds.
            # How do we get all_events? Need to cache it?
            # --> Problem: Can't re-evaluate criteria without fetching.
            # --> Solution: Always fetch data when logic runs, but use interval for logic run itself.
            # --> Let's revert: Fetch data based on fetch interval, run logic based on logic interval.
            # --> Requires caching the fetched `all_events`. Let's add a cache.

            # --- Let's stick to the previous version's combined logic/fetch interval for now ---
            # --- and focus on combining the event lists ---

            today_local = datetime.now(self.local_timezone)
            dates_to_fetch = {
                 (today_local - timedelta(days=2)).strftime('%Y%m%d'),
                 (today_local - timedelta(days=1)).strftime('%Y%m%d'),
                 today_local.strftime('%Y%m%d'),
                 (today_local + timedelta(days=1)).strftime('%Y%m%d')
            }
            all_events = self._fetch_data_for_dates(sorted(list(dates_to_fetch)))
            if not all_events:
                 logging.warning("[NHL] No events found after fetching.")
                 if self.relevant_events:
                     self.relevant_events = []
                     self.current_event_index = 0
                     self.current_display_details = None
                     self.needs_redraw = True
                 return


        # --- Determine Combined List of Relevant Events ---
        live_events = self._find_events_by_criteria(all_events, is_live=True)
        upcoming_events = self._find_events_by_criteria(all_events, is_upcoming_today=True)
        recent_final_events = self._find_events_by_criteria(all_events, is_recent_final=True)

        new_relevant_events_combined = []
        added_ids = set()

        # Add in order of priority, avoiding duplicates
        for event in live_events + upcoming_events + recent_final_events:
            event_id = event.get("id")
            if event_id and event_id not in added_ids:
                new_relevant_events_combined.append(event)
                added_ids.add(event_id)

        # --- TODO: Implement Fallback Logic if show_only_favorites is False ---
        if not new_relevant_events_combined and not self.show_only_favorites:
            logging.debug("[NHL] No relevant favorite games, show_only_favorites=false. Fallback needed.")
            # Add logic here to find non-favorite games based on priority if desired
            pass # No fallback implemented yet

        # --- Compare and Update State ---
        old_event_ids = {e.get("id") for e in self.relevant_events if e}
        new_event_ids = {e.get("id") for e in new_relevant_events_combined if e}

        if old_event_ids != new_event_ids:
            logging.info(f"[NHL] Relevant events changed. New count: {len(new_relevant_events_combined)}")
            self.relevant_events = new_relevant_events_combined
            self.current_event_index = 0
            self.last_cycle_time = time.time() # Reset cycle timer
            # Load details for the first item immediately
            self.current_display_details = self._extract_game_details(self.relevant_events[0] if self.relevant_events else None)
            self.needs_redraw = True
        elif self.relevant_events: # List content is same, check if details of *current* item changed
            current_event_in_list = self.relevant_events[self.current_event_index]
            new_details_for_current = self._extract_game_details(current_event_in_list)
            # Compare specifically relevant fields (score, clock, period, status)
            if self._details_changed_significantly(self.current_display_details, new_details_for_current):
                 logging.debug(f"[NHL] Details updated for current event index {self.current_event_index}")
                 self.current_display_details = new_details_for_current
                 self.needs_redraw = True
            else:
                 logging.debug("[NHL] No significant change in details for current event.")
        # else: No relevant events before or after


    def _details_changed_significantly(self, old_details, new_details) -> bool:
         """Compare specific fields to see if a redraw is needed."""
         if old_details is None and new_details is None: return False
         if old_details is None or new_details is None: return True # Changed from something to nothing or vice-versa

         fields_to_check = ['home_score', 'away_score', 'clock', 'period', 'is_live', 'is_final', 'is_upcoming']
         for field in fields_to_check:
              if old_details.get(field) != new_details.get(field):
                   return True
         return False


    def display(self, force_clear: bool = False):
        """Generates and displays the current frame, handling cycling."""
        if not self.is_enabled:
            return

        now = time.time()
        redraw_this_frame = force_clear or self.needs_redraw

        # --- Handle Cycling ---
        if len(self.relevant_events) > 1: # Cycle if more than one relevant event exists
             if now - self.last_cycle_time > self.cycle_duration:
                  self.current_event_index = (self.current_event_index + 1) % len(self.relevant_events)
                  # Get details for the *new* index
                  self.current_display_details = self._extract_game_details(self.relevant_events[self.current_event_index])
                  self.last_cycle_time = now
                  redraw_this_frame = True # Force redraw on cycle
                  logging.debug(f"[NHL] Cycling to event index {self.current_event_index}")
             elif self.current_display_details is None: # Ensure details loaded for index 0 initially
                  self.current_display_details = self._extract_game_details(self.relevant_events[0])
                  redraw_this_frame = True # Force redraw if details were missing
        elif len(self.relevant_events) == 1:
             # If only one event, make sure its details are loaded
             if self.current_display_details is None:
                  self.current_display_details = self._extract_game_details(self.relevant_events[0])
                  redraw_this_frame = True
        else: # No relevant events
             if self.current_display_details is not None: # Clear details if list is empty now
                  self.current_display_details = None
                  redraw_this_frame = True


        # --- Generate and Display Frame ---
        if not redraw_this_frame:
            return

        logging.debug(f"[NHL] Generating frame (Index: {self.current_event_index})")
        frame = self._create_frame(self.current_display_details) # Pass the specific details

        try:
            if hasattr(self.display_manager, 'display_image'):
                 self.display_manager.display_image(frame)
            elif hasattr(self.display_manager, 'matrix') and hasattr(self.display_manager.matrix, 'SetImage'):
                 self.display_manager.matrix.SetImage(frame.convert('RGB'))
            else:
                 logging.error("[NHL] DisplayManager missing display_image or matrix.SetImage method.")

            self.needs_redraw = False

        except Exception as e:
            logging.error(f"[NHL] Error displaying frame via DisplayManager: {e}")


    def _create_frame(self, game_details: Optional[Dict[str, Any]]) -> Image.Image:
        """Creates a Pillow image frame based on game details."""
        # This method now simply renders the layout based on the details passed in
        img = Image.new('RGB', (self.display_width, self.display_height), color='black')
        draw = ImageDraw.Draw(img)

        if not game_details:
            self._draw_placeholder_layout(draw)
        elif game_details.get("is_upcoming"):
            self._draw_upcoming_layout(draw, game_details)
        elif game_details.get("is_live") or game_details.get("is_final"):
            self._draw_scorebug_layout(draw, game_details)
        else: # Fallback/Other states
             self._draw_placeholder_layout(draw, msg=game_details.get("status_text", "NHL Status")) # Show status text

        return img

    def _draw_placeholder_layout(self, draw: ImageDraw.ImageDraw, msg: str = "No NHL Games"):
        """Draws the 'No NHL Games' or other placeholder message."""
        font = self.fonts.get('placeholder', ImageFont.load_default())
        bbox = draw.textbbox((0,0), msg, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        draw.text(((self.display_width - text_width) // 2, (self.display_height - text_height) // 2),
                  msg, font=font, fill='grey')

    def _draw_upcoming_layout(self, draw: ImageDraw.ImageDraw, game_details: Dict[str, Any]):
        """Draws the layout for an upcoming game."""
        font_team = self.fonts.get('team', ImageFont.load_default())
        font_main = self.fonts.get('upcoming_main', ImageFont.load_default())
        font_vs = self.fonts.get('upcoming_vs', ImageFont.load_default())
        img = draw.im

        logging.debug("[NHL] Drawing upcoming game layout.")

        logo_padding = 2
        logo_max_h = self.display_height - (logo_padding * 2)
        logo_area_width = int(self.display_width * 0.4)
        logo_max_w = logo_area_width - logo_padding
        logo_size = (logo_max_w, logo_max_h)

        away_logo_x = logo_padding
        home_logo_x = self.display_width - logo_area_width + logo_padding

        # Draw Away Logo
        if game_details.get("away_logo_path"):
            try:
                away_logo_rgba = Image.open(game_details["away_logo_path"]).convert("RGBA")
                # Resize and reassign, instead of in-place thumbnail
                away_logo_rgba = away_logo_rgba.resize(logo_size, Image.Resampling.LANCZOS)

                paste_x = away_logo_x
                paste_y = (self.display_height - away_logo_rgba.height) // 2

                # Manual pixel paste (robust alternative)
                for x in range(away_logo_rgba.width):
                    for y in range(away_logo_rgba.height):
                        r, g, b, a = away_logo_rgba.getpixel((x, y))
                        if a > 128: # Check alpha threshold
                            target_x = paste_x + x
                            target_y = paste_y + y
                            # Ensure target pixel is within image bounds
                            if 0 <= target_x < img.width and 0 <= target_y < img.height:
                                img.putpixel((target_x, target_y), (r, g, b))

            except Exception as e:
                logging.error(f"[NHL] Error rendering upcoming away logo {game_details['away_logo_path']}: {e}")
                draw.text((away_logo_x, 5), game_details.get("away_abbr", "?"), font=font_team, fill="white")
        else:
             draw.text((away_logo_x, 5), game_details.get("away_abbr", "?"), font=font_team, fill="white")

        # Draw Home Logo
        if game_details.get("home_logo_path"):
             try:
                home_logo_rgba = Image.open(game_details["home_logo_path"]).convert("RGBA")
                # Resize and reassign, instead of in-place thumbnail
                home_logo_rgba = home_logo_rgba.resize(logo_size, Image.Resampling.LANCZOS)

                paste_x = home_logo_x
                paste_y = (self.display_height - home_logo_rgba.height) // 2

                # Manual pixel paste (robust alternative)
                for x in range(home_logo_rgba.width):
                    for y in range(home_logo_rgba.height):
                        r, g, b, a = home_logo_rgba.getpixel((x, y))
                        if a > 128: # Check alpha threshold
                            target_x = paste_x + x
                            target_y = paste_y + y
                            # Ensure target pixel is within image bounds
                            if 0 <= target_x < img.width and 0 <= target_y < img.height:
                                img.putpixel((target_x, target_y), (r, g, b))

             except Exception as e:
                logging.error(f"[NHL] Error rendering upcoming home logo {game_details['home_logo_path']}: {e}")
                draw.text((home_logo_x, 5), game_details.get("home_abbr", "?"), font=font_team, fill="white")
        else:
            draw.text((home_logo_x, 5), game_details.get("home_abbr", "?"), font=font_team, fill="white")

        # Center Text Area
        center_start_x = logo_area_width
        center_end_x = self.display_width - logo_area_width
        center_x = (center_start_x + center_end_x) // 2

        # Prepare Text
        start_utc = game_details.get("start_time_utc")
        date_str = "???"
        time_str = "??:??"
        if start_utc:
            start_local = start_utc.astimezone(self.local_timezone)
            now_local = datetime.now(self.local_timezone)
            today_local = now_local.date()
            start_date_local = start_local.date()
            if start_date_local == today_local: date_str = "TODAY"
            elif start_date_local == today_local + timedelta(days=1): date_str = "TOMORROW"
            else: date_str = start_local.strftime("%a %b %d").upper()
            time_str = start_local.strftime("%H:%M")
        vs_str = "VS"

        # Calculate Positions (adjust line_height as needed)
        line_height_approx = font_main.getbbox("Aj")[3] - font_main.getbbox("Aj")[1] + 2
        vs_height = font_vs.getbbox("VS")[3] - font_vs.getbbox("VS")[1]
        total_text_height = (line_height_approx * 2) + vs_height
        start_y = (self.display_height - total_text_height) // 2

        date_y = start_y
        time_y = date_y + line_height_approx
        vs_y = time_y + line_height_approx

        # Draw Text
        draw.text((center_x, date_y), date_str, font=font_main, fill='white', anchor="mt")
        draw.text((center_x, time_y), time_str, font=font_main, fill='white', anchor="mt")
        draw.text((center_x, vs_y), vs_str, font=font_vs, fill='white', anchor="mt")


    def _draw_scorebug_layout(self, draw: ImageDraw.ImageDraw, game_details: Dict[str, Any]):
        """Draws the standard score bug layout for live or final games."""
        font_score = self.fonts.get('score', ImageFont.load_default())
        font_time = self.fonts.get('time', ImageFont.load_default())
        font_team = self.fonts.get('team', ImageFont.load_default())
        font_status = self.fonts.get('status', ImageFont.load_default())
        img = draw.im

        logging.debug("[NHL] Drawing live/final game layout.")

        # Layout Calculations
        logo_max_h = self.display_height - 4
        logo_max_w = int(self.display_width * 0.25)
        logo_size = (logo_max_w, logo_max_h)
        away_logo_x = 2
        score_width_approx = 25
        away_score_x = away_logo_x + logo_max_w + 4
        home_logo_x = self.display_width - logo_max_w - 2
        home_score_x = home_logo_x - score_width_approx - 4
        center_x = self.display_width // 2
        time_y = 2
        period_y = 15

        # --- Draw Away Team ---
        away_logo_drawn_size = (0,0)
        if game_details.get("away_logo_path"):
            try:
                away_logo_rgba = Image.open(game_details["away_logo_path"]).convert("RGBA")
                # Resize and reassign, instead of in-place thumbnail
                away_logo_rgba = away_logo_rgba.resize(logo_size, Image.Resampling.LANCZOS)
                away_logo_drawn_size = away_logo_rgba.size # Keep track of size

                paste_x = away_logo_x
                paste_y = (self.display_height - away_logo_rgba.height) // 2

                # Manual pixel paste (robust alternative)
                for x in range(away_logo_rgba.width):
                    for y in range(away_logo_rgba.height):
                        r, g, b, a = away_logo_rgba.getpixel((x, y))
                        if a > 128: # Check alpha threshold
                            target_x = paste_x + x
                            target_y = paste_y + y
                            # Ensure target pixel is within image bounds
                            if 0 <= target_x < img.width and 0 <= target_y < img.height:
                                img.putpixel((target_x, target_y), (r, g, b))

            except Exception as e:
                logging.error(f"[NHL] Error rendering away logo {game_details['away_logo_path']}: {e}")
                draw.text((away_logo_x + 2, 5), game_details.get("away_abbr", "?"), font=font_team, fill="white")
        else:
            draw.text((away_logo_x + 2, 5), game_details.get("away_abbr", "?"), font=font_team, fill="white")

        current_away_score_x = (away_logo_x + away_logo_drawn_size[0] + 4) if away_logo_drawn_size[0] > 0 else away_score_x
        draw.text((current_away_score_x, (self.display_height - 12) // 2), str(game_details.get("away_score", "0")), font=font_score, fill='white')

        # --- Draw Home Team ---
        home_logo_drawn_size = (0,0)
        if game_details.get("home_logo_path"):
             try:
                home_logo_rgba = Image.open(game_details["home_logo_path"]).convert("RGBA")
                # Resize and reassign, instead of in-place thumbnail
                home_logo_rgba = home_logo_rgba.resize(logo_size, Image.Resampling.LANCZOS)
                home_logo_drawn_size = home_logo_rgba.size # Keep track of size

                paste_x = home_logo_x
                paste_y = (self.display_height - home_logo_rgba.height) // 2

                # Manual pixel paste (robust alternative)
                for x in range(home_logo_rgba.width):
                    for y in range(home_logo_rgba.height):
                        r, g, b, a = home_logo_rgba.getpixel((x, y))
                        if a > 128: # Check alpha threshold
                            target_x = paste_x + x
                            target_y = paste_y + y
                            # Ensure target pixel is within image bounds
                            if 0 <= target_x < img.width and 0 <= target_y < img.height:
                                img.putpixel((target_x, target_y), (r, g, b))

             except Exception as e:
                logging.error(f"[NHL] Error rendering home logo {game_details['home_logo_path']}: {e}")
                draw.text((home_logo_x + 2, 5), game_details.get("home_abbr", "?"), font=font_team, fill="white")
        else:
            draw.text((home_logo_x + 2, 5), game_details.get("home_abbr", "?"), font=font_team, fill="white")

        current_home_score_x = home_logo_x - score_width_approx - 4
        draw.text((current_home_score_x, (self.display_height - 12) // 2), str(game_details.get("home_score", "0")), font=font_score, fill='white')

        # --- Draw Center Info ---
        if game_details.get("is_live"):
            period = game_details.get('period', 0)
            period_str = f"{period}{'st' if period==1 else 'nd' if period==2 else 'rd' if period==3 else 'th'}".upper() if period > 0 and period <= 3 else "OT" if period > 3 else ""
            status_name = game_details.get("status_type_name", "")
            clock_text = game_details.get("clock", "")
            if status_name == "STATUS_HALFTIME" or "intermission" in game_details.get("status_text", "").lower():
                period_str = "INTER"
                clock_text = ""
            draw.text((center_x, time_y), clock_text, font=font_time, fill='yellow', anchor="mt")
            draw.text((center_x, period_y), period_str, font=font_time, fill='yellow', anchor="mt")
        elif game_details.get("is_final"):
            draw.text((center_x, time_y), "FINAL", font=font_status, fill='red', anchor="mt")
            period = game_details.get('period', 0)
            final_period_str = ""
            if period > 3:
                 final_period_str = f"OT{period - 3 if period < 7 else ''}"
            elif game_details.get("status_type_name") == "STATUS_SHOOTOUT":
                 final_period_str = "SO"
            if final_period_str:
                draw.text((center_x, period_y), final_period_str, font=font_time, fill='red', anchor="mt")
        else: # Should not happen if logic is correct, but fallback
             status_text = game_details.get("status_text", "Error")
             draw.text((center_x, time_y), status_text, font=font_time, fill='grey', anchor="mt")


if __name__ == "__main__":
    main() 