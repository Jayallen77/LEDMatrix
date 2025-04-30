import logging
import time
from PIL import ImageFont
import freetype
import os

from .display_manager import DisplayManager

logger = logging.getLogger(__name__)

class TextDisplay:
    def __init__(self, display_manager: DisplayManager, config: dict):
        self.display_manager = display_manager
        self.config = config.get('text_display', {})
        
        self.text = self.config.get('text', "Hello, World!")
        self.font_path = self.config.get('font_path', "assets/fonts/PressStart2P-Regular.ttf")
        self.font_size = self.config.get('font_size', 8)
        self.scroll_enabled = self.config.get('scroll', False)
        self.text_color = tuple(self.config.get('text_color', [255, 255, 255]))
        self.bg_color = tuple(self.config.get('background_color', [0, 0, 0]))

        self.font = self._load_font()
        self.text_width = self._calculate_text_width()
        
        self.scroll_pos = 0
        self.last_update_time = time.time()
        self.scroll_speed = self.config.get('scroll_speed', 30) # Pixels per second

    def _load_font(self):
        """Load the specified font file (TTF or BDF)."""
        font_path = self.font_path
        # Try to resolve relative path from project root
        if not os.path.isabs(font_path) and not font_path.startswith('assets/'):
             # Assuming relative paths are relative to the project root
             # Adjust this logic if paths are relative to src or config
             base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
             font_path = os.path.join(base_path, font_path)

        elif not os.path.isabs(font_path) and font_path.startswith('assets/'):
             # Assuming 'assets/' path is relative to project root
             base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
             font_path = os.path.join(base_path, font_path)


        logger.info(f"Attempting to load font: {font_path} at size {self.font_size}")
        
        if not os.path.exists(font_path):
            logger.error(f"Font file not found: {font_path}. Falling back to default.")
            return self.display_manager.regular_font # Use default from DisplayManager

        try:
            if font_path.lower().endswith('.ttf'):
                font = ImageFont.truetype(font_path, self.font_size)
                logger.info(f"Loaded TTF font: {self.font_path}")
                return font
            elif font_path.lower().endswith('.bdf'):
                # Use freetype for BDF fonts
                face = freetype.Face(font_path)
                # BDF fonts often have fixed sizes, freetype handles this
                # We might need to adjust how size is used or interpreted for BDF
                face.set_pixel_sizes(0, self.font_size) 
                logger.info(f"Loaded BDF font: {self.font_path} with freetype")
                return face 
            else:
                logger.warning(f"Unsupported font type: {font_path}. Falling back.")
                return self.display_manager.regular_font
        except Exception as e:
            logger.error(f"Failed to load font {font_path}: {e}", exc_info=True)
            return self.display_manager.regular_font

    def _calculate_text_width(self):
        """Calculate the pixel width of the text with the loaded font."""
        try:
            return self.display_manager.get_text_width(self.text, self.font)
        except Exception as e:
            logger.error(f"Error calculating text width: {e}")
            return 0 # Default to 0 if calculation fails

    def update(self):
        """Update scroll position if scrolling is enabled."""
        if not self.scroll_enabled or self.text_width <= self.display_manager.matrix.width:
            self.scroll_pos = 0 # Reset if not scrolling or text fits
            return

        current_time = time.time()
        delta_time = current_time - self.last_update_time
        self.last_update_time = current_time

        # Calculate scroll distance
        scroll_delta = delta_time * self.scroll_speed
        self.scroll_pos += scroll_delta

        # Reset scroll position when the text has scrolled completely off screen
        # Add some padding (e.g., matrix width) before resetting
        if self.scroll_pos > self.text_width + self.display_manager.matrix.width:
            self.scroll_pos = 0 # Reset to start from the right edge again
            
    def display(self):
        """Draw the text onto the display manager's canvas."""
        self.display_manager.draw.rectangle(
            (0, 0, self.display_manager.matrix.width, self.display_manager.matrix.height),
            fill=self.bg_color
        )

        matrix_width = self.display_manager.matrix.width
        matrix_height = self.display_manager.matrix.height

        # Calculate Y position (center vertically)
        # This might need adjustment depending on font metrics
        try:
            if isinstance(self.font, freetype.Face):
                # Estimate height for freetype (BDF)
                 # Using ascender/descender might be more accurate if available
                text_height = self.font.size.height >> 6 
            else:
                # Use PIL's textbbox for TTF height
                bbox = self.display_manager.draw.textbbox((0, 0), self.text, font=self.font)
                text_height = bbox[3] - bbox[1] 
            
            y = (matrix_height - text_height) // 2
            # Adjust y based on baseline for PIL fonts if needed
            if not isinstance(self.font, freetype.Face):
                 # Small adjustment often needed for PIL's draw.text
                 y -= bbox[1] # Subtract the top bearing

        except Exception as e:
             logger.warning(f"Could not calculate text height accurately: {e}. Using default.")
             y = 0 # Default to top

        if self.scroll_enabled and self.text_width > matrix_width:
            # Scrolling text
            x = matrix_width - int(self.scroll_pos)
            
            # Draw text using display_manager's draw_text method
            self.display_manager.draw_text(
                text=self.text,
                x=x,
                y=y,
                color=self.text_color,
                font=self.font # Pass the specific font instance
            )
        else:
            # Static text (centered horizontally)
            x = (matrix_width - self.text_width) // 2
            self.display_manager.draw_text(
                 text=self.text,
                 x=x,
                 y=y,
                 color=self.text_color,
                 font=self.font # Pass the specific font instance
            )
            # No need to call update_display here, controller should handle it after calling display
        
        # Reset scroll position for next time if not scrolling
        # self.last_update_time = time.time() # Reset time tracking if static

