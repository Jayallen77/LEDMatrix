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
    """Manager for testing tom-thumb font."""
    
    def __init__(self, config: Dict[str, Any], display_manager: DisplayManager):
        self.display_manager = display_manager
        self.config = config
        self.font_path = "assets/fonts/tom-thumb.bdf"
        self.font_size = 8  # Default size for BDF font
        self.logger = logging.getLogger('FontTest')
        
        # Verify font exists
        if not os.path.exists(self.font_path):
            self.logger.error(f"Font file not found: {self.font_path}")
            raise FileNotFoundError(f"Font file not found: {self.font_path}")
        
        self.logger.info("Initialized FontTestManager with tom-thumb font")
    
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
            
            # Load the BDF font
            font = ImageFont.truetype(self.font_path, self.font_size)
            
            # Draw font name at the top
            self.display_manager.draw_text("tom-thumb", y=2, color=(255, 255, 255))
            
            # Draw sample text
            draw = ImageDraw.Draw(self.display_manager.image)
            sample_text = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            
            # Get text dimensions
            bbox = draw.textbbox((0, 0), sample_text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            # Calculate position to center the text
            x = (width - text_width) // 2
            y = (height - text_height) // 2
            
            # Draw the text
            draw.text((x, y), sample_text, font=font, fill=(255, 255, 255))
            
            # Update the display once
            self.display_manager.update_display()
            
            # Log that display is complete
            self.logger.info("Font test display complete.")
            
        except Exception as e:
            self.logger.error(f"Error displaying font test: {e}", exc_info=True) 