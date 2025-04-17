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

# --- Constants ---
CONFIG_FILE = Path("../config/config.json") # Correct path relative to src/
# Default values in case config loading fails
DEFAULT_DISPLAY_WIDTH = 64
DEFAULT_DISPLAY_HEIGHT = 32
DEFAULT_NHL_ENABLED = False
DEFAULT_FAVORITE_TEAMS = []
DEFAULT_NHL_TEST_MODE = False
DEFAULT_UPDATE_INTERVAL = 60
DEFAULT_LOGO_DIR = Path("../assets/sports/nhl_logos") # Relative to src/
DEFAULT_TEST_DATA_FILE = Path("../test_nhl_data.json") # Relative to src/
DEFAULT_OUTPUT_IMAGE_FILE = Path("../nhl_scorebug_output.png") # Relative to src/
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
    global DISPLAY_WIDTH, DISPLAY_HEIGHT, NHL_ENABLED, FAVORITE_TEAMS, TEST_MODE, UPDATE_INTERVAL_SECONDS, LOGO_DIR, TEST_DATA_FILE, OUTPUT_IMAGE_FILE, LOCAL_TIMEZONE, SHOW_ONLY_FAVORITES

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
        SHOW_ONLY_FAVORITES = nhl_config.get("show_only_favorites", DEFAULT_NHL_SHOW_ONLY_FAVORITES)

        logging.info("Configuration loaded successfully.")
        logging.info(f"Display: {DISPLAY_WIDTH}x{DISPLAY_HEIGHT}")
        logging.info(f"NHL Enabled: {NHL_ENABLED}")
        logging.info(f"Favorite Teams: {FAVORITE_TEAMS}")
        logging.info(f"Test Mode: {TEST_MODE}")
        logging.info(f"Update Interval: {UPDATE_INTERVAL_SECONDS}s")
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

            # --- Display Output (Simulation) ---
            try:
                # Ensure OUTPUT_IMAGE_FILE is used
                scorebug_image.save(OUTPUT_IMAGE_FILE)
                logging.info(f"Scorebug image saved to {OUTPUT_IMAGE_FILE.name}")
            except Exception as e:
                logging.error(f"Failed to save scorebug image: {e}")

            # Add your actual display update logic here
            # matrix.SetImage(scorebug_image.convert('RGB'))

        else:
            logging.warning("No data received, skipping update cycle.")
            # Optionally display an error message on the matrix
            # You might want to create and display a specific error image here too
            error_image = create_scorebug_image(None) # Or a custom error message
            try:
                error_image.save(OUTPUT_IMAGE_FILE)
            except Exception as e:
                 logging.error(f"Failed to save error image: {e}")

        logging.debug(f"Sleeping for {UPDATE_INTERVAL_SECONDS} seconds...")
        time.sleep(UPDATE_INTERVAL_SECONDS)


if __name__ == "__main__":
    main() 