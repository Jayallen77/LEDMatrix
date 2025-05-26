import logging
import time
from PIL import ImageFont, Image, ImageDraw
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
        
        self.text_pixel_width = 0 # Authoritative width of the text
        self.text_image_cache = None # For pre-rendered text

        self._regenerate_renderings() # Initial creation of cache and width calculation
        
        self.scroll_pos = 0.0 # Use float for precision
        self.last_update_time = time.time()
        self.scroll_speed = self.config.get('scroll_speed', 30) # Pixels per second

    def _regenerate_renderings(self):
        """Calculate text width and attempt to create/update the text image cache."""
        if not self.text or not self.font:
            self.text_pixel_width = 0
            self.text_image_cache = None
            return

        # Always calculate the authoritative text width
        try:
            self.text_pixel_width = self.display_manager.get_text_width(self.text, self.font)
        except Exception as e:
            logger.error(f"Error calculating text width: {e}")
            self.text_pixel_width = 0
            self.text_image_cache = None
            return
            
        self._create_text_image_cache()
        self.scroll_pos = 0 # Reset scroll position when text changes

    def _create_text_image_cache(self):
        """Pre-render the text onto an image if using a TTF font."""
        self.text_image_cache = None # Clear previous cache

        if not self.text or not self.font or self.text_pixel_width == 0:
            return

        if isinstance(self.font, freetype.Face):
            logger.info("TextDisplay: Pre-rendering cache is not used for BDF/freetype fonts. Will use direct drawing.")
            return

        # --- TTF Caching Path ---
        try:
            # Use a dummy image to get accurate text bounding box for vertical centering
            dummy_img = Image.new('RGB', (1, 1))
            dummy_draw = ImageDraw.Draw(dummy_img)
            # Pillow's textbbox gives (left, top, right, bottom) relative to anchor (0,0)
            bbox = dummy_draw.textbbox((0, 0), self.text, font=self.font)
            actual_text_render_height = bbox[3] - bbox[1] # The actual height of the pixels of the text
            # bbox[1] is the y-offset from the drawing point (where text is anchored) to the top of the text.

            cache_width = self.text_pixel_width
            cache_height = self.display_manager.matrix.height # Cache is always full panel height

            self.text_image_cache = Image.new('RGB', (cache_width, cache_height), self.bg_color)
            draw_cache = ImageDraw.Draw(self.text_image_cache)

            # Calculate y-position to draw the text on the cache for vertical centering.
            # The drawing point for PIL's draw.text is typically the baseline.
            # y_draw_on_cache = (desired_top_edge_of_text_on_cache) - bbox[1]
            desired_top_edge = (cache_height - actual_text_render_height) // 2
            y_draw_on_cache = desired_top_edge - bbox[1]
            
            draw_cache.text((0, y_draw_on_cache), self.text, font=self.font, fill=self.text_color)
            logger.info(f"TextDisplay: Created text cache for '{self.text[:30]}...' (TTF). Size: {cache_width}x{cache_height}")
        except Exception as e:
            logger.error(f"TextDisplay: Failed to create text image cache: {e}", exc_info=True)
            self.text_image_cache = None

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
            # This method is now largely superseded by _regenerate_renderings setting self.text_pixel_width
            # Kept for potential direct calls or clarity, but should rely on self.text_pixel_width
            return self.display_manager.get_text_width(self.text, self.font)
        except Exception as e:
            logger.error(f"Error calculating text width: {e}")
            return 0 # Default to 0 if calculation fails

    def update(self):
        """Update scroll position if scrolling is enabled."""
        if not self.scroll_enabled or self.text_pixel_width <= self.display_manager.matrix.width:
            self.scroll_pos = 0.0 # Reset if not scrolling or text fits
            return

        current_time = time.time()
        delta_time = current_time - self.last_update_time
        self.last_update_time = current_time

        scroll_delta = delta_time * self.scroll_speed
        self.scroll_pos += scroll_delta

        # Reset scroll position
        if self.text_image_cache: # Using cached image, scroll_pos is offset into cache
            # Loop smoothly over the cached image width
            if self.scroll_pos >= self.text_pixel_width:
                self.scroll_pos %= self.text_pixel_width 
        else: # Not using cache (e.g., BDF), original scroll logic for off-screen reset
            # Reset when text fully scrolled past left edge + matrix width padding (appearance of starting from right)
            if self.scroll_pos > self.text_pixel_width + self.display_manager.matrix.width:
                self.scroll_pos = 0.0
            
    def display(self):
        """Draw the text onto the display manager's canvas."""
        dm = self.display_manager
        matrix_width = dm.matrix.width
        matrix_height = dm.matrix.height

        # Create a new image and draw context for the display manager for this frame
        # Fill with background color. If cache is used, it also has bg color, so this is fine.
        dm.image = Image.new('RGB', (matrix_width, matrix_height), self.bg_color)
        dm.draw = ImageDraw.Draw(dm.image) # dm.draw needed for fallback path
        
        if not self.text or self.text_pixel_width == 0:
            dm.update_display() # Display empty background
            return

        # Attempt to use pre-rendered cache for scrolling TTF fonts
        if self.text_image_cache and self.scroll_enabled and self.text_pixel_width > matrix_width:
            current_scroll_int = int(self.scroll_pos)
            
            source_x1 = current_scroll_int
            source_x2 = current_scroll_int + matrix_width

            if source_x2 <= self.text_pixel_width:
                # Normal case: Paste single crop from cache
                segment = self.text_image_cache.crop((source_x1, 0, source_x2, matrix_height))
                dm.image.paste(segment, (0, 0))
            else:
                # Wrap-around case: Paste two parts from cache for seamless loop
                width1 = self.text_pixel_width - source_x1
                if width1 > 0: # Should always be true if source_x2 > self.text_pixel_width
                    segment1 = self.text_image_cache.crop((source_x1, 0, self.text_pixel_width, matrix_height))
                    dm.image.paste(segment1, (0, 0))
                
                remaining_width_for_screen = matrix_width - width1
                if remaining_width_for_screen > 0:
                    segment2 = self.text_image_cache.crop((0, 0, remaining_width_for_screen, matrix_height))
                    # Paste segment2 at the correct x-offset on the screen
                    dm.image.paste(segment2, (width1 if width1 > 0 else 0, 0))
        else:
            # Fallback to direct drawing (e.g., BDF, static text, or text fits screen)
            # Calculate Y position (center vertically) - original logic
            # This part needs to be robust for both BDF and TTF (when not cached)
            final_y_for_draw = 0
            try:
                if isinstance(self.font, freetype.Face):
                    text_render_height = self.font.size.height >> 6 
                    final_y_for_draw = (matrix_height - text_render_height) // 2
                else: # PIL TTF Font
                    # Use dm.draw for live textbbox calculation on the current frame's draw context
                    pil_bbox = dm.draw.textbbox((0, 0), self.text, font=self.font)
                    text_render_height = pil_bbox[3] - pil_bbox[1] 
                    final_y_for_draw = (matrix_height - text_render_height) // 2 - pil_bbox[1] # Adjust for PIL's baseline
            except Exception as e:
                 logger.warning(f"TextDisplay: Could not calculate text height accurately for direct drawing: {e}. Using y=0.", exc_info=True)
                 final_y_for_draw = 0

            if self.scroll_enabled and self.text_pixel_width > matrix_width:
                # Scrolling text (direct drawing path, e.g., for BDF or if cache failed)
                # This x calculation makes text appear from right and scroll left
                x_draw_pos = matrix_width - int(self.scroll_pos)
                dm.draw_text(
                    text=self.text, x=x_draw_pos, y=final_y_for_draw,
                    color=self.text_color, font=self.font
                )
            else:
                # Static text (centered horizontally)
                x_draw_pos = (matrix_width - self.text_pixel_width) // 2
                dm.draw_text(
                    text=self.text, x=x_draw_pos, y=final_y_for_draw,
                    color=self.text_color, font=self.font
                )
            
        dm.update_display()

    # Add setters to regenerate cache if properties change
    def set_text(self, new_text: str):
        self.text = new_text
        self._regenerate_renderings()

    def set_font(self, font_path: str, font_size: int):
        self.font_path = font_path
        self.font_size = font_size
        self.font = self._load_font()
        self._regenerate_renderings()

    def set_color(self, text_color: tuple, bg_color: tuple):
        self.text_color = text_color
        self.bg_color = bg_color
        # Background color change requires cache regeneration
        # Text color is part of cache, so also regenerate.
        self._regenerate_renderings()

    def set_scroll_enabled(self, enabled: bool):
        self.scroll_enabled = enabled
        self.scroll_pos = 0.0 # Reset scroll when state changes
        # No need to regenerate cache, just affects display logic

    def set_scroll_speed(self, speed: float):
        self.scroll_speed = speed
        # No need to regenerate cache

