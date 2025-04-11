from rgbmatrix import RGBMatrix, RGBMatrixOptions
from PIL import Image, ImageDraw, ImageFont
import time
from typing import Dict, Any, List, Tuple
import logging
import math
from .weather_icons import WeatherIcons

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DisplayManager:
    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(DisplayManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._setup_matrix()
        self._load_fonts()
        
    def _setup_matrix(self):
        """Initialize the RGB matrix with configuration settings."""
        options = RGBMatrixOptions()
        
        # Hardware configuration
        hardware_config = self.config.get('hardware', {})
        options.rows = hardware_config.get('rows', 32)
        options.cols = hardware_config.get('cols', 64)
        options.chain_length = hardware_config.get('chain_length', 2)
        options.parallel = hardware_config.get('parallel', 1)
        options.hardware_mapping = hardware_config.get('hardware_mapping', 'adafruit-hat-pwm')
        
        # Optimize display settings for chained panels
        options.brightness = 100
        options.pwm_bits = 11
        options.pwm_lsb_nanoseconds = 200  # Increased for better stability
        options.led_rgb_sequence = 'RGB'
        options.pixel_mapper_config = ''
        options.row_address_type = 0
        options.multiplexing = 0
        options.disable_hardware_pulsing = False  # Enable hardware pulsing for better sync
        options.show_refresh_rate = False
        options.limit_refresh_rate_hz = 60  # Reduced refresh rate for stability
        options.gpio_slowdown = 2  # Increased slowdown for better stability
        
        # Initialize the matrix
        self.matrix = RGBMatrix(options=options)
        
        # Create double buffer for smooth updates
        self.offscreen_canvas = self.matrix.CreateFrameCanvas()
        self.current_canvas = self.matrix.CreateFrameCanvas()
        
        # Create image with full chain width
        self.image = Image.new('RGB', (self.matrix.width, self.matrix.height))
        self.draw = ImageDraw.Draw(self.image)
        
        # Initialize font with Press Start 2P
        try:
            self.font = ImageFont.truetype("assets/fonts/PressStart2P-Regular.ttf", 10)
            logger.info("Initial font loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load initial font: {e}")
            self.font = ImageFont.load_default()
        
        # Draw a test pattern
        self._draw_test_pattern()

    def _draw_test_pattern(self):
        """Draw a test pattern to verify the display is working."""
        self.clear()
        
        # Draw a red rectangle border
        self.draw.rectangle([0, 0, self.matrix.width-1, self.matrix.height-1], outline=(255, 0, 0))
        
        # Draw a diagonal line
        self.draw.line([0, 0, self.matrix.width-1, self.matrix.height-1], fill=(0, 255, 0))
        
        # Draw some text
        self.draw.text((10, 10), "TEST", font=self.font, fill=(0, 0, 255))
        
        # Update the display once after everything is drawn
        self.update_display()
        time.sleep(2)

    def update_display(self):
        """Update the display using double buffering with proper sync."""
        try:
            # Copy the current image to the offscreen canvas   
            self.offscreen_canvas.SetImage(self.image)
            
            # Wait for the next vsync before swapping
            self.matrix.SwapOnVSync(self.offscreen_canvas)
            
            # Swap our canvas references
            self.offscreen_canvas, self.current_canvas = self.current_canvas, self.offscreen_canvas
            
            # Small delay to ensure stable refresh
            time.sleep(0.001)
        except Exception as e:
            logger.error(f"Error updating display: {e}")

    def clear(self):
        """Clear the display completely."""
        try:
            # Create a new black image
            self.image = Image.new('RGB', (self.matrix.width, self.matrix.height))
            self.draw = ImageDraw.Draw(self.image)
            
            # Clear both canvases
            self.offscreen_canvas.Clear()
            self.current_canvas.Clear()
            
            # Update the display to show the clear
            self.update_display()
        except Exception as e:
            logger.error(f"Error clearing display: {e}")

    def _load_fonts(self):
        """Load fonts with proper error handling."""
        try:
            # Load regular font (Press Start 2P)
            self.regular_font = ImageFont.truetype("assets/fonts/PressStart2P-Regular.ttf", 10)
            logger.info("Regular font loaded successfully")
            
            # Load small font (Press Start 2P at smaller size)
            self.small_font = ImageFont.truetype("assets/fonts/PressStart2P-Regular.ttf", 8)
            logger.info("Small font loaded successfully")
            
        except Exception as e:
            logger.error(f"Error in font loading: {e}")
            # Fallback to default font
            self.regular_font = ImageFont.load_default()
            self.small_font = self.regular_font

    def draw_text(self, text: str, x: int = None, y: int = None, color: Tuple[int, int, int] = (255, 255, 255), small_font: bool = False) -> None:
        """Draw text on the display with improved clarity."""
        font = self.small_font if small_font else self.regular_font
        
        # Get text dimensions including ascenders and descenders
        bbox = self.draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # Add padding to prevent cutoff
        padding = 1  # Reduced padding since Press Start 2P has built-in spacing
        
        # Center text horizontally if x not specified
        if x is None:
            x = (self.matrix.width - text_width) // 2
        
        # Center text vertically if y not specified, with padding
        if y is None:
            y = (self.matrix.height - text_height) // 2
        else:
            # Ensure text doesn't get cut off at bottom
            max_y = self.matrix.height - text_height - padding
            y = min(y, max_y)
            y = max(y, padding)  # Ensure text doesn't get cut off at top
        
        # Press Start 2P is pixel-perfect, so we can draw directly without any adjustments
        self.draw.text((x, y), text, font=font, fill=color)

    def draw_sun(self, x: int, y: int, size: int = 16):
        """Draw a sun icon using yellow circles and lines."""
        center = (x + size//2, y + size//2)
        radius = size//3
        
        # Draw the center circle
        self.draw.ellipse([center[0]-radius, center[1]-radius, 
                          center[0]+radius, center[1]+radius], 
                         fill=(255, 255, 0))  # Yellow
        
        # Draw the rays
        ray_length = size//4
        for angle in range(0, 360, 45):
            rad = math.radians(angle)
            start_x = center[0] + (radius * math.cos(rad))
            start_y = center[1] + (radius * math.sin(rad))
            end_x = center[0] + ((radius + ray_length) * math.cos(rad))
            end_y = center[1] + ((radius + ray_length) * math.sin(rad))
            self.draw.line([start_x, start_y, end_x, end_y], fill=(255, 255, 0), width=2)

    def draw_cloud(self, x: int, y: int, size: int = 16, color=(200, 200, 200)):
        """Draw a cloud icon."""
        # Draw multiple circles to form a cloud shape
        self.draw.ellipse([x+size//4, y+size//3, x+size//4+size//2, y+size//3+size//2], fill=color)
        self.draw.ellipse([x+size//2, y+size//3, x+size//2+size//2, y+size//3+size//2], fill=color)
        self.draw.ellipse([x+size//3, y+size//6, x+size//3+size//2, y+size//6+size//2], fill=color)

    def draw_rain(self, x: int, y: int, size: int = 16):
        """Draw rain icon with cloud and droplets."""
        # Draw cloud
        self.draw_cloud(x, y, size)
        
        # Draw rain drops
        drop_color = (0, 0, 255)  # Blue
        drop_size = size//6
        for i in range(3):
            drop_x = x + size//4 + (i * size//3)
            drop_y = y + size//2
            self.draw.line([drop_x, drop_y, drop_x, drop_y+drop_size], 
                          fill=drop_color, width=2)

    def draw_snow(self, x: int, y: int, size: int = 16):
        """Draw snow icon with cloud and snowflakes."""
        # Draw cloud
        self.draw_cloud(x, y, size)
        
        # Draw snowflakes
        snow_color = (200, 200, 255)  # Light blue
        for i in range(3):
            center_x = x + size//4 + (i * size//3)
            center_y = y + size//2 + size//4
            # Draw a small star shape
            for angle in range(0, 360, 60):
                rad = math.radians(angle)
                end_x = center_x + (size//8 * math.cos(rad))
                end_y = center_y + (size//8 * math.sin(rad))
                self.draw.line([center_x, center_y, end_x, end_y], 
                             fill=snow_color, width=1)

    # Weather icon color constants
    WEATHER_COLORS = {
        'sun': (255, 200, 0),    # Bright yellow
        'cloud': (200, 200, 200), # Light gray
        'rain': (0, 100, 255),    # Light blue
        'snow': (220, 220, 255),  # Ice blue
        'storm': (255, 255, 0)    # Lightning yellow
    }

    def _draw_sun(self, x: int, y: int, size: int) -> None:
        """Draw a sun icon with rays."""
        center_x, center_y = x + size//2, y + size//2
        radius = size//4
        ray_length = size//3
        
        # Draw the main sun circle
        self.draw.ellipse([center_x - radius, center_y - radius, 
                          center_x + radius, center_y + radius], 
                         fill=self.WEATHER_COLORS['sun'])
        
        # Draw sun rays
        for angle in range(0, 360, 45):
            rad = math.radians(angle)
            start_x = center_x + int((radius + 2) * math.cos(rad))
            start_y = center_y + int((radius + 2) * math.sin(rad))
            end_x = center_x + int((radius + ray_length) * math.cos(rad))
            end_y = center_y + int((radius + ray_length) * math.sin(rad))
            self.draw.line([start_x, start_y, end_x, end_y], 
                         fill=self.WEATHER_COLORS['sun'], width=2)

    def _draw_cloud(self, x: int, y: int, size: int) -> None:
        """Draw a cloud using multiple circles."""
        cloud_color = self.WEATHER_COLORS['cloud']
        base_y = y + size//2
        
        # Draw main cloud body (3 overlapping circles)
        circle_radius = size//4
        positions = [
            (x + size//3, base_y),           # Left circle
            (x + size//2, base_y - size//6), # Top circle
            (x + 2*size//3, base_y)          # Right circle
        ]
        
        for cx, cy in positions:
            self.draw.ellipse([cx - circle_radius, cy - circle_radius,
                             cx + circle_radius, cy + circle_radius],
                            fill=cloud_color)

    def _draw_rain(self, x: int, y: int, size: int) -> None:
        """Draw rain drops falling from a cloud."""
        self._draw_cloud(x, y, size)
        rain_color = self.WEATHER_COLORS['rain']
        
        # Draw rain drops at an angle
        drop_size = size//8
        drops = [
            (x + size//4, y + 2*size//3),
            (x + size//2, y + 3*size//4),
            (x + 3*size//4, y + 2*size//3)
        ]
        
        for dx, dy in drops:
            # Draw angled rain drops
            self.draw.line([dx, dy, dx - drop_size//2, dy + drop_size],
                         fill=rain_color, width=2)

    def _draw_snow(self, x: int, y: int, size: int) -> None:
        """Draw snowflakes falling from a cloud."""
        self._draw_cloud(x, y, size)
        snow_color = self.WEATHER_COLORS['snow']
        
        # Draw snowflakes
        flake_size = size//6
        flakes = [
            (x + size//4, y + 2*size//3),
            (x + size//2, y + 3*size//4),
            (x + 3*size//4, y + 2*size//3)
        ]
        
        for fx, fy in flakes:
            # Draw a snowflake (six-pointed star)
            for angle in range(0, 360, 60):
                rad = math.radians(angle)
                end_x = fx + int(flake_size * math.cos(rad))
                end_y = fy + int(flake_size * math.sin(rad))
                self.draw.line([fx, fy, end_x, end_y],
                             fill=snow_color, width=1)

    def _draw_storm(self, x: int, y: int, size: int) -> None:
        """Draw a storm cloud with lightning bolt."""
        self._draw_cloud(x, y, size)
        
        # Draw lightning bolt
        bolt_color = self.WEATHER_COLORS['storm']
        bolt_points = [
            (x + size//2, y + size//2),          # Top
            (x + 3*size//5, y + 2*size//3),      # Middle right
            (x + 2*size//5, y + 2*size//3),      # Middle left
            (x + size//2, y + 5*size//6)         # Bottom
        ]
        self.draw.polygon(bolt_points, fill=bolt_color)

    def draw_weather_icon(self, condition: str, x: int, y: int, size: int = 16) -> None:
        """Draw a weather icon based on the condition."""
        if condition.lower() in ['clear', 'sunny']:
            self._draw_sun(x, y, size)
        elif condition.lower() in ['clouds', 'cloudy', 'partly cloudy']:
            self._draw_cloud(x, y, size)
        elif condition.lower() in ['rain', 'drizzle', 'shower']:
            self._draw_rain(x, y, size)
        elif condition.lower() in ['snow', 'sleet', 'hail']:
            self._draw_snow(x, y, size)
        elif condition.lower() in ['thunderstorm', 'storm']:
            self._draw_storm(x, y, size)
        else:
            self._draw_sun(x, y, size)
        # Note: No update_display() here - let the caller handle the update

    def draw_text_with_icons(self, text: str, icons: List[tuple] = None, x: int = None, y: int = None, 
                            color: tuple = (255, 255, 255)):
        """Draw text with weather icons at specified positions."""
        # Draw the text
        self.draw_text(text, x, y, color)
        
        # Draw any icons
        if icons:
            for icon_type, icon_x, icon_y in icons:
                self.draw_weather_icon(icon_type, icon_x, icon_y)
        
        # Update the display once after everything is drawn
        self.update_display()

    def cleanup(self):
        """Clean up resources."""
        self.matrix.Clear()
        # Reset the singleton state when cleaning up
        DisplayManager._instance = None
        DisplayManager._initialized = False 