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
    """Manager for testing different font sizes of PressStart2P-Regular."""
    
    def __init__(self, config: Dict[str, Any], display_manager: DisplayManager):
        self.display_manager = display_manager
        self.config = config
        self.font_path = "assets/fonts/PressStart2P-Regular.ttf"
        self.font_sizes = [4, 6, 8, 10, 12, 14, 16, 18]
        self.current_size_index = 0
        self.display_duration = 3  # Display each size for 3 seconds
        self.last_update = 0
        self.logger = logging.getLogger('FontTest')
        
        # Verify font exists
        if not os.path.exists(self.font_path):
            self.logger.error(f"Font file not found: {self.font_path}")
            raise FileNotFoundError(f"Font file not found: {self.font_path}")
        
        self.logger.info(f"Initialized FontTestManager with {len(self.font_sizes)} font sizes to test")
    
    def update(self):
        """Update the display with the current font size."""
        current_time = time.time()
        
        # Check if it's time to switch to the next font size
        if current_time - self.last_update >= self.display_duration:
            self.current_size_index = (self.current_size_index + 1) % len(self.font_sizes)
            self.last_update = current_time
            self.logger.info(f"Switching to font size: {self.font_sizes[self.current_size_index]}")
    
    def display(self, force_clear: bool = False):
        """Display the current font size test."""
        try:
            # Clear the display
            self.display_manager.clear()
            
            # Get current font size
            current_size = self.font_sizes[self.current_size_index]
            
            # Load the font at the current size
            font = ImageFont.truetype(self.font_path, current_size)
            
            # Create text to display (the size number)
            text = str(current_size)
            
            # Get display dimensions
            width = self.display_manager.matrix.width
            height = self.display_manager.matrix.height
            
            # Get text dimensions
            draw = ImageDraw.Draw(self.display_manager.image)
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            # Calculate position to center the text
            x = (width - text_width) // 2
            y = (height - text_height) // 2
            
            # Draw the text
            draw.text((x, y), text, font=font, fill=(255, 255, 255))
            
            # Update the display
            self.display_manager.update_display()
            
        except Exception as e:
            self.logger.error(f"Error displaying font test: {e}", exc_info=True) 