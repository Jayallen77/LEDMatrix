import os
import time
import freetype
from PIL import Image, ImageDraw
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
        self.logger = logging.getLogger('FontTest')
        
        # Verify font exists
        if not os.path.exists(self.font_path):
            self.logger.error(f"Font file not found: {self.font_path}")
            raise FileNotFoundError(f"Font file not found: {self.font_path}")
        
        # Load the font
        self.face = freetype.Face(self.font_path)
        
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
            
            # Draw font name at the top
            self.display_manager.draw_text("tom-thumb", y=2, color=(255, 255, 255))
            
            # Draw sample text
            draw = ImageDraw.Draw(self.display_manager.image)
            sample_text = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            
            # Calculate starting position
            x = 10  # Start 10 pixels from the left
            y = (height - self.face.size.height) // 2  # Center vertically using font's natural height
            
            # Draw each character
            for char in sample_text:
                # Load the glyph
                self.face.load_char(char)
                bitmap = self.face.glyph.bitmap
                
                # Log bitmap details for debugging
                self.logger.debug(f"Bitmap for '{char}': width={bitmap.width}, rows={bitmap.rows}, pitch={bitmap.pitch}")
                
                # Draw the glyph
                for i in range(bitmap.rows):
                    for j in range(bitmap.width):
                        try:
                            # Get the byte containing the pixel
                            byte_index = i * bitmap.pitch + (j // 8)
                            if byte_index < len(bitmap.buffer):
                                byte = bitmap.buffer[byte_index]
                                # Check if the specific bit is set
                                if byte & (1 << (7 - (j % 8))):
                                    draw.point((x + j, y + i), fill=(255, 255, 255))
                        except IndexError:
                            self.logger.warning(f"Index out of range for char '{char}' at position ({i}, {j})")
                            continue
                
                # Move to next character position
                x += self.face.glyph.advance.x >> 6
            
            # Update the display once
            self.display_manager.update_display()
            
            # Log that display is complete
            self.logger.info("Font test display complete.")
            
        except Exception as e:
            self.logger.error(f"Error displaying font test: {e}", exc_info=True) 