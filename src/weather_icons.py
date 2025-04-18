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
        # Normalize the input condition string
        condition = condition.lower().strip()
        print(f"[WeatherIcons] Determining icon for condition: '{condition}'")
        
        filename = WeatherIcons.DEFAULT_ICON # Start with default
        
        # --- Severe / Extreme --- (Checked first)
        if "tornado" in condition: filename = "tornado.png"
        elif "hurricane" in condition: filename = "hurricane.png"
        elif "squall" in condition: filename = "wind.png" # Or potentially extreme.png? Using wind for now.
        elif "extreme" in condition: # Look for combined extreme conditions
            if "thunderstorm" in condition or "thunder" in condition or "storm" in condition:
                if "rain" in condition: filename = "thunderstorms-day-extreme-rain.png" # Default day
                elif "snow" in condition: filename = "thunderstorms-day-extreme-snow.png" # Default day
                else: filename = "thunderstorms-day-extreme.png" # Default day
            elif "rain" in condition: filename = "extreme-rain.png"
            elif "snow" in condition: filename = "extreme-snow.png"
            elif "sleet" in condition: filename = "extreme-sleet.png"
            elif "drizzle" in condition: filename = "extreme-drizzle.png"
            elif "hail" in condition: filename = "extreme-hail.png"
            elif "fog" in condition: filename = "extreme-day-fog.png" # Default day
            elif "haze" in condition: filename = "extreme-day-haze.png" # Default day
            elif "smoke" in condition: filename = "extreme-day-smoke.png" # Default day
            else: filename = "extreme-day.png" # Default day

        # --- Thunderstorms --- 
        elif "thunderstorm" in condition or "thunder" in condition or "storm" in condition:
            if "overcast" in condition:
                if "rain" in condition: filename = "thunderstorms-overcast-rain.png"
                elif "snow" in condition: filename = "thunderstorms-overcast-snow.png"
                else: filename = "thunderstorms-overcast.png"
            # Simple thunderstorm conditions
            elif "rain" in condition: filename = "thunderstorms-day-rain.png" # Default day
            elif "snow" in condition: filename = "thunderstorms-day-snow.png" # Default day
            else: filename = "thunderstorms-day.png" # Default day

        # --- Precipitation --- (Excluding thunderstorms covered above)
        elif "sleet" in condition:
            if "overcast" in condition: filename = "overcast-day-sleet.png" # Default day
            elif "partly cloudy" in condition or "scattered" in condition or "few" in condition or "broken" in condition: # Approximating partly cloudy
                 filename = "partly-cloudy-day-sleet.png" # Default day
            else: filename = "sleet.png"
        elif "snow" in condition:
            if "overcast" in condition: filename = "overcast-day-snow.png" # Default day
            elif "partly cloudy" in condition or "scattered" in condition or "few" in condition or "broken" in condition:
                 filename = "partly-cloudy-day-snow.png" # Default day
            elif "wind" in condition: filename = "wind-snow.png"
            else: filename = "snow.png"
        elif "rain" in condition:
            if "overcast" in condition: filename = "overcast-day-rain.png" # Default day
            elif "partly cloudy" in condition or "scattered" in condition or "few" in condition or "broken" in condition:
                 filename = "partly-cloudy-day-rain.png" # Default day
            else: filename = "rain.png"
        elif "drizzle" in condition:
            if "overcast" in condition: filename = "overcast-day-drizzle.png" # Default day
            elif "partly cloudy" in condition or "scattered" in condition or "few" in condition or "broken" in condition:
                 filename = "partly-cloudy-day-drizzle.png" # Default day
            else: filename = "drizzle.png"
        elif "hail" in condition:
            if "overcast" in condition: filename = "overcast-day-hail.png" # Default day
            elif "partly cloudy" in condition or "scattered" in condition or "few" in condition or "broken" in condition:
                 filename = "partly-cloudy-day-hail.png" # Default day
            else: filename = "hail.png"

        # --- Obscurations (Fog, Mist, Haze, Smoke, Dust, Sand, Ash) ---
        elif "fog" in condition:
            if "overcast" in condition: filename = "overcast-day-fog.png" # Default day
            elif "partly cloudy" in condition or "scattered" in condition or "few" in condition or "broken" in condition:
                 filename = "partly-cloudy-day-fog.png" # Default day
            else: filename = "fog-day.png" # Default day
        elif "mist" in condition: filename = "mist.png"
        elif "haze" in condition:
            if "overcast" in condition: filename = "overcast-day-haze.png" # Default day
            elif "partly cloudy" in condition or "scattered" in condition or "few" in condition or "broken" in condition:
                 filename = "partly-cloudy-day-haze.png" # Default day
            else: filename = "haze-day.png" # Default day
        elif "smoke" in condition:
            if "overcast" in condition: filename = "overcast-day-smoke.png" # Default day
            elif "partly cloudy" in condition or "scattered" in condition or "few" in condition or "broken" in condition:
                 filename = "partly-cloudy-day-smoke.png" # Default day
            else: filename = "smoke.png"
        elif "dust" in condition:
             filename = "dust-day.png" # Default day
        elif "sand" in condition: filename = "dust-day.png" # Map sand to dust (day)
        elif "ash" in condition: filename = "smoke.png" # Map ash to smoke

        # --- Clouds --- (No precipitation, no obscuration)
        elif "overcast" in condition: # Solid cloud cover
             filename = "overcast-day.png" # Default day
        elif "broken clouds" in condition or "scattered clouds" in condition or "partly cloudy" in condition: # Partial cover
             filename = "partly-cloudy-day.png" # Default day
        elif "few clouds" in condition: # Minimal clouds
             filename = "partly-cloudy-day.png" # Use partly cloudy day for few clouds
        elif "clouds" in condition: # Generic cloudy
             filename = "cloudy.png"

        # --- Clear --- 
        elif "clear" in condition or "sunny" in condition:
             filename = "clear-day.png" # Default day

        # --- Wind (if no other condition matched significantly) ---
        elif "wind" in condition: filename = "wind.png"
        
        # --- Final Check --- 
        # Check if the determined filename exists, otherwise use default
        potential_path = os.path.join(WeatherIcons.ICON_DIR, filename)
        if not os.path.exists(potential_path):
            # If a specific icon was determined but not found, log warning and use default
            if filename != WeatherIcons.DEFAULT_ICON:
                print(f"Warning: Determined icon '{filename}' not found at '{potential_path}'. Falling back to default.")
                filename = WeatherIcons.DEFAULT_ICON
            
            # Check if default exists
            default_path = os.path.join(WeatherIcons.ICON_DIR, WeatherIcons.DEFAULT_ICON)
            if not os.path.exists(default_path):
                 print(f"Error: Default icon file also not found: {default_path}")
                 # Allow filename to remain DEFAULT_ICON name, load_weather_icon handles FileNotFoundError

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
             # Create a thresholded mask from the icon's alpha channel
             # to remove faint anti-aliasing pixels when pasting on black bg.
             # Pixels with alpha > 200 will be fully opaque, others fully transparent.
             try:
                 # alpha = icon_to_draw.getchannel('A')
                 # # Apply threshold: lambda function returns 255 if input > 200, else 0
                 # threshold_mask = alpha.point(lambda p: 255 if p > 200 else 0)
                 
                 # Paste the icon using the thresholded mask
                 # image.paste(icon_to_draw, (x, y), threshold_mask)
                 
                 # Paste the icon directly with its original alpha channel
                 image.paste(icon_to_draw, (x, y), icon_to_draw)
             except Exception as e:
                 print(f"Error processing or pasting icon for condition '{condition}' at ({x},{y}): {e}")
                 # Fallback or alternative handling if needed
                 # try:
                 #    # Fallback: Try pasting with original alpha if thresholding fails
                 #    image.paste(icon_to_draw, (x, y), icon_to_draw)
                 # except Exception as e2:
                 #    print(f"Error during fallback paste: {e2}")
                 pass
         else:
             # Optional: Draw a placeholder if icon loading fails completely
             print(f"Could not load icon for condition '{condition}' to draw at ({x},{y})")

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