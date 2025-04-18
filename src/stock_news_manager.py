import time
import logging
import requests
import json
import random
from typing import Dict, Any, List, Tuple
from datetime import datetime
import os
import urllib.parse
import re
from src.config_manager import ConfigManager
from PIL import Image, ImageDraw

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StockNewsManager:
    def __init__(self, config: Dict[str, Any], display_manager):
        self.config = config
        self.config_manager = ConfigManager()
        self.display_manager = display_manager
        self.stocks_config = config.get('stocks', {})
        self.stock_news_config = config.get('stock_news', {})
        self.last_update = 0
        self.news_data = {}
        self.current_news_group = 0  # Track which group of headlines we're showing
        self.scroll_position = 0
        self.cached_text_image = None  # Cache for the text image
        self.cached_text = None  # Cache for the text string

        
        # Get scroll settings from config with faster defaults
        self.scroll_speed = self.stock_news_config.get('scroll_speed', 1)
        self.scroll_delay = self.stock_news_config.get('scroll_delay', 0.001)  # Default to 1ms instead of 50ms
        
        # Log the actual values being used
        logger.info(f"Scroll settings - Speed: {self.scroll_speed} pixels/frame, Delay: {self.scroll_delay*1000:.2f}ms")
        
        # Initialize frame rate tracking
        self.frame_count = 0
        self.last_frame_time = time.time()
        self.last_fps_log_time = time.time()
        self.frame_times = []  # Keep track of recent frame times for average FPS
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        # Initialize with first update
        self.update_news_data()
        
    def _fetch_news_for_symbol(self, symbol: str) -> List[Dict[str, Any]]:
        """Fetch news headlines for a stock symbol."""
        try:
            # Using Yahoo Finance API to get news
            encoded_symbol = urllib.parse.quote(symbol)
            url = f"https://query1.finance.yahoo.com/v1/finance/search?q={encoded_symbol}&lang=en-US&region=US&quotesCount=0&newsCount={self.stock_news_config.get('max_headlines_per_symbol', 5)}"
            
            response = requests.get(url, headers=self.headers, timeout=5)
            if response.status_code != 200:
                logger.error(f"Failed to fetch news for {symbol}: HTTP {response.status_code}")
                return []
                
            data = response.json()
            news_items = data.get('news', [])
            
            # Process and format news items
            formatted_news = []
            for item in news_items:
                formatted_news.append({
                    "title": item.get('title', ''),
                    "publisher": item.get('publisher', ''),
                    "link": item.get('link', ''),
                    "published": item.get('providerPublishTime', 0)
                })
                
            logger.info(f"Fetched {len(formatted_news)} news items for {symbol}")
            return formatted_news
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error fetching news for {symbol}: {e}")
            return []
        except (ValueError, IndexError, KeyError) as e:
            logger.error(f"Error parsing news data for {symbol}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching news for {symbol}: {e}")
            return []
            
    def update_news_data(self):
        """Update news data for all configured stock symbols."""
        current_time = time.time()
        update_interval = self.stock_news_config.get('update_interval', 300)  # Default to 5 minutes
        
        # If not enough time has passed, keep using existing data
        if current_time - self.last_update < update_interval:
            return
            
        # Get symbols from config
        symbols = self.stocks_config.get('symbols', [])
        if not symbols:
            logger.warning("No stock symbols configured for news")
            return
            
        # Create temporary storage for new data
        new_data = {}
        success = False
        
        for symbol in symbols:
            # Add a small delay between requests to avoid rate limiting
            time.sleep(random.uniform(0.1, 0.3))
            news_items = self._fetch_news_for_symbol(symbol)
            if news_items:
                new_data[symbol] = news_items
                success = True
                
        if success:
            # Only update the displayed data when we have new data
            self.news_data = new_data
            self.last_update = current_time
            logger.info(f"Updated news data for {len(new_data)} symbols")
        else:
            logger.error("Failed to fetch news for any configured stocks")
            
    def _create_text_image(self, text: str, color: Tuple[int, int, int] = (255, 255, 255)) -> Image.Image:
        """Create an image containing the text for efficient scrolling."""
        # Get text dimensions
        bbox = self.display_manager.draw.textbbox((0, 0), text, font=self.display_manager.small_font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # Create a new image with the text
        text_image = Image.new('RGB', (text_width, self.display_manager.matrix.height), (0, 0, 0))
        text_draw = ImageDraw.Draw(text_image)
        
        # Draw the text centered vertically
        y = (self.display_manager.matrix.height - text_height) // 2
        text_draw.text((0, y), text, font=self.display_manager.small_font, fill=color)
        
        return text_image
            
    def _log_frame_rate(self):
        """Log frame rate statistics."""
        current_time = time.time()
        
        # Calculate instantaneous frame time
        frame_time = current_time - self.last_frame_time
        self.frame_times.append(frame_time)
        
        # Keep only last 100 frames for average
        if len(self.frame_times) > 100:
            self.frame_times.pop(0)
        
        # Log FPS every second
        if current_time - self.last_fps_log_time >= 1.0:
            avg_frame_time = sum(self.frame_times) / len(self.frame_times)
            avg_fps = 1.0 / avg_frame_time if avg_frame_time > 0 else 0
            instant_fps = 1.0 / frame_time if frame_time > 0 else 0
            
            logger.info(f"Frame stats - Avg FPS: {avg_fps:.1f}, Current FPS: {instant_fps:.1f}, Frame time: {frame_time*1000:.2f}ms")
            self.last_fps_log_time = current_time
            self.frame_count = 0
        
        self.last_frame_time = current_time
        self.frame_count += 1

    def display_news(self):
        """Display news headlines by scrolling them across the screen."""
        if not self.stock_news_config.get('enabled', False):
            return
            
        # Start update in background if needed
        if time.time() - self.last_update >= self.stock_news_config.get('update_interval', 300):
            self.update_news_data()
            
        if not self.news_data:
            logger.warning("No news data available to display")
            return
            
        # Get all news items from all symbols
        all_news = []
        for symbol, news_items in self.news_data.items():
            for item in news_items:
                all_news.append({
                    "symbol": symbol,
                    "title": item["title"],
                    "publisher": item["publisher"]
                })
                
        if not all_news:
            return

        # Define width and height here, so they are always available
        width = self.display_manager.matrix.width
        height = self.display_manager.matrix.height

        # Create a continuous scrolling image if needed
        if self.cached_text_image is None:
            random.shuffle(all_news)
            
            # Estimate total width needed (adjust multiplier if needed)
            # Average headline length guess + symbol + screen width gap
            estimated_item_width = width * 3 # Estimate each item + gap needs ~3 screen widths
            estimated_total_width = estimated_item_width * len(all_news)

            # Create the full image with estimated width
            full_image = Image.new('RGB', (max(estimated_total_width, width), height), (0, 0, 0))
            draw = ImageDraw.Draw(full_image)
            
            current_x = 0
            screen_width_gap = width # Use a full screen width as the gap
            
            # Add initial gap before the first headline
            current_x += screen_width_gap
            
            actual_total_width = 0
            for news in all_news:
                news_text = f"{news['symbol']}: {news['title']}   "
                news_image = self._create_text_image(news_text)
                
                # Check if image needs resizing (should be rare with estimate)
                if current_x + news_image.width > full_image.width:
                    # Resize needed - this is less efficient but handles variability
                    new_width = current_x + news_image.width + screen_width_gap * (len(all_news) - all_news.index(news)) # Estimate remaining needed
                    new_full_image = Image.new('RGB', (new_width, height), (0, 0, 0))
                    new_full_image.paste(full_image, (0, 0))
                    full_image = new_full_image
                    draw = ImageDraw.Draw(full_image) # Update draw object
                    logging.warning(f"[StockNews] Resized full_image to {new_width}px")

                # Paste this news image into the full image
                full_image.paste(news_image, (current_x, 0))
                
                # Move to next position: text width + screen width gap
                current_x += news_image.width + screen_width_gap
                
            actual_total_width = current_x - screen_width_gap # Remove trailing gap
            
            # Crop the image to the actual needed size
            if actual_total_width > 0 and actual_total_width < full_image.width:
                 full_image = full_image.crop((0, 0, actual_total_width, height))

            # Cache the full image
            self.cached_text_image = full_image
            self.scroll_position = 0
            # Don't reset last_update time here, cache creation isn't a data update
            # self.last_update = time.time()
        
        # --- Scrolling logic remains the same --- 
        # width = self.display_manager.matrix.width # Moved up
        # Check if cached image exists before accessing width
        if self.cached_text_image is None:
            logger.warning("[StockNews] Cached image is None, cannot scroll.")
            return False # Indicate nothing was displayed
            
        total_width = self.cached_text_image.width
        
        # If total_width is somehow less than screen width, don't scroll
        if total_width <= width:
            self.display_manager.image.paste(self.cached_text_image, (0, 0))
            self.display_manager.update_display()
            time.sleep(self.stock_news_config.get('item_display_duration', 5)) # Hold static image
            self.cached_text_image = None # Force recreation next cycle
            return True

        # Update scroll position
        self.scroll_position += self.scroll_speed
        if self.scroll_position >= total_width:
            self.scroll_position = 0 # Wrap around
            # Optional: Force reload/reshuffle when wrapping
            # self.cached_text_image = None 
            # return True # Indicate wrap happened if needed by controller

        # Calculate the visible portion
        # Handle wrap-around drawing
        visible_end = self.scroll_position + width
        if visible_end <= total_width:
            # Normal case: Paste single crop
            visible_portion = self.cached_text_image.crop((
                self.scroll_position, 0,
                visible_end, height
            ))
            self.display_manager.image.paste(visible_portion, (0, 0))
        else:
            # Wrap-around case: Paste two parts
            width1 = total_width - self.scroll_position
            width2 = width - width1
            portion1 = self.cached_text_image.crop((self.scroll_position, 0, total_width, height))
            portion2 = self.cached_text_image.crop((0, 0, width2, height))
            self.display_manager.image.paste(portion1, (0, 0))
            self.display_manager.image.paste(portion2, (width1, 0))

        self.display_manager.update_display()
        self._log_frame_rate()
        time.sleep(self.scroll_delay)
        
        return True 