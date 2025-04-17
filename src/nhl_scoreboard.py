import requests
import json
import time
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import logging
from datetime import datetime, timedelta, timezone
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
DEFAULT_IDLE_UPDATE_INTERVAL = 300 # Default 5 minutes
DEFAULT_LOGO_DIR = PROJECT_ROOT / "assets" / "sports" / "nhl_logos" # Absolute path
DEFAULT_TEST_DATA_FILE = PROJECT_ROOT / "test_nhl_data.json" # Absolute path
DEFAULT_OUTPUT_IMAGE_FILE = PROJECT_ROOT / "nhl_scorebug_output.png" # Absolute path
DEFAULT_TIMEZONE = "UTC"
DEFAULT_NHL_SHOW_ONLY_FAVORITES = False
RECENT_GAME_HOURS = 24 # How many hours back to check for recent finals

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
            away_logo = Image.open(game_details["away_logo_path"]).convert("RGBA")
            away_logo.thumbnail(logo_size, Image.Resampling.LANCZOS)
            img.paste(away_logo, away_logo_pos, away_logo) # Use logo as mask for transparency
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
            home_logo = Image.open(game_details["home_logo_path"]).convert("RGBA")
            home_logo.thumbnail(logo_size, Image.Resampling.LANCZOS)
            img.paste(home_logo, home_logo_pos, home_logo)
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
        """
        Initializes the NHLScoreboardManager.

        Args:
            config (dict): The main configuration dictionary.
            display_manager: The central display manager object 
                             (used for dimensions, potentially fonts/drawing later).
        """
        self.display_manager = display_manager
        self.config = config
        self.nhl_config = config.get("nhl_scoreboard", {})
        self.is_enabled = self.nhl_config.get("enabled", DEFAULT_NHL_ENABLED)

        # Load settings
        self.favorite_teams = self.nhl_config.get("favorite_teams", DEFAULT_FAVORITE_TEAMS)
        self.test_mode = self.nhl_config.get("test_mode", DEFAULT_NHL_TEST_MODE)
        self.update_interval = self.nhl_config.get("update_interval_seconds", DEFAULT_UPDATE_INTERVAL)
        self.idle_update_interval = self.nhl_config.get("idle_update_interval_seconds", DEFAULT_IDLE_UPDATE_INTERVAL)
        self.show_only_favorites = self.nhl_config.get("show_only_favorites", DEFAULT_NHL_SHOW_ONLY_FAVORITES)
        self.logo_dir = DEFAULT_LOGO_DIR # Use constant for now, could be made configurable
        self.test_data_file = DEFAULT_TEST_DATA_FILE # Use constant for now

        # Timezone handling (uses timezone from main config)
        tz_string = config.get("timezone", DEFAULT_TIMEZONE)
        try:
            self.local_timezone = ZoneInfo(tz_string)
        except ZoneInfoNotFoundError:
            logging.warning(f"[NHL] Timezone '{tz_string}' not found. Defaulting to {DEFAULT_TIMEZONE}.")
            self.local_timezone = ZoneInfo(DEFAULT_TIMEZONE)

        # State variables
        self.last_update_time = 0
        self.current_event_data = None # Raw data for the event being displayed
        self.current_game_details = None # Processed details for the event
        self.needs_update = True # Flag to indicate frame needs regeneration

        # Get display dimensions (from display_manager if possible, else config)
        if hasattr(display_manager, 'width') and hasattr(display_manager, 'height'):
            self.display_width = display_manager.width
            self.display_height = display_manager.height
        else: # Fallback to reading from config
            display_config = config.get("display", {})
            hardware_config = display_config.get("hardware", {})
            cols = hardware_config.get("cols", 64)
            chain = hardware_config.get("chain_length", 1)
            self.display_width = int(cols * chain)
            self.display_height = hardware_config.get("rows", 32)
        
        # Preload fonts (optional, but good practice)
        self.fonts = self._load_fonts()

        logging.info("[NHL] NHLScoreboardManager Initialized.")
        logging.info(f"[NHL] Enabled: {self.is_enabled}")
        logging.info(f"[NHL] Favorite Teams: {self.favorite_teams}")
        logging.info(f"[NHL] Test Mode: {self.test_mode}")
        logging.info(f"[NHL] Show Only Favorites: {self.show_only_favorites}")
        logging.info(f"[NHL] Update Interval: {self.update_interval}s (Active), {self.idle_update_interval}s (Idle)")
        logging.info(f"[NHL] Display Size: {self.display_width}x{self.display_height}")

    def _load_fonts(self):
        """Loads fonts used by the scoreboard."""
        fonts = {}
        try:
            # Adjust sizes as needed
            fonts['score'] = ImageFont.truetype("arial.ttf", 12) 
            fonts['time'] = ImageFont.truetype("arial.ttf", 10)
            fonts['team'] = ImageFont.truetype("arial.ttf", 8)
            fonts['status'] = ImageFont.truetype("arial.ttf", 9)
            fonts['default'] = fonts['time'] # Default if specific not found
        except IOError:
            logging.warning("[NHL] Arial font not found, using default PIL font.")
            fonts['score'] = ImageFont.load_default()
            fonts['time'] = ImageFont.load_default()
            fonts['team'] = ImageFont.load_default()
            fonts['status'] = ImageFont.load_default()
            fonts['default'] = ImageFont.load_default()
        return fonts

    def _fetch_data(self):
        """Fetches scoreboard data from ESPN API or loads test data."""
        try:
            response = requests.get(ESPN_NHL_SCOREBOARD_URL)
            response.raise_for_status()
            data = response.json()
            logging.info("[NHL] Successfully fetched live data from ESPN.")
            if self.test_mode:
                try:
                    with open(self.test_data_file, 'w') as f:
                        json.dump(data, f, indent=2)
                    logging.info(f"[NHL] Saved live data to {self.test_data_file.name}")
                except Exception as e:
                    logging.error(f"[NHL] Failed to save test data: {e}")
            self.last_update_time = time.time()
            return data
        except requests.exceptions.RequestException as e:
            logging.error(f"[NHL] Error fetching data from ESPN: {e}")
            if self.test_mode:
                logging.warning("[NHL] Fetching failed, attempting to load test data.")
                try:
                    with open(self.test_data_file, 'r') as f:
                        data = json.load(f)
                        logging.info(f"[NHL] Successfully loaded test data from {self.test_data_file.name}")
                    return data
                except FileNotFoundError:
                    logging.error(f"[NHL] Test data file {self.test_data_file.name} not found.")
                except json.JSONDecodeError:
                    logging.error(f"[NHL] Error decoding test data file {self.test_data_file.name}.")
                except Exception as e:
                    logging.error(f"[NHL] Failed to load test data: {e}")
            return None

    def _extract_game_details(self, game_event):
        """Extracts relevant details for the score bug display from raw event data."""
        if not game_event:
            return None

        details = {}
        try:
            competition = game_event["competitions"][0]
            status = competition["status"]
            competitors = competition["competitors"]
            game_date_str = game_event["date"]

            try:
                details["start_time_utc"] = datetime.fromisoformat(game_date_str.replace("Z", "+00:00"))
            except ValueError:
                logging.warning(f"[NHL] Could not parse game date: {game_date_str}")
                details["start_time_utc"] = None

            home_team = next(c for c in competitors if c.get("homeAway") == "home")
            away_team = next(c for c in competitors if c.get("homeAway") == "away")

            details["status_text"] = status["type"]["shortDetail"]
            details["status_type_name"] = status["type"].get("name") 
            details["period"] = status.get("period", 0)
            details["clock"] = status.get("displayClock", "0:00")
            details["is_live"] = status["type"]["state"] in ("in", "halftime")
            details["is_final"] = status["type"]["state"] == "post"
            details["is_upcoming"] = status["type"]["state"] == "pre"

            details["home_abbr"] = home_team["team"]["abbreviation"]
            details["home_score"] = home_team.get("score", "0")
            details["home_logo_path"] = self.logo_dir / f"{details['home_abbr']}.png"

            details["away_abbr"] = away_team["team"]["abbreviation"]
            details["away_score"] = away_team.get("score", "0")
            details["away_logo_path"] = self.logo_dir / f"{details['away_abbr']}.png"

            # Check if logo files exist
            if not details["home_logo_path"].is_file():
                logging.debug(f"[NHL] Home logo not found: {details['home_logo_path']}")
                details["home_logo_path"] = None
            if not details["away_logo_path"].is_file():
                logging.debug(f"[NHL] Away logo not found: {details['away_logo_path']}")
                details["away_logo_path"] = None

            return details

        except (KeyError, IndexError, StopIteration, TypeError) as e:
            logging.error(f"[NHL] Error parsing game details: {e} - Data snippet: {str(game_event)[:200]}...")
            return None

    def _find_relevant_favorite_event(self, data):
        """Finds the most relevant game for favorite teams: Live > Recent Final > Next Upcoming."""
        if not data or "events" not in data:
            return None

        live_event = None
        recent_final_event = None
        next_upcoming_event = None

        now_utc = datetime.now(timezone.utc)
        cutoff_time_utc = now_utc - timedelta(hours=RECENT_GAME_HOURS)
        
        favorite_events_details = {}
        for event in data["events"]:
            competitors = event.get("competitions", [{}])[0].get("competitors", [])
            if len(competitors) == 2:
                team1_abbr = competitors[0].get("team", {}).get("abbreviation")
                team2_abbr = competitors[1].get("team", {}).get("abbreviation")
                is_favorite = team1_abbr in self.favorite_teams or team2_abbr in self.favorite_teams
                if is_favorite:
                    details = self._extract_game_details(event)
                    if details and details.get("start_time_utc"): # Ensure details and time parsed
                        favorite_events_details[event["id"]] = (event, details)
                    elif details:
                        logging.debug(f"[NHL] Skipping favorite event {event.get('id')} due to missing start time in details.")
                    else:
                        logging.debug(f"[NHL] Skipping favorite event {event.get('id')} due to parsing error.")

        # --- Prioritize --- 
        # Store details along with event to avoid re-extracting for comparison
        potential_recent_final = None
        potential_upcoming = None

        for event_id, (event, details) in favorite_events_details.items():
            # 1. Live Game? Highest priority.
            if details["is_live"]:
                logging.debug(f"[NHL] Found live favorite game: {details['away_abbr']} vs {details['home_abbr']}")
                live_event = event
                break # Found the highest priority

            # 2. Recent Final?
            if details["is_final"] and details["start_time_utc"] > cutoff_time_utc:
                if potential_recent_final is None or details["start_time_utc"] > potential_recent_final[1]["start_time_utc"]:
                     potential_recent_final = (event, details)

            # 3. Upcoming Game?
            if details["is_upcoming"] and details["start_time_utc"] > now_utc:
                if potential_upcoming is None or details["start_time_utc"] < potential_upcoming[1]["start_time_utc"]:
                    potential_upcoming = (event, details)

        # --- Select based on priority --- 
        if live_event:
            logging.info("[NHL] Selecting live favorite game.")
            return live_event
        elif potential_recent_final:
            logging.info("[NHL] Selecting recent final favorite game.")
            return potential_recent_final[0] # Return the event part
        elif potential_upcoming:
            logging.info("[NHL] Selecting next upcoming favorite game.")
            return potential_upcoming[0] # Return the event part
        else:
            logging.info("[NHL] No relevant (live, recent final, or upcoming) favorite games found.")
            return None

    def _create_frame(self, game_details):
        """Creates a Pillow image for the score bug based on game details."""
        img = Image.new('RGB', (self.display_width, self.display_height), color='black')
        draw = ImageDraw.Draw(img)
        font_default = self.fonts.get('default', ImageFont.load_default())

        if not game_details:
            msg = "NHL: No Game"
            bbox = draw.textbbox((0,0), msg, font=font_default)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            draw.text(((self.display_width - text_width) // 2, (self.display_height - text_height) // 2),
                      msg, font=font_default, fill='grey')
            return img

        # Get fonts from preloaded dict
        score_font = self.fonts.get('score', font_default)
        time_font = self.fonts.get('time', font_default)
        team_font = self.fonts.get('team', font_default)
        status_font = self.fonts.get('status', font_default)

        # --- Layout Calculations --- 
        logo_max_h = self.display_height - 4
        logo_max_w = int(self.display_width * 0.25) 
        logo_size = (logo_max_w, logo_max_h)

        away_logo_x = 2
        # Reserve space for score next to logo area (adjust width as needed)
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
                away_logo = Image.open(game_details["away_logo_path"]).convert("RGBA")
                away_logo.thumbnail(logo_size, Image.Resampling.LANCZOS)
                img.paste(away_logo, (away_logo_x, (self.display_height - away_logo.height) // 2), away_logo)
                away_logo_drawn_size = away_logo.size
            except Exception as e:
                logging.error(f"[NHL] Error rendering away logo {game_details['away_logo_path']}: {e}")
                # Fallback to text if logo fails
                draw.text((away_logo_x + 2, 5), game_details.get("away_abbr", "?"), font=team_font, fill="white")
        else:
            draw.text((away_logo_x + 2, 5), game_details.get("away_abbr", "?"), font=team_font, fill="white")

        # Adjust score position dynamically based on drawn logo, if available
        current_away_score_x = (away_logo_x + away_logo_drawn_size[0] + 4) if away_logo_drawn_size[0] > 0 else away_score_x
        draw.text((current_away_score_x, (self.display_height - 12) // 2), str(game_details.get("away_score", "0")), font=score_font, fill='white')

        # --- Draw Home Team ---
        home_logo_drawn_size = (0,0)
        if game_details.get("home_logo_path"):
             try:
                home_logo = Image.open(game_details["home_logo_path"]).convert("RGBA")
                home_logo.thumbnail(logo_size, Image.Resampling.LANCZOS)
                img.paste(home_logo, (home_logo_x, (self.display_height - home_logo.height) // 2), home_logo)
                home_logo_drawn_size = home_logo.size
             except Exception as e:
                logging.error(f"[NHL] Error rendering home logo {game_details['home_logo_path']}: {e}")
                draw.text((home_logo_x + 2, 5), game_details.get("home_abbr", "?"), font=team_font, fill="white")
        else:
            draw.text((home_logo_x + 2, 5), game_details.get("home_abbr", "?"), font=team_font, fill="white")

        # Adjust score position dynamically
        # Position score to the left of where the logo starts
        current_home_score_x = home_logo_x - score_width_approx - 4 
        draw.text((current_home_score_x, (self.display_height - 12) // 2), str(game_details.get("home_score", "0")), font=score_font, fill='white')

        # --- Draw Time and Period / Status --- 
        center_x = self.display_width // 2
        if game_details.get("is_live"):
            period = game_details.get('period', 0)
            period_str = f"{period}{'st' if period==1 else 'nd' if period==2 else 'rd' if period==3 else 'th'}".upper() if period > 0 and period <= 3 else "OT" if period > 3 else ""
            status_name = game_details.get("status_type_name", "")
            clock_text = game_details.get("clock", "")
            if status_name == "STATUS_HALFTIME" or "intermission" in game_details.get("status_text", "").lower():
                period_str = "INTER"
                clock_text = "" 

            draw.text((center_x, time_y), clock_text, font=time_font, fill='yellow', anchor="mt")
            draw.text((center_x, period_y), period_str, font=time_font, fill='yellow', anchor="mt")

        elif game_details.get("is_final"):
            draw.text((center_x, time_y), "FINAL", font=status_font, fill='red', anchor="mt")
            period = game_details.get('period', 0)
            final_period_str = ""
            if period > 3:
                 final_period_str = f"OT{period - 3 if period < 7 else ''}" # Basic multi-OT
            elif game_details.get("status_type_name") == "STATUS_SHOOTOUT": 
                 final_period_str = "SO"
            if final_period_str:
                draw.text((center_x, period_y), final_period_str, font=time_font, fill='red', anchor="mt")

        elif game_details.get("is_upcoming") and game_details.get("start_time_utc"):
            start_local = game_details["start_time_utc"].astimezone(self.local_timezone)
            now_local = datetime.now(self.local_timezone)
            today_local = now_local.date()
            start_date_local = start_local.date()

            if start_date_local == today_local: date_str = "Today"
            elif start_date_local == today_local + timedelta(days=1): date_str = "Tomorrow"
            else: date_str = start_local.strftime("%a %b %d")

            time_str = start_local.strftime("%I:%M %p").lstrip('0')

            draw.text((center_x, time_y), date_str, font=status_font, fill='cyan', anchor="mt")
            draw.text((center_x, period_y), time_str, font=time_font, fill='cyan', anchor="mt")
        else:
            # Fallback for other statuses
            status_text = game_details.get("status_text", "Error")
            draw.text((center_x, time_y), status_text, font=time_font, fill='grey', anchor="mt")

        return img

    # --- Public Methods for Controller ---

    def update(self):
        """
        Checks if an update is needed based on state (active vs idle interval), 
        fetches data, finds relevant event, and updates state.
        Called periodically by the main display controller.
        Sets self.needs_update if the relevant game details change.
        """
        if not self.is_enabled:
            if self.current_game_details is not None:
                 self.current_game_details = None
                 self.needs_update = True
            return

        now = time.time()
        force_check = False

        # Determine which update interval to use for this check
        # Use short interval if a game is live or upcoming relatively soon, otherwise use idle interval
        # Simple check: Use active interval if we currently have *any* game details selected
        current_interval = self.update_interval if self.current_game_details else self.idle_update_interval

        # Check if upcoming game might have started (still needs a check regardless of interval)
        if self.current_game_details and self.current_game_details.get('is_upcoming'):
            start_time = self.current_game_details.get('start_time_utc')
            # Check if start time is within the *next* active interval period to force check early
            if start_time and (start_time - timedelta(seconds=self.update_interval)) < datetime.now(timezone.utc):
                logging.debug("[NHL] Upcoming game is starting soon, ensuring frequent checks.")
                current_interval = self.update_interval # Ensure we use the short interval
                if datetime.now(timezone.utc) > start_time:
                     logging.debug("[NHL] Upcoming game may have started, forcing update check.")
                     force_check = True

        # Check interval or if forced
        if force_check or (now - self.last_update_time > current_interval):
            logging.debug(f"[NHL] Checking for updates (Force: {force_check}, Interval: {current_interval}s). Triggered at {now:.2f}, Last update: {self.last_update_time:.2f}")
            all_data = self._fetch_data() 
            new_event_data = None
            if all_data:
                new_event_data = self._find_relevant_favorite_event(all_data)
                if not new_event_data and not self.show_only_favorites and all_data.get("events"):
                    live_games = [e for e in all_data["events"] if e.get("competitions", [{}])[0].get("status", {}).get("type", {}).get("state") == "in"]
                    if live_games:
                        new_event_data = live_games[0]
                    elif all_data["events"]:
                         new_event_data = all_data["events"][0]
            # else: fetch failed, new_event_data remains None

            # --- Compare and Update State --- 
            old_event_id = self.current_event_data.get("id") if self.current_event_data else None
            new_event_id = new_event_data.get("id") if new_event_data else None
            
            new_details = self._extract_game_details(new_event_data)

            # Significant change detection (more robust needed?)
            # Compare relevant fields: score, clock, period, status state
            if new_details != self.current_game_details: # Basic check for now
                 logging.debug("[NHL] Game details updated or event changed.")
                 self.current_event_data = new_event_data
                 self.current_game_details = new_details
                 self.needs_update = True
            else:
                 logging.debug("[NHL] No change detected in event or details.")
                 # self.needs_update remains unchanged (likely False)

        # No else needed here, if interval hasn't passed, we do nothing

    def display(self, force_clear: bool = False):
        """
        Generates the NHL frame and displays it using the display_manager.
        Called by the main display controller when this module is active.
        """
        if not self.is_enabled:
            # Optionally display a "disabled" message or clear?
            # For now, just return to let controller handle it.
            return

        # Only redraw if forced or if data has changed
        if not force_clear and not self.needs_update:
            return

        logging.debug(f"[NHL] Generating frame (force_clear={force_clear}, needs_update={self.needs_update})")
        frame = self._create_frame(self.current_game_details)

        # Use the display_manager to show the frame
        try:
            if hasattr(self.display_manager, 'display_image'):
                 self.display_manager.display_image(frame)
            elif hasattr(self.display_manager, 'matrix') and hasattr(self.display_manager.matrix, 'SetImage'):
                 self.display_manager.matrix.SetImage(frame.convert('RGB'))
            else:
                 logging.error("[NHL] DisplayManager missing display_image or matrix.SetImage method.")
            
            self.needs_update = False # Reset flag after successful display attempt

        except Exception as e:
            logging.error(f"[NHL] Error displaying frame via DisplayManager: {e}")
            # Should we set needs_update = True again if display fails?

# ... (rest of the class remains the same) ... 