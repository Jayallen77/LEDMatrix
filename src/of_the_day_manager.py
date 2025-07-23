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

        # Load fonts
        font_dir = os.path.join(os.path.dirname(__file__), '..', 'assets', 'fonts')
        self.title_font = ImageFont.load_bdf(os.path.join(font_dir, 'ic8x8u.bdf'))
        self.body_font = ImageFont.load_bdf(os.path.join(font_dir, 'cozette.bdf'))

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
            title_height = title_font.getsize('A')[1]
            body_height = body_font.getsize('A')[1]

            # --- Draw Title (always at top, ic8x8u.bdf) ---
            self.display_manager.draw_text(title, 1, 0, color=self.title_color, font=title_font)
            title_width = self.display_manager.get_text_width(title, title_font)
            underline_y = title_height  # Just below the title font
            draw.line([(1, underline_y), (1 + title_width, underline_y)], fill=self.title_color, width=1)

            # --- Draw Subtitle or Description (rotating, cozette.bdf) ---
            available_height = matrix_height - (title_height + 2)
            y_start = title_height + 2
            available_width = matrix_width - 2
            if self.rotation_state == 0 and subtitle:
                # Show subtitle
                wrapped = self._wrap_text(subtitle, available_width, body_font, max_lines=3, line_height=body_height, max_height=available_height)
                for i, line in enumerate(wrapped):
                    self.display_manager.draw_text(line, 1, y_start + i * body_height, color=self.subtitle_color, font=body_font)
            elif self.rotation_state == 1 and description:
                # Show description
                wrapped = self._wrap_text(description, available_width, body_font, max_lines=3, line_height=body_height, max_height=available_height)
                for i, line in enumerate(wrapped):
                    self.display_manager.draw_text(line, 1, y_start + i * body_height, color=self.subtitle_color, font=body_font)
            # else: nothing to show
            return True
        except Exception as e:
            logger.error(f"Error drawing 'of the day' item: {e}", exc_info=True)
            return False

    def _wrap_text(self, text, max_width, font, max_lines=3, line_height=8, max_height=24):
        if not text:
            return [""]
        lines = []
        current_line = []
        words = text.split()
        for word in words:
            test_line = ' '.join(current_line + [word]) if current_line else word
            text_width = self.display_manager.get_text_width(test_line, font)
            if text_width <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                    current_line = [word]
                else:
                    truncated = word
                    while len(truncated) > 0:
                        if self.display_manager.get_text_width(truncated + "...", font) <= max_width:
                            lines.append(truncated + "...")
                            break
                        truncated = truncated[:-1]
                    if not truncated:
                        lines.append(word[:10] + "...")
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
            self.current_category_index = (self.current_category_index + 1) % len(self.current_items)
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
            
        category_names = list(self.current_items.keys())
        if not category_names:
            return
            
        self.current_category_index += 1
        if self.current_category_index >= len(category_names):
            self.current_category_index = 0
        logger.debug(f"OfTheDayManager advanced to category index {self.current_category_index}") 