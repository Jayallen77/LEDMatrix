#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.display_manager import DisplayManager
from src.config_manager import ConfigManager
from PIL import Image, ImageDraw
import freetype

def test_matrix_light6_font():
    """Test the MatrixLight6 font rendering."""
    print("Testing MatrixLight6 font rendering...")
    
    # Load config
    config_manager = ConfigManager()
    config = config_manager.get_config()
    
    # Initialize display manager
    display_manager = DisplayManager(config)
    
    # Test if the font was loaded
    if hasattr(display_manager, 'matrix_light6_font'):
        print(f"MatrixLight6 font loaded: {type(display_manager.matrix_light6_font)}")
        if isinstance(display_manager.matrix_light6_font, freetype.Face):
            print(f"Font size: {display_manager.matrix_light6_font.size.height >> 6} pixels")
        else:
            print("Font is not a FreeType face")
    else:
        print("MatrixLight6 font not found")
        return
    
    # Test text rendering
    test_text = "45 / 67"
    print(f"Testing text: '{test_text}'")
    
    # Create a test image
    image = Image.new('RGB', (display_manager.matrix.width, display_manager.matrix.height))
    draw = ImageDraw.Draw(image)
    
    # Try to render the text using the BDF font
    try:
        # Calculate width
        text_width = display_manager.get_text_width(test_text, display_manager.matrix_light6_font)
        print(f"Calculated width: {text_width}")
        
        # Calculate position (center)
        x = (display_manager.matrix.width - text_width) // 2
        y = 10
        
        print(f"Drawing at position: ({x}, {y})")
        
        # Draw the text
        display_manager._draw_bdf_text(test_text, x, y, (255, 255, 255), display_manager.matrix_light6_font)
        
        # Update the display
        display_manager.image = image
        display_manager.update_display()
        
        print("Text should be displayed on the matrix")
        
    except Exception as e:
        print(f"Error rendering text: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_matrix_light6_font() 