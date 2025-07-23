import os
import json
import logging
from datetime import datetime, date
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from rgbmatrix import graphics
import pytz
from src.config_manager import ConfigManager
import time
import freetype

# Configure logger for this module
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class OfTheDayManager:
    def __init__(self, display_manager, config):
        logger.info("Initializing OfTheDayManager")
        self.display_manager = display_manager
        self.config = config
        self.of_the_day_config = config.get('of_the_day', {})
        self.enabled = self.of_the_day_config.get('enabled', False)
        self.update_interval = self.of_the_day_config.get('update_interval', 3600)  # 1 hour default
        self.subtitle_rotate_interval = self.of_the_day_config.get('subtitle_rotate_interval', 10)  # 10 seconds default
        self.display_rotate_interval = self.of_the_day_config.get('display_rotate_interval', 30)  # 30 seconds default
        self.last_update = 0
        self.last_display_log = 0
        self.current_day = None
        self.current_items = {}
        self.current_item_index = 0
        self.current_category_index = 0
        self.last_drawn_category_index = -1
        self.last_drawn_day = None
        self.force_clear = False
        self.rotation_state = 0  # 0 = subtitle, 1 = description
        self.last_rotation_time = time.time()
        self.last_category_rotation_time = time.time()

        # Load fonts using freetype
        font_dir = os.path.join(os.path.dirname(__file__), '..', 'assets', 'fonts')
        self.title_font = freetype.Face(os.path.join(font_dir, 'ic8x8u.bdf'))
        self.body_font = freetype.Face(os.path.join(font_dir, 'MatrixLight6.bdf'))
        
        # Log font properties for debugging
        logger.debug(f"Title font properties: height={self.title_font.size.height}, ascender={self.title_font.size.ascender}, descender={self.title_font.size.descender}")
        logger.debug(f"Body font properties: height={self.body_font.size.height}, ascender={self.body_font.size.ascender}, descender={self.body_font.size.descender}")

        # Load categories and their data
        self.categories = self.of_the_day_config.get('categories', {})
        self.category_order = self.of_the_day_config.get('category_order', [])
        
        # Display properties
        self.title_color = (255, 255, 255)  # White
        self.subtitle_color = (200, 200, 200)  # Light gray
        self.background_color = (0, 0, 0)  # Black
        
        # State management
        self.force_clear = False
        self.last_drawn_category_index = -1
        self.last_drawn_day = None
        
        # Load data files
        self.data_files = {}
        logger.info("Loading data files for OfTheDayManager...")
        self._load_data_files()
        logger.info(f"Loaded {len(self.data_files)} data files: {list(self.data_files.keys())}")
        
        logger.info(f"OfTheDayManager configuration: enabled={self.enabled}, categories={list(self.categories.keys())}")
        
        if self.enabled:
            logger.info("OfTheDayManager is enabled, loading today's items...")
            self._load_todays_items()
            logger.info(f"After loading, current_items has {len(self.current_items)} items: {list(self.current_items.keys())}")
        else:
            logger.warning("OfTheDayManager is disabled in configuration")
    
    def _load_data_files(self):
        """Load all data files for enabled categories."""
        if not self.enabled:
            logger.debug("OfTheDayManager is disabled, skipping data file loading")
            return
            
        logger.info(f"Loading data files for {len(self.categories)} categories")
            
        for category_name, category_config in self.categories.items():
            logger.debug(f"Processing category: {category_name}")
            if not category_config.get('enabled', True):
                logger.debug(f"Skipping disabled category: {category_name}")
                continue
                
            data_file = category_config.get('data_file')
            if not data_file:
                logger.warning(f"No data file specified for category: {category_name}")
                continue
                
            try:
                # Try relative path first, then absolute
                file_path = data_file
                if not os.path.isabs(file_path):
                    # If data_file already contains 'of_the_day/', use it as is
                    if data_file.startswith('of_the_day/'):
                        file_path = os.path.join(os.path.dirname(__file__), '..', data_file)
                    else:
                        file_path = os.path.join(os.path.dirname(__file__), '..', 'of_the_day', data_file)
                
                if os.path.exists(file_path):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        self.data_files[category_name] = json.load(f)
                    logger.info(f"Loaded data file for {category_name}: {len(self.data_files[category_name])} items")
                    logger.debug(f"Sample keys from {category_name}: {list(self.data_files[category_name].keys())[:5]}")
                else:
                    logger.error(f"Data file not found for {category_name}: {file_path}")
                    self.data_files[category_name] = {}
            except Exception as e:
                logger.error(f"Error loading data file for {category_name}: {e}")
                self.data_files[category_name] = {}
    
    def _load_todays_items(self):
        """Load items for today based on the current date."""
        if not self.enabled:
            return
            
        today = date.today()
        day_of_year = today.timetuple().tm_yday
        logger.info(f"Loading items for day {day_of_year} of the year")
        
        self.current_items = {}
        
        for category_name, category_config in self.categories.items():
            if not category_config.get('enabled', True):
                logger.debug(f"Skipping disabled category: {category_name}")
                continue
                
            data = self.data_files.get(category_name, {})
            if not data:
                logger.warning(f"No data loaded for category: {category_name}")
                continue
                
            logger.debug(f"Checking category {category_name} for day {day_of_year}")
            # Get item for today (day of year)
            item = data.get(str(day_of_year))
            if item:
                self.current_items[category_name] = item
                logger.info(f"Loaded {category_name} item for day {day_of_year}: {item.get('title', 'No title')}")
            else:
                logger.warning(f"No item found for {category_name} on day {day_of_year}")
                logger.debug(f"Available days in {category_name}: {list(data.keys())[:10]}...")
        
        self.current_day = today
        self.current_category_index = 0
        self.current_item_index = 0
    
    def update(self, current_time):
        """Update items if needed (daily or on interval)."""
        if not self.enabled:
            logger.debug("OfTheDayManager is disabled, skipping update")
            return
        
        today = date.today()
        
        # Check if we need to load new items (new day or first time)
        if self.current_day != today:
            logger.info("New day detected, loading new items")
            self._load_todays_items()
        
        # Check if we need to update based on interval
        if current_time - self.last_update > self.update_interval:
            logger.debug("OfTheDayManager update interval reached")
            self.last_update = current_time
    
    def _draw_bdf_text(self, draw, face, text, x, y, color=(255,255,255)):
        """Draw text using a BDF font loaded with freetype."""
        orig_x = x
        for char in text:
            face.load_char(char)
            bitmap = face.glyph.bitmap
            # For bottom baseline alignment, we need to position glyphs so their bottoms align
            # bitmap_top gives us the distance from baseline to top of bitmap
            # For bottom alignment, we want the bottom of each glyph at the same y position
            glyph_y = y - bitmap.rows
            for i in range(bitmap.rows):
                for j in range(bitmap.width):
                    byte_index = i * bitmap.pitch + (j // 8)
                    if byte_index < len(bitmap.buffer):
                        byte = bitmap.buffer[byte_index]
                        if byte & (1 << (7 - (j % 8))):
                            draw.point((x + j, glyph_y + i), fill=color)
            x += face.glyph.advance.x >> 6
        return x - orig_x

    def draw_item(self, category_name, item):
        try:
            title = item.get('title', 'No Title')
            subtitle = item.get('subtitle', '')
            description = item.get('description', '')
            draw = ImageDraw.Draw(self.display_manager.image)
            matrix_width = self.display_manager.matrix.width
            matrix_height = self.display_manager.matrix.height
            title_font = self.title_font
            body_font = self.body_font
            
            # Get font heights - simplified
            title_font.load_char('A')
            title_height = title_font.glyph.bitmap.rows
            body_font.load_char('A')
            body_height = body_font.glyph.bitmap.rows
            
            # --- Draw Title (always at top) ---
            title_y = title_height  # Position title so its bottom is at title_height
            self._draw_bdf_text(draw, title_font, title, 1, title_y, color=self.title_color)
            
            # Calculate title width for underline
            title_width = 0
            for c in title:
                title_font.load_char(c)
                title_width += title_font.glyph.advance.x
            title_width = title_width // 64
            
            # Underline below title
            underline_y = title_height + 1
            draw.line([(1, underline_y), (1 + title_width, underline_y)], fill=self.title_color, width=1)

            # --- Draw Subtitle or Description (rotating) ---
            # Start subtitle/description below the title and underline
            # Account for title height + underline + spacing
            y_start = title_height + body_height + 3  # Space for underline
            available_height = matrix_height - y_start
            available_width = matrix_width - 2
            
            if self.rotation_state == 0 and subtitle:
                # Show subtitle
                wrapped = self._wrap_text(subtitle, available_width, body_font, max_lines=3, line_height=body_height, max_height=available_height)
                for i, line in enumerate(wrapped):
                    if line.strip():  # Only draw non-empty lines
                        # Account for bottom baseline alignment - position so bottom of text is at y_start
                        self._draw_bdf_text(draw, body_font, line, 1, y_start + i * body_height, color=self.subtitle_color)
            elif self.rotation_state == 1 and description:
                # Show description
                wrapped = self._wrap_text(description, available_width, body_font, max_lines=3, line_height=body_height, max_height=available_height)
                for i, line in enumerate(wrapped):
                    if line.strip():  # Only draw non-empty lines
                        # Account for bottom baseline alignment - position so bottom of text is at y_start
                        self._draw_bdf_text(draw, body_font, line, 1, y_start + i * body_height, color=self.subtitle_color)
            # else: nothing to show
            return True
        except Exception as e:
            logger.error(f"Error drawing 'of the day' item: {e}", exc_info=True)
            return False

    def _wrap_text(self, text, max_width, face, max_lines=3, line_height=8, max_height=24):
        if not text:
            return [""]
        lines = []
        current_line = []
        words = text.split()
        for word in words:
            test_line = ' '.join(current_line + [word]) if current_line else word
            text_width = 0
            for c in test_line:
                face.load_char(c)
                text_width += face.glyph.advance.x
            text_width = text_width // 64
            if text_width <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                    current_line = [word]
                else:
                    truncated = word
                    while len(truncated) > 0:
                        test_width = 0
                        for c in (truncated + "..."):
                            face.load_char(c)
                            test_width += face.glyph.advance.x
                        test_width = test_width // 64
                        if test_width <= max_width:
                            lines.append(truncated + "...")
                            break
                        truncated = truncated[:-1]
                    if not truncated:
                        lines.append(word[:10] + "...")
            # Check if we've filled all lines (accounting for line spacing)
            if len(lines) * line_height >= max_height or len(lines) >= max_lines:
                break
        if current_line and (len(lines) * line_height < max_height and len(lines) < max_lines):
            lines.append(' '.join(current_line))
        while len(lines) < max_lines:
            lines.append("")
        return lines[:max_lines]
    
    def display(self, force_clear=False):
        if not self.enabled:
            return
        if not self.current_items:
            current_time = time.time()
            if not hasattr(self, 'last_warning_time') or current_time - self.last_warning_time > 10:
                logger.warning(f"OfTheDayManager has no current items.")
                self.last_warning_time = current_time
            return
        now = time.time()
        # Handle subtitle/description rotation
        if now - self.last_rotation_time > self.subtitle_rotate_interval:
            self.rotation_state = (self.rotation_state + 1) % 2
            self.last_rotation_time = now
            # Force redraw
            self.last_drawn_category_index = -1
            self.last_drawn_day = None
        # Handle OTD category rotation
        if now - self.last_category_rotation_time > self.display_rotate_interval:
            # Find the next category with valid data
            original_index = self.current_category_index
            self.current_category_index = (self.current_category_index + 1) % len(self.current_items)
            
            # If we've cycled through all categories and none have data, reset to first
            if self.current_category_index == original_index:
                logger.warning("No categories have valid data, staying on current category")
            else:
                logger.info(f"Rotating from category index {original_index} to {self.current_category_index}")
                logger.info(f"Available categories with data: {list(self.current_items.keys())}")
            
            self.last_category_rotation_time = now
            # Reset subtitle/description rotation when switching category
            self.rotation_state = 0
            self.last_rotation_time = now
            # Force redraw
            self.last_drawn_category_index = -1
            self.last_drawn_day = None
        content_has_changed = self.current_category_index != self.last_drawn_category_index or self.current_day != self.last_drawn_day
        if not content_has_changed and not force_clear:
            return
        try:
            category_names = list(self.current_items.keys())
            if not category_names or self.current_category_index >= len(category_names):
                self.current_category_index = 0
                if not category_names: return
            current_category = category_names[self.current_category_index]
            current_item = self.current_items[current_category]
            current_time = time.time()
            if current_time - self.last_display_log > 5:
                logger.info(f"Displaying {current_category}: {current_item.get('title', 'No Title')}")
                self.last_display_log = current_time
            self.display_manager.clear()
            self.draw_item(current_category, current_item)
            self.display_manager.update_display()
            self.last_drawn_category_index = self.current_category_index
            self.last_drawn_day = self.current_day
        except Exception as e:
            logger.error(f"Error displaying 'of the day' item: {e}", exc_info=True)
    
    def advance_item(self):
        """Advance to the next item. Called by DisplayController when display time is up."""
        if not self.enabled:
            logger.debug("OfTheDayManager is disabled, skipping item advance")
            return
            
        # Check if internal rotation should happen first
        now = time.time()
        if now - self.last_category_rotation_time > self.display_rotate_interval:
            # Let the internal rotation handle it
            logger.debug("Internal rotation timer triggered, skipping external advance")
            return
            
        # Only advance if internal rotation hasn't happened recently
        category_names = list(self.current_items.keys())
        if not category_names:
            return
            
        self.current_category_index += 1
        if self.current_category_index >= len(category_names):
            self.current_category_index = 0
        logger.debug(f"OfTheDayManager advanced to category index {self.current_category_index}") 