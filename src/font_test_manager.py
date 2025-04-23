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
    """Manager for testing different font sizes of multiple fonts."""
    
    def __init__(self, config: Dict[str, Any], display_manager: DisplayManager):
        self.display_manager = display_manager
        self.config = config
        self.fonts = {
            "4x6": "assets/fonts/4x6-font.ttf",
            "MatrixChunky6": "assets/fonts/MatrixChunky6.ttf"
        }
        self.font_sizes = [6, 8, 10, 12, 14, 16, 18, 20]
        self.logger = logging.getLogger('FontTest')
        
        # Verify fonts exist
        for font_name, font_path in self.fonts.items():
            if not os.path.exists(font_path):
                self.logger.error(f"Font file not found: {font_path}")
                raise FileNotFoundError(f"Font file not found: {font_path}")
        
        self.logger.info(f"Initialized FontTestManager with {len(self.font_sizes)} font sizes to test using {len(self.fonts)} fonts")
    
    def update(self):
        """No update needed for static display."""
        pass
    
    def display(self, force_clear: bool = False):
        """Display all font sizes at once across the screen for each font."""
        try:
            # Clear the display
            self.display_manager.clear()
            
            # Get display dimensions
            width = self.display_manager.matrix.width
            height = self.display_manager.matrix.height
            
            # Calculate spacing between font sizes
            total_sizes = len(self.font_sizes)
            spacing = width // (total_sizes + 1)  # Add 1 to account for edges
            
            # Draw each font
            draw = ImageDraw.Draw(self.display_manager.image)
            
            for font_name, font_path in self.fonts.items():
                # Draw font name at the top
                font_name_y = 2 if font_name == "4x6" else height - 10
                self.display_manager.draw_text(font_name, y=font_name_y, color=(255, 255, 255))
                
                # Draw each font size
                for i, size in enumerate(self.font_sizes):
                    # Load the font at the current size
                    font = ImageFont.truetype(font_path, size)
                    
                    # Create text to display (the size number)
                    text = str(size)
                    
                    # Get text dimensions
                    bbox = draw.textbbox((0, 0), text, font=font)
                    text_width = bbox[2] - bbox[0]
                    text_height = bbox[3] - bbox[1]
                    
                    # Calculate position to center the text horizontally
                    x = spacing * (i + 1) - (text_width // 2)
                    # Position vertically based on font type
                    y = 10 if font_name == "4x6" else height - 20
                    
                    # Draw the text
                    draw.text((x, y), text, font=font, fill=(255, 255, 255))
            
            # Update the display once
            self.display_manager.update_display()
            
            # Log that display is complete
            self.logger.info("Font size test display complete. All sizes shown at once.")
            
        except Exception as e:
            self.logger.error(f"Error displaying font test: {e}", exc_info=True) 