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
        self.last_update = 0
        self.last_display_log = 0
        self.current_day = None
        self.current_items = {}
        self.current_item_index = 0
        self.current_category_index = 0
        
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
        """Draw a single 'of the day' item."""
        try:
            title = item.get('title', 'No Title')
            subtitle = item.get('subtitle', '')
            description = item.get('description', '')
            font = self.display_manager.calendar_font
            draw = ImageDraw.Draw(self.display_manager.image)
            line_height = 8  # For 7px font

            # --- Title and Subtitle Drawing (Top Aligned) ---

            # 1. Draw Title
            self.display_manager.draw_text(title, 1, 0, color=self.title_color, font=font)

            # 2. Underline Title Only
            title_width = self.display_manager.get_text_width(title, font)
            underline_y = 7  # Just below the 7px high font
            draw.line([(1, underline_y), (1 + title_width, underline_y)], fill=self.title_color, width=1)

            # 3. Draw Subtitle, starting on the same line as the title
            if subtitle:
                current_x = 1 + title_width
                separator = " - "
                
                # Draw separator if it fits
                if current_x + self.display_manager.get_text_width(separator, font) < self.display_manager.matrix.width:
                    self.display_manager.draw_text(separator, current_x, 0, color=self.subtitle_color, font=font)
                    current_x += self.display_manager.get_text_width(separator, font)

                    # Wrap the rest of the subtitle
                    available_width_line1 = self.display_manager.matrix.width - current_x
                    words = subtitle.split(' ')
                    
                    line1_words = []
                    while words:
                        word = words.pop(0)
                        test_line = ' '.join(line1_words + [word])
                        if self.display_manager.get_text_width(test_line, font) <= available_width_line1:
                            line1_words.append(word)
                        else:
                            words.insert(0, word) # Put word back
                            break
                    
                    if line1_words:
                        self.display_manager.draw_text(' '.join(line1_words), current_x, 0, color=self.subtitle_color, font=font)

                    # Draw remaining words on the next line
                    if words:
                        remaining_text = ' '.join(words)
                        wrapped_line2 = self._wrap_text(remaining_text, self.display_manager.matrix.width - 2, font, max_lines=1)
                        if wrapped_line2 and wrapped_line2[0]:
                             self.display_manager.draw_text(wrapped_line2[0], 1, line_height, color=self.subtitle_color, font=font)
                else:
                    # If even the separator doesn't fit, wrap the whole subtitle on the next line
                    wrapped_subtitle = self._wrap_text(subtitle, self.display_manager.matrix.width - 2, font, max_lines=2)
                    for i, line in enumerate(wrapped_subtitle):
                        if line.strip():
                            self.display_manager.draw_text(line, 1, (i + 1) * line_height, color=self.subtitle_color, font=font)

            # --- Description Drawing (Bottom Aligned) ---
            if description:
                available_width = self.display_manager.matrix.width - 2
                wrapped_lines = self._wrap_text(description, available_width, font, max_lines=3)
                
                num_lines = len([line for line in wrapped_lines if line.strip()])
                total_description_height = num_lines * line_height
                start_y = self.display_manager.matrix.height - total_description_height
                
                for i, line in enumerate(wrapped_lines):
                    if line.strip():
                        self.display_manager.draw_text(line, 1, start_y + (i * line_height), 
                                                    color=self.subtitle_color,
                                                    font=font)
            
            return True
        except Exception as e:
            logger.error(f"Error drawing 'of the day' item: {e}", exc_info=True)
            return False
    
    def _wrap_text(self, text, max_width, font, max_lines=2):
        """Wrap text to fit within max_width using the provided font."""
        if not text:
            return [""]
            
        lines = []
        current_line = []
        words = text.split()
        
        for word in words:
            # Try adding the word to the current line
            test_line = ' '.join(current_line + [word]) if current_line else word
            text_width = self.display_manager.get_text_width(test_line, font)
            
            if text_width <= max_width:
                # Word fits, add it to current line
                current_line.append(word)
            else:
                # Word doesn't fit, start a new line
                if current_line:
                    lines.append(' '.join(current_line))
                    current_line = [word]
                else:
                    # Single word too long, truncate it
                    truncated = word
                    while len(truncated) > 0:
                        if self.display_manager.get_text_width(truncated + "...", font) <= max_width:
                            lines.append(truncated + "...")
                            break
                        truncated = truncated[:-1]
                    if not truncated:
                        lines.append(word[:10] + "...")
            
            # Check if we've filled all lines
            if len(lines) >= max_lines:
                break
        
        # Handle any remaining text in current_line
        if current_line and len(lines) < max_lines:
            remaining_text = ' '.join(current_line)
            if len(words) > len(current_line):  # More words remain
                # Try to fit with ellipsis
                while len(remaining_text) > 0:
                    if self.display_manager.get_text_width(remaining_text + "...", font) <= max_width:
                        lines.append(remaining_text + "...")
                        break
                    remaining_text = remaining_text[:-1]
            else:
                lines.append(remaining_text)
        
        # Ensure we have exactly max_lines
        while len(lines) < max_lines:
            lines.append("")
            
        return lines[:max_lines]
    
    def display(self, force_clear=False):
        """Display 'of the day' items on the LED matrix, only updating when content changes."""
        if not self.enabled:
            return # Manager is disabled
        if not self.current_items:
            # Throttle warning to once every 10 seconds
            current_time = time.time()
            if not hasattr(self, 'last_warning_time') or current_time - self.last_warning_time > 10:
                logger.warning(f"OfTheDayManager has no current items.")
                self.last_warning_time = current_time
            return

        # Check if a redraw is necessary
        content_has_changed = self.current_category_index != self.last_drawn_category_index or self.current_day != self.last_drawn_day
        if not content_has_changed and not force_clear:
            return # Nothing to update, so we exit early

        try:
            # Get current category and item
            category_names = list(self.current_items.keys())
            if not category_names or self.current_category_index >= len(category_names):
                self.current_category_index = 0
                if not category_names: return

            current_category = category_names[self.current_category_index]
            current_item = self.current_items[current_category]

            # Log the new item being displayed (throttled)
            current_time = time.time()
            if current_time - self.last_display_log > 5:
                logger.info(f"Displaying {current_category}: {current_item.get('title', 'No Title')}")
                self.last_display_log = current_time
            
            # A redraw is needed, so first clear the canvas
            self.display_manager.clear()

            # Draw the item
            self.draw_item(current_category, current_item)
            
            # Update the physical display
            self.display_manager.update_display()

            # Cache the state of what was just drawn
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