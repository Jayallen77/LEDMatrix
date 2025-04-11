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

    def _create_stock_display(self, symbol: str, data: Dict[str, Any]) -> Image.Image:
        """Create an image containing the stock information for efficient scrolling."""
        width = self.display_manager.matrix.width
        height = self.display_manager.matrix.height
        
        # Create a new image with black background
        display_image = Image.new('RGB', (width, height), (0, 0, 0))
        draw = ImageDraw.Draw(display_image)
        
        # Get stock color
        color = self._get_stock_color(symbol)
        
        # Draw stock logo (placeholder for now - we'll use a simple icon)
        logo_text = "📈" if data.get('change', 0) >= 0 else "📉"
        bbox = draw.textbbox((0, 0), logo_text, font=self.display_manager.small_font)
        logo_width = bbox[2] - bbox[0]
        logo_height = bbox[3] - bbox[1]
        logo_y = (height - logo_height) // 2
        draw.text((2, logo_y), logo_text, font=self.display_manager.small_font, fill=color)
        
        # Draw symbol
        symbol_text = symbol
        bbox = draw.textbbox((0, 0), symbol_text, font=self.display_manager.small_font)
        symbol_width = bbox[2] - bbox[0]
        symbol_height = bbox[3] - bbox[1]
        symbol_x = (width - symbol_width) // 2
        symbol_y = (height - symbol_height) // 2
        draw.text((symbol_x, symbol_y), symbol_text, font=self.display_manager.small_font, fill=(255, 255, 255))
        
        # Draw mini chart
        if data.get('price_history'):
            chart_width = width // 4
            chart_height = height // 3
            chart_x = width - chart_width - 2
            chart_y = (height - chart_height) // 2
            
            # Get price data for chart
            prices = [p['price'] for p in data['price_history']]
            if prices:
                min_price = min(prices)
                max_price = max(prices)
                price_range = max_price - min_price
                
                if price_range > 0:
                    points = []
                    for i, price in enumerate(prices):
                        x = chart_x + int((i / len(prices)) * chart_width)
                        y = chart_y + chart_height - int(((price - min_price) / price_range) * chart_height)
                        points.append((x, y))
                    
                    # Draw lines between points
                    for i in range(len(points) - 1):
                        draw.line([points[i], points[i + 1]], fill=color, width=1)
        
        # Draw price and change below
        price_text = f"${data['price']:.2f}"
        change_text = f"({data['change']:+.1f}%)"
        
        # Draw price
        bbox = draw.textbbox((0, 0), price_text, font=self.display_manager.small_font)
        price_width = bbox[2] - bbox[0]
        price_x = (width - price_width) // 2
        draw.text((price_x, height - 20), price_text, font=self.display_manager.small_font, fill=color)
        
        # Draw change
        bbox = draw.textbbox((0, 0), change_text, font=self.display_manager.small_font)
        change_width = bbox[2] - bbox[0]
        change_x = (width - change_width) // 2
        draw.text((change_x, height - 10), change_text, font=self.display_manager.small_font, fill=color)
        
        return display_image

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
            self.cached_text_image = self._create_stock_display(current_symbol, data)
            self.cached_text = current_symbol
        
        # Clear the display if requested
        if force_clear:
            self.display_manager.clear()
            self.scroll_position = 0
        
        # Copy the cached image to the display
        self.display_manager.image.paste(self.cached_text_image, (0, 0))
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