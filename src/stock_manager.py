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
from PIL import Image, ImageDraw
import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StockManager:
    def __init__(self, config: Dict[str, Any], display_manager):
        self.config = config
        self.display_manager = display_manager
        self.stocks_config = config.get('stocks', {})
        self.last_update = 0
        self.stock_data = {}
        self.current_stock_index = 0
        self.scroll_position = 0
        self.cached_text_image = None
        self.cached_text = None
        
        # Get scroll settings from config with faster defaults
        self.scroll_speed = self.stocks_config.get('scroll_speed', 1)
        self.scroll_delay = self.stocks_config.get('scroll_delay', 0.001)
        
        # Initialize frame rate tracking
        self.frame_count = 0
        self.last_frame_time = time.time()
        self.last_fps_log_time = time.time()
        self.frame_times = []
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        # Initialize with first update
        self.update_stock_data()
        
    def _get_stock_color(self, symbol: str) -> Tuple[int, int, int]:
        """Get color based on stock performance."""
        if symbol not in self.stock_data:
            return (255, 255, 255)  # White for unknown
        
        change = self.stock_data[symbol].get('change', 0)
        if change > 0:
            return (0, 255, 0)  # Green for positive
        elif change < 0:
            return (255, 0, 0)  # Red for negative
        return (255, 255, 0)  # Yellow for no change
        
    def _extract_json_from_html(self, html: str) -> Dict:
        """Extract the JSON data from Yahoo Finance HTML."""
        try:
            # Look for the finance data in the HTML
            patterns = [
                r'root\.App\.main = (.*?);\s*</script>',
                r'"QuotePageStore":\s*({.*?}),\s*"',
                r'{"regularMarketPrice":.*?"regularMarketChangePercent".*?}'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, html, re.DOTALL)
                if match:
                    json_str = match.group(1)
                    try:
                        data = json.loads(json_str)
                        if isinstance(data, dict):
                            if 'context' in data:
                                # First pattern matched
                                context = data.get('context', {})
                                dispatcher = context.get('dispatcher', {})
                                stores = dispatcher.get('stores', {})
                                quote_data = stores.get('QuoteSummaryStore', {})
                                if quote_data:
                                    return quote_data
                            else:
                                # Direct quote data
                                return data
                    except json.JSONDecodeError:
                        continue
                        
            # If we get here, try one last attempt to find the price data directly
            price_match = re.search(r'"regularMarketPrice":{"raw":([\d.]+)', html)
            change_match = re.search(r'"regularMarketChangePercent":{"raw":([-\d.]+)', html)
            prev_close_match = re.search(r'"regularMarketPreviousClose":{"raw":([\d.]+)', html)
            name_match = re.search(r'"shortName":"([^"]+)"', html)
            
            if price_match:
                return {
                    "price": {
                        "regularMarketPrice": {"raw": float(price_match.group(1))},
                        "regularMarketChangePercent": {"raw": float(change_match.group(1)) if change_match else 0},
                        "regularMarketPreviousClose": {"raw": float(prev_close_match.group(1)) if prev_close_match else 0},
                        "shortName": name_match.group(1) if name_match else None
                    }
                }
            
            return {}
        except Exception as e:
            logger.error(f"Error extracting JSON data: {e}")
            return {}
        
    def _fetch_stock_data(self, symbol: str) -> Dict[str, Any]:
        """Fetch stock data from Yahoo Finance public API."""
        try:
            # Use Yahoo Finance query1 API for chart data
            encoded_symbol = urllib.parse.quote(symbol)
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded_symbol}"
            params = {
                'interval': '5m',  # 5-minute intervals
                'range': '1d'      # 1 day of data
            }
            
            response = requests.get(url, headers=self.headers, params=params, timeout=5)
            if response.status_code != 200:
                logger.error(f"Failed to fetch data for {symbol}: HTTP {response.status_code}")
                return None
                
            data = response.json()
            
            # Extract the relevant data from the response
            chart_data = data.get('chart', {}).get('result', [{}])[0]
            meta = chart_data.get('meta', {})
            
            if not meta:
                logger.error(f"No meta data found for {symbol}")
                return None
                
            current_price = meta.get('regularMarketPrice', 0)
            prev_close = meta.get('previousClose', current_price)
            
            # Get price history
            timestamps = chart_data.get('timestamp', [])
            indicators = chart_data.get('indicators', {}).get('quote', [{}])[0]
            close_prices = indicators.get('close', [])
            
            # Build price history
            price_history = []
            for i, ts in enumerate(timestamps):
                if i < len(close_prices) and close_prices[i] is not None:
                    price_history.append({
                        'timestamp': datetime.fromtimestamp(ts),
                        'price': close_prices[i]
                    })
            
            # Calculate change percentage
            change_pct = ((current_price - prev_close) / prev_close) * 100 if prev_close > 0 else 0
            
            # Get company name (symbol will be used if name not available)
            name = meta.get('symbol', symbol)
            
            logger.debug(f"Processed data for {symbol}: price={current_price}, change={change_pct}%")
            
            return {
                "symbol": symbol,
                "name": name,
                "price": current_price,
                "change": change_pct,
                "open": prev_close,
                "price_history": price_history
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error fetching data for {symbol}: {e}")
            return None
        except (ValueError, IndexError, KeyError) as e:
            logger.error(f"Error parsing data for {symbol}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching data for {symbol}: {e}")
            return None

    def _draw_chart(self, symbol: str, data: Dict[str, Any]):
        """Draw a price chart for the stock."""
        if not data.get('price_history'):
            return
            
        # Clear the display
        self.display_manager.clear()
        
        # Draw the symbol at the top with small font
        self.display_manager.draw_text(
            symbol,
            y=1,  # Moved up slightly
            color=(255, 255, 255),
            small_font=True  # Use small font
        )
        
        # Calculate chart dimensions
        chart_height = 16  # Reduced from 22 to make chart smaller
        chart_y = 8  # Slightly adjusted starting position
        width = self.display_manager.matrix.width
        
        # Get min and max prices for scaling
        prices = [p['price'] for p in data['price_history']]
        if not prices:
            return
        min_price = min(prices)
        max_price = max(prices)
        price_range = max_price - min_price
        
        if price_range == 0:
            return
            
        # Draw chart points
        points = []
        color = self._get_stock_color(symbol)
        
        for i, point in enumerate(data['price_history']):
            x = int((i / len(data['price_history'])) * width)
            y = chart_y + chart_height - int(((point['price'] - min_price) / price_range) * chart_height)
            points.append((x, y))
            
        # Draw lines between points
        for i in range(len(points) - 1):
            x1, y1 = points[i]
            x2, y2 = points[i + 1]
            self.display_manager.draw.line([x1, y1, x2, y2], fill=color, width=1)
            
        # Draw current price at the bottom with small font
        price_text = f"${data['price']:.2f} ({data['change']:+.1f}%)"
        self.display_manager.draw_text(
            price_text,
            y=28,  # Moved down slightly from 30 to give more space
            color=color,
            small_font=True  # Use small font
        )
        
        # Update the display
        self.display_manager.update_display()

    def _reload_config(self):
        """Reload configuration from file."""
        # Reset stock data if symbols have changed
        new_symbols = set(self.stocks_config.get('symbols', []))
        current_symbols = set(self.stock_data.keys())
        if new_symbols != current_symbols:
            self.stock_data = {}
            self.current_stock_index = 0
            self.last_update = 0  # Force immediate update
            logger.info(f"Stock symbols changed. New symbols: {new_symbols}")

    def update_stock_data(self):
        """Update stock data if enough time has passed."""
        current_time = time.time()
        update_interval = self.stocks_config.get('update_interval', 60)
        
        # If not enough time has passed, keep using existing data
        if current_time - self.last_update < update_interval + random.uniform(0, 2):
            return

        # Reload config to check for symbol changes
        self._reload_config()
            
        # Get symbols from config
        symbols = self.stocks_config.get('symbols', [])
        if not symbols:
            logger.warning("No stock symbols configured")
            return
            
        # If symbols is a list of strings, convert to list of dicts
        if isinstance(symbols[0], str):
            symbols = [{"symbol": symbol} for symbol in symbols]
            
        # Create temporary storage for new data
        new_data = {}
        success = False
        
        for stock in symbols:
            symbol = stock['symbol']
            # Add a small delay between requests to avoid rate limiting
            time.sleep(random.uniform(0.1, 0.3))  # Reduced delay
            data = self._fetch_stock_data(symbol)
            if data:
                new_data[symbol] = data
                success = True
                logger.info(f"Updated {symbol}: ${data['price']:.2f} ({data['change']:+.2f}%)")
                
        if success:
            # Only update the displayed data when we have new data
            self.stock_data.update(new_data)
            self.last_update = current_time
        else:
            logger.error("Failed to fetch data for any configured stocks")

    def _create_stock_display(self, symbol: str, data: Dict[str, Any], width: int, height: int, scroll_position: int = 0) -> Image.Image:
        """Create a single stock display with scrolling animation."""
        # Create a wider image for scrolling
        scroll_width = width * 2  # Double width for smooth scrolling
        image = Image.new('RGB', (scroll_width, height), (0, 0, 0))
        draw = ImageDraw.Draw(image)
        
        # Get stock color
        color = self._get_stock_color(symbol)
        
        # Calculate center position for the main content
        center_x = width // 2
        
        # Draw large stock logo on the left
        logo_text = symbol[:1].upper()  # First letter of symbol
        bbox = draw.textbbox((0, 0), logo_text, font=self.display_manager.regular_font)
        logo_width = bbox[2] - bbox[0]
        logo_height = bbox[3] - bbox[1]
        logo_x = center_x - width // 3 - logo_width // 2
        logo_y = (height - logo_height) // 2
        draw.text((logo_x, logo_y), logo_text, font=self.display_manager.regular_font, fill=color)
        
        # Draw stacked symbol, price, and change in the center
        # Symbol (always white)
        symbol_text = symbol
        bbox = draw.textbbox((0, 0), symbol_text, font=self.display_manager.small_font)
        symbol_width = bbox[2] - bbox[0]
        symbol_height = bbox[3] - bbox[1]
        symbol_x = center_x + (width // 3 - symbol_width) // 2
        symbol_y = height // 4 - symbol_height // 2  # Center symbol in top quarter
        draw.text((symbol_x, symbol_y), symbol_text, font=self.display_manager.small_font, fill=(255, 255, 255))  # White color for symbol
        
        # Price and change (in stock color)
        price_text = f"${data['price']:.2f}"
        change_text = f"({data['change']:+.1f}%)"
        
        # Calculate widths and heights for both texts to ensure proper alignment
        price_bbox = draw.textbbox((0, 0), price_text, font=self.display_manager.small_font)
        change_bbox = draw.textbbox((0, 0), change_text, font=self.display_manager.small_font)
        price_width = price_bbox[2] - price_bbox[0]
        change_width = change_bbox[2] - change_bbox[0]
        text_height = price_bbox[3] - price_bbox[1]
        
        # Center both texts based on the wider of the two
        max_width = max(price_width, change_width)
        price_x = center_x + (width // 3 - max_width) // 2
        change_x = center_x + (width // 3 - max_width) // 2
        
        # Calculate total height needed for all three elements
        total_text_height = symbol_height + text_height * 2  # Two lines of text
        spacing = 1  # Minimal spacing between elements
        total_height = total_text_height + spacing * 2  # Spacing between all elements
        
        # Start from the top with proper centering
        start_y = (height - total_height) // 2
        
        # Position texts vertically with minimal spacing
        price_y = start_y + symbol_height + spacing
        change_y = price_y + text_height + spacing
        
        # Draw both texts
        draw.text((price_x, price_y), price_text, font=self.display_manager.small_font, fill=color)
        draw.text((change_x, change_y), change_text, font=self.display_manager.small_font, fill=color)
        
        # Draw mini chart on the right
        chart_width = 30  # Increased from 20 to 30
        chart_height = 32  # Increased from 32 to match text height
        chart_x = scroll_width - chart_width - 5  # Shift one width to the right (using scroll_width instead of width)
        chart_y = 0  # Align with top of display
        
        # Draw chart background
        draw.rectangle([(chart_x, chart_y), (chart_x + chart_width - 1, chart_y + chart_height - 1)], 
                     outline=color)
        
        # Get price history for chart
        price_history = data.get('price_history', [])
        if len(price_history) >= 2:  # Need at least 2 points to draw a line
            # Extract prices from price history
            prices = [p['price'] for p in price_history]
            # Calculate price range with padding to avoid flat lines
            min_price = min(prices) * 0.99  # 1% padding below
            max_price = max(prices) * 1.01  # 1% padding above
            price_range = max_price - min_price
            
            if price_range == 0:  # If all prices are the same
                price_range = min_price * 0.01  # Use 1% of price as range
            
            # Calculate points for the line
            points = []
            for i, price_data in enumerate(price_history):
                price = price_data['price']
                # Calculate x position with proper spacing
                x = chart_x + 1 + (i * (chart_width - 2) // (len(price_history) - 1))
                # Calculate y position (inverted because y=0 is at top)
                y = chart_y + chart_height - 1 - int((price - min_price) * (chart_height - 2) / price_range)
                points.append((x, y))
            
            # Draw the line
            if len(points) >= 2:
                draw.line(points, fill=color, width=1)
        
        # Crop to show only the visible portion based on scroll position
        visible_image = image.crop((scroll_position, 0, scroll_position + width, height))
        return visible_image

    def _update_stock_display(self, symbol: str, data: Dict[str, Any], width: int, height: int) -> None:
        """Update the stock display with smooth scrolling animation."""
        try:
            # Create the full scrolling image
            full_image = self._create_stock_display(symbol, data, width, height)
            scroll_width = width * 2  # Double width for smooth scrolling
            
            # Scroll the image smoothly
            for scroll_pos in range(0, scroll_width - width, 15):  # Increased scroll speed to match news ticker
                # Create visible portion
                visible_image = full_image.crop((scroll_pos, 0, scroll_pos + width, height))
                
                # Convert to RGB and create numpy array
                rgb_image = visible_image.convert('RGB')
                image_array = np.array(rgb_image)
                
                # Update display
                self.display_manager.update_display(image_array)
                
                # Small delay for smooth animation
                time.sleep(0.01)  # Reduced delay to 10ms for smoother scrolling
            
            # Show final position briefly
            final_image = full_image.crop((scroll_width - width, 0, scroll_width, height))
            rgb_image = final_image.convert('RGB')
            image_array = np.array(rgb_image)
            self.display_manager.update_display(image_array)
            time.sleep(0.5)  # Brief pause at the end
            
        except Exception as e:
            logger.error(f"Error updating stock display for {symbol}: {str(e)}")
            # Show error state
            self._show_error_state(width, height)

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

    def display_stocks(self, force_clear: bool = False):
        """Display stock information with scrolling animation."""
        if not self.stocks_config.get('enabled', False):
            return
            
        # Start update in background if needed
        if time.time() - self.last_update >= self.stocks_config.get('update_interval', 60):
            self.update_stock_data()
        
        if not self.stock_data:
            logger.warning("No stock data available to display")
            return
            
        # Get the current stock to display
        symbols = list(self.stock_data.keys())
        if not symbols:
            return
            
        current_symbol = symbols[self.current_stock_index]
        data = self.stock_data[current_symbol]
        
        # Create the display image if needed
        if self.cached_text_image is None or self.cached_text != current_symbol:
            self.cached_text_image = self._create_stock_display(current_symbol, data, self.display_manager.matrix.width, self.display_manager.matrix.height)
            self.cached_text = current_symbol
            self.scroll_position = 0
        
        # Clear the display if requested
        if force_clear:
            self.display_manager.clear()
            self.scroll_position = 0
        
        # Calculate the visible portion of the image
        width = self.display_manager.matrix.width
        scroll_width = width * 2  # Double width for smooth scrolling
        
        # Update scroll position with small increments
        self.scroll_position = (self.scroll_position + self.scroll_speed) % scroll_width
        
        # Calculate the visible portion
        visible_portion = self.cached_text_image.crop((
            self.scroll_position, 0,
            self.scroll_position + width, self.display_manager.matrix.height
        ))
        
        # Copy the visible portion to the display
        self.display_manager.image.paste(visible_portion, (0, 0))
        self.display_manager.update_display()
        
        # Log frame rate
        self._log_frame_rate()
        
        # Add a small delay between frames
        time.sleep(self.scroll_delay)
        
        # Move to next stock after a delay
        if time.time() - self.last_update > 5:  # Show each stock for 5 seconds
            self.current_stock_index = (self.current_stock_index + 1) % len(symbols)
            self.last_update = time.time()
            self.cached_text_image = None  # Force recreation of display for next stock
        
        # If we've shown all stocks, signal completion by returning True
        return self.current_stock_index == 0 