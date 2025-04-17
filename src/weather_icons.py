import os
from PIL import Image, ImageDraw
# math is no longer needed for drawing, remove if not used elsewhere
# import math 

class WeatherIcons:
    ICON_DIR = "assets/weather/"  # Path where PNG icons are stored
    DEFAULT_ICON = "not-available.png"
    DEFAULT_SIZE = 64 # Default size, should match icons but can be overridden

    @staticmethod
    def _get_icon_filename(condition: str) -> str:
        """Maps a weather condition string to an icon filename."""
        condition = condition.lower().strip()
        filename = WeatherIcons.DEFAULT_ICON # Start with default

        # Prioritize more specific conditions based on keywords (order matters)
        if "thunderstorm" in condition or "thunder" in condition or "storm" in condition:
            if "rain" in condition: filename = "thunderstorms-rain.png"
            elif "snow" in condition: filename = "thunderstorms-snow.png"
            else: filename = "thunderstorms.png"
        elif "sleet" in condition: filename = "sleet.png"
        elif "snow" in condition: filename = "snow.png"
        elif "rain" in condition: filename = "rain.png"
        elif "drizzle" in condition: filename = "drizzle.png"
        elif "hail" in condition: filename = "hail.png"
        elif "fog" in condition: filename = "fog.png"
        elif "mist" in condition: filename = "mist.png"
        elif "haze" in condition: filename = "haze.png"
        elif "smoke" in condition: filename = "smoke.png"
        # General sky conditions
        elif "partly cloudy" in condition:
             filename = "partly-cloudy-night.png" if "night" in condition else "partly-cloudy-day.png"
        elif "overcast" in condition: filename = "overcast.png"
        elif "cloudy" in condition: # Catches variations like 'mostly cloudy'
            filename = "cloudy.png"
        elif "clear" in condition or "sunny" in condition:
             filename = "clear-night.png" if "night" in condition else "clear-day.png"

        # Check if the chosen icon file actually exists
        potential_path = os.path.join(WeatherIcons.ICON_DIR, filename)
        if not os.path.exists(potential_path):
            # If the specific icon doesn't exist, print a warning and fall back to the default
            if filename != WeatherIcons.DEFAULT_ICON:
                 print(f"Warning: Specific icon file not found: {potential_path}. Falling back to default.")
                 filename = WeatherIcons.DEFAULT_ICON
            # Check if even the default icon exists
            default_path = os.path.join(WeatherIcons.ICON_DIR, WeatherIcons.DEFAULT_ICON)
            if not os.path.exists(default_path):
                print(f"Error: Default icon file also not found: {default_path}")
                # No icon found, return the default name; load_weather_icon will handle the FileNotFoundError
        
        return filename

    @staticmethod
    def load_weather_icon(condition: str, size: int = DEFAULT_SIZE) -> Image.Image | None:
        """Loads, converts, and resizes the appropriate weather icon. Returns None on failure."""
        filename = WeatherIcons._get_icon_filename(condition)
        icon_path = os.path.join(WeatherIcons.ICON_DIR, filename)

        try:
            # Open image and ensure it's RGBA for transparency handling
            icon_img = Image.open(icon_path).convert("RGBA")

            # Resize if necessary using high-quality downsampling (LANCZOS/ANTIALIAS)
            if icon_img.width != size or icon_img.height != size:
                icon_img = icon_img.resize((size, size), Image.Resampling.LANCZOS)

            return icon_img
        except FileNotFoundError:
            print(f"Error: Icon file not found: {icon_path}")
            # Don't try to load default here, _get_icon_filename already handled fallback logic
            return None
        except Exception as e:
            print(f"Error processing icon {icon_path}: {e}")
            return None

    @staticmethod
    def draw_weather_icon(image: Image.Image, condition: str, x: int, y: int, size: int = DEFAULT_SIZE):
         """Loads the appropriate weather icon and pastes it onto the target PIL Image object."""
         icon_to_draw = WeatherIcons.load_weather_icon(condition, size)
         if icon_to_draw:
             # Paste the icon using its alpha channel as the mask for transparency
             # This ensures transparent parts of the PNG are handled correctly.
             try:
                 image.paste(icon_to_draw, (x, y), icon_to_draw)
             except Exception as e:
                 print(f"Error pasting icon for condition '{condition}' at ({x},{y}): {e}")
         else:
             # Optional: Draw a placeholder if icon loading fails completely
             print(f"Could not load icon for condition '{condition}' to draw at ({x},{y})")
             # Example placeholder: draw a small magenta square
             # placeholder_draw = ImageDraw.Draw(image)
             # placeholder_draw.rectangle([x, y, x + size, y + size], fill=(255, 0, 255))
             pass # Default: do nothing if icon cannot be loaded

    @staticmethod
    def draw_sun(draw: ImageDraw, x: int, y: int, size: int = 16, color: tuple = (255, 200, 0)):
        """Draw a sun icon with rays."""
        center_x = x + size // 2
        center_y = y + size // 2
        radius = size // 3
        
        # Draw main sun circle
        draw.ellipse([
            center_x - radius, center_y - radius,
            center_x + radius, center_y + radius
        ], fill=color)
        
        # Draw rays
        ray_length = size // 4
        for angle in range(0, 360, 45):
            rad = math.radians(angle)
            start_x = center_x + (radius * math.cos(rad))
            start_y = center_y + (radius * math.sin(rad))
            end_x = center_x + ((radius + ray_length) * math.cos(rad))
            end_y = center_y + ((radius + ray_length) * math.sin(rad))
            draw.line([start_x, start_y, end_x, end_y], fill=color, width=2)

    @staticmethod
    def draw_cloud(draw: ImageDraw, x: int, y: int, size: int = 16, color: tuple = (200, 200, 200)):
        """Draw a cloud icon."""
        # Draw multiple circles to form cloud shape
        circle_size = size // 2
        positions = [
            (x + size//4, y + size//3),
            (x + size//2, y + size//3),
            (x + size//3, y + size//6)
        ]
        
        for pos_x, pos_y in positions:
            draw.ellipse([
                pos_x, pos_y,
                pos_x + circle_size, pos_y + circle_size
            ], fill=color)

    @staticmethod
    def draw_rain(draw: ImageDraw, x: int, y: int, size: int = 16):
        """Draw rain icon with cloud and droplets."""
        # Draw cloud first
        WeatherIcons.draw_cloud(draw, x, y, size)
        
        # Draw rain drops
        drop_color = (0, 150, 255)  # Light blue
        drop_length = size // 3
        drop_spacing = size // 4
        
        for i in range(3):
            drop_x = x + size//4 + (i * drop_spacing)
            drop_y = y + size//2
            draw.line([
                drop_x, drop_y,
                drop_x - 2, drop_y + drop_length
            ], fill=drop_color, width=2)

    @staticmethod
    def draw_snow(draw: ImageDraw, x: int, y: int, size: int = 16):
        """Draw snow icon with cloud and snowflakes."""
        # Draw cloud first
        WeatherIcons.draw_cloud(draw, x, y, size)
        
        # Draw snowflakes
        snow_color = (200, 200, 255)  # Light blue-white
        flake_size = size // 6
        flake_spacing = size // 4
        
        for i in range(3):
            center_x = x + size//4 + (i * flake_spacing)
            center_y = y + size//2
            
            # Draw 6-point snowflake
            for angle in range(0, 360, 60):
                rad = math.radians(angle)
                end_x = center_x + (flake_size * math.cos(rad))
                end_y = center_y + (flake_size * math.sin(rad))
                draw.line([center_x, center_y, end_x, end_y], fill=snow_color, width=1)

    @staticmethod
    def draw_thunderstorm(draw: ImageDraw, x: int, y: int, size: int = 16):
        """Draw thunderstorm icon with cloud and lightning."""
        # Draw dark cloud
        WeatherIcons.draw_cloud(draw, x, y, size, color=(100, 100, 100))
        
        # Draw lightning bolt
        lightning_color = (255, 255, 0)  # Yellow
        bolt_points = [
            (x + size//2, y + size//3),
            (x + size//2 - size//4, y + size//2),
            (x + size//2, y + size//2),
            (x + size//2 - size//4, y + size//2 + size//4)
        ]
        draw.line(bolt_points, fill=lightning_color, width=2)

    @staticmethod
    def draw_mist(draw: ImageDraw, x: int, y: int, size: int = 16):
        """Draw mist/fog icon."""
        mist_color = (200, 200, 200)  # Light gray
        wave_height = size // 4
        wave_spacing = size // 3
        
        for i in range(3):
            wave_y = y + size//3 + (i * wave_spacing)
            draw.line([
                x + size//4, wave_y,
                x + size//4 + size//2, wave_y + wave_height
            ], fill=mist_color, width=2) 