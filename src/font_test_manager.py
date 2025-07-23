import os
import time
from PIL import Image, ImageDraw, ImageFont
import logging
from typing import Dict, Any
from src.display_manager import DisplayManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FontTestManager:
    """Manager for testing 5x7 regular TTF font."""
    
    def __init__(self, config: Dict[str, Any], display_manager: DisplayManager):
        self.display_manager = display_manager
        self.config = config
        self.font_path = "assets/fonts/5by7.regular.ttf"
        self.logger = logging.getLogger('FontTest')
        
        # Verify font exists
        if not os.path.exists(self.font_path):
            self.logger.error(f"Font file not found: {self.font_path}")
            raise FileNotFoundError(f"Font file not found: {self.font_path}")
        
        # Load the TTF font with PIL
        try:
            self.font = ImageFont.truetype(self.font_path, 7)  # Size 7 for 5x7 font
            self.logger.info(f"Successfully loaded 5x7 regular TTF font from {self.font_path}")
        except Exception as e:
            self.logger.error(f"Failed to load 5x7 TTF font: {e}")
            raise
        
        self.logger.info("Initialized FontTestManager with 5x7 regular TTF font")
    
    def update(self):
        """No update needed for static display."""
        pass
    
    def display(self, force_clear: bool = False):
        """Display the font with sample text."""
        try:
            # Clear the display
            self.display_manager.clear()
            
            # Get display dimensions
            width = self.display_manager.matrix.width
            height = self.display_manager.matrix.height
            
            # Draw font name at the top
            self.display_manager.draw_text("5x7 Regular", y=2, color=(255, 255, 255))
            
            # Draw sample text using TTF font
            draw = ImageDraw.Draw(self.display_manager.image)
            sample_text = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            
            # Calculate starting position
            x = 10  # Start 10 pixels from the left
            y = 10  # Start 10 pixels from the top
            
            # Draw the sample text using PIL's text drawing
            draw.text((x, y), sample_text, font=self.font, fill=(255, 255, 255))
            
            # Update the display once
            self.display_manager.update_display()
            
            # Log that display is complete
            self.logger.info("Font test display complete.")
            
        except Exception as e:
            self.logger.error(f"Error displaying font test: {e}", exc_info=True) 