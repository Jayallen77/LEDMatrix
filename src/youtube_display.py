#!/usr/bin/env python3
import json
import time
import logging
from PIL import Image, ImageDraw, ImageFont
import requests
from rgbmatrix import RGBMatrix, RGBMatrixOptions
import os
from typing import Dict, Any

# Get logger without configuring
logger = logging.getLogger(__name__)

class YouTubeDisplay:
    def __init__(self, display_manager, config_path='config/config.json', secrets_path='config/config_secrets.json'):
        self.config = self._load_config(config_path)
        self.secrets = self._load_config(secrets_path)
        self.matrix = self._setup_matrix()
        self.canvas = self.matrix.CreateFrameCanvas()
        self.font = ImageFont.truetype("assets/fonts/PressStart2P-Regular.ttf", 8)
        self.youtube_logo = Image.open("assets/youtube_logo.png")
        self.display_manager = display_manager
        self.last_update = 0
        self.update_interval = self.config.get('youtube', {}).get('update_interval', 300)  # Default 5 minutes
        self.channel_stats = None
        
    def _load_config(self, config_path):
        with open(config_path, 'r') as f:
            return json.load(f)
            
    def _setup_matrix(self):
        options = RGBMatrixOptions()
        display_config = self.config['display']['hardware']
        
        options.rows = display_config['rows']
        options.cols = display_config['cols']
        options.chain_length = display_config['chain_length']
        options.parallel = display_config['parallel']
        options.hardware_mapping = display_config['hardware_mapping']
        options.brightness = display_config['brightness']
        options.pwm_bits = display_config['pwm_bits']
        options.pwm_lsb_nanoseconds = display_config['pwm_lsb_nanoseconds']
        options.disable_hardware_pulsing = display_config['disable_hardware_pulsing']
        options.show_refresh_rate = display_config['show_refresh_rate']
        options.limit_refresh_rate_hz = display_config['limit_refresh_rate_hz']
        options.gpio_slowdown = self.config['display']['runtime']['gpio_slowdown']
        
        return RGBMatrix(options=options)
        
    def _get_channel_stats(self, channel_id):
        api_key = self.secrets['youtube']['api_key']
        url = f"https://www.googleapis.com/youtube/v3/channels?part=statistics,snippet&id={channel_id}&key={api_key}"
        
        try:
            response = requests.get(url)
            data = response.json()
            if data['items']:
                channel = data['items'][0]
                return {
                    'title': channel['snippet']['title'],
                    'subscribers': int(channel['statistics']['subscriberCount']),
                    'views': int(channel['statistics']['viewCount'])
                }
        except Exception as e:
            logger.error(f"Error fetching YouTube stats: {e}")
            return None
            
    def _create_display(self, channel_stats):
        # Create a new image with the matrix dimensions
        image = Image.new('RGB', (self.matrix.width, self.matrix.height))
        draw = ImageDraw.Draw(image)
        
        # Resize YouTube logo to fit
        logo_height = self.matrix.height // 3
        logo_width = int(self.youtube_logo.width * (logo_height / self.youtube_logo.height))
        resized_logo = self.youtube_logo.resize((logo_width, logo_height))
        
        # Calculate positions
        logo_x = (self.matrix.width - logo_width) // 2
        logo_y = 0
        
        # Paste the logo
        image.paste(resized_logo, (logo_x, logo_y))
        
        # Draw channel name
        channel_name = channel_stats['title']
        name_bbox = draw.textbbox((0, 0), channel_name, font=self.font)
        name_width = name_bbox[2] - name_bbox[0]
        name_x = (self.matrix.width - name_width) // 2
        name_y = logo_height + 5
        draw.text((name_x, name_y), channel_name, font=self.font, fill=(255, 255, 255))
        
        # Draw subscriber count
        subs_text = f"{channel_stats['subscribers']:,} subscribers"
        subs_bbox = draw.textbbox((0, 0), subs_text, font=self.font)
        subs_width = subs_bbox[2] - subs_bbox[0]
        subs_x = (self.matrix.width - subs_width) // 2
        subs_y = name_y + 15
        draw.text((subs_x, subs_y), subs_text, font=self.font, fill=(255, 255, 255))
        
        return image
        
    def update(self):
        """Update YouTube channel stats if needed."""
        current_time = time.time()
        if current_time - self.last_update >= self.update_interval:
            channel_id = self.secrets['youtube']['channel_id']
            self.channel_stats = self._get_channel_stats(channel_id)
            self.last_update = current_time
            
    def display(self, force_clear: bool = False):
        """Display YouTube channel stats."""
        if not self.config.get('youtube', {}).get('enabled', False):
            return
            
        if not self.channel_stats:
            self.update()
            
        if self.channel_stats:
            if force_clear:
                self.matrix.Clear()
                
            display_image = self._create_display(self.channel_stats)
            self.canvas.SetImage(display_image)
            self.matrix.SwapOnVSync(self.canvas)
            time.sleep(self.update_interval)
            
    def cleanup(self):
        self.matrix.Clear()

if __name__ == "__main__":
    # Example usage
    youtube_display = YouTubeDisplay()
    youtube_display.display()
    youtube_display.cleanup() 