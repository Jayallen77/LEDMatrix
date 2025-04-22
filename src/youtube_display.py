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
    def __init__(self, display_manager, config: Dict[str, Any]):
        self.display_manager = display_manager
        self.config = config
        self.youtube_config = config.get('youtube', {})
        self.enabled = self.youtube_config.get('enabled', False)
        self.update_interval = self.youtube_config.get('update_interval', 300)
        self.last_update = 0
        self.channel_stats = None
        
        # Load secrets file
        try:
            with open('config/config_secrets.json', 'r') as f:
                self.secrets = json.load(f)
        except Exception as e:
            logger.error(f"Error loading secrets file: {e}")
            self.secrets = {}
            self.enabled = False
        
        if self.enabled:
            logger.info("YouTube display enabled")
            self._initialize_display()
        else:
            logger.info("YouTube display disabled")
            
    def _initialize_display(self):
        """Initialize display components."""
        self.font = ImageFont.truetype("assets/fonts/PressStart2P-Regular.ttf", 8)
        try:
            self.youtube_logo = Image.open("assets/youtube_logo.png")
        except Exception as e:
            logger.error(f"Error loading YouTube logo: {e}")
            self.enabled = False
            
    def _get_channel_stats(self, channel_id):
        """Fetch channel statistics from YouTube API."""
        api_key = self.secrets.get('youtube', {}).get('api_key')
        if not api_key:
            logger.error("YouTube API key not configured in secrets file")
            return None
            
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
        """Create the display image with channel statistics."""
        if not channel_stats:
            return None
            
        # Create a new image with the matrix dimensions
        image = Image.new('RGB', (self.display_manager.matrix.width, self.display_manager.matrix.height))
        draw = ImageDraw.Draw(image)
        
        # Resize YouTube logo to fill 75% of display height
        logo_height = int(self.display_manager.matrix.height * 0.75)
        logo_width = int(self.youtube_logo.width * (logo_height / self.youtube_logo.height))
        resized_logo = self.youtube_logo.resize((logo_width, logo_height))
        
        # Position logo on the left
        logo_x = 2  # Small padding from left edge
        logo_y = (self.display_manager.matrix.height - logo_height) // 2  # Center vertically
        
        # Paste the logo
        image.paste(resized_logo, (logo_x, logo_y))
        
        # Calculate right section width (remaining space after logo)
        right_section_x = logo_x + logo_width + 5  # Start after logo with some padding
        
        # Draw channel name (top right)
        channel_name = channel_stats['title']
        name_bbox = draw.textbbox((0, 0), channel_name, font=self.font)
        name_width = name_bbox[2] - name_bbox[0]
        name_x = right_section_x + ((self.display_manager.matrix.width - right_section_x - name_width) // 2)
        name_y = 5  # Small padding from top
        draw.text((name_x, name_y), channel_name, font=self.font, fill=(255, 255, 255))
        
        # Draw subscriber count (middle right)
        subs_text = f"{channel_stats['subscribers']:,} subscribers"
        subs_bbox = draw.textbbox((0, 0), subs_text, font=self.font)
        subs_width = subs_bbox[2] - subs_bbox[0]
        subs_x = right_section_x + ((self.display_manager.matrix.width - right_section_x - subs_width) // 2)
        subs_y = name_y + 15  # Position below channel name
        draw.text((subs_x, subs_y), subs_text, font=self.font, fill=(255, 255, 255))
        
        # Draw view count (bottom right)
        views_text = f"{channel_stats['views']:,} views"
        views_bbox = draw.textbbox((0, 0), views_text, font=self.font)
        views_width = views_bbox[2] - views_bbox[0]
        views_x = right_section_x + ((self.display_manager.matrix.width - right_section_x - views_width) // 2)
        views_y = subs_y + 15  # Position below subscriber count
        draw.text((views_x, views_y), views_text, font=self.font, fill=(255, 255, 255))
        
        return image
        
    def update(self):
        """Update YouTube channel stats if needed."""
        if not self.enabled:
            return
            
        current_time = time.time()
        if current_time - self.last_update >= self.update_interval:
            channel_id = self.config.get('youtube', {}).get('channel_id')
            if not channel_id:
                logger.error("YouTube channel ID not configured")
                return
                
            self.channel_stats = self._get_channel_stats(channel_id)
            self.last_update = current_time
            
    def display(self, force_clear: bool = False):
        """Display YouTube channel stats."""
        if not self.enabled:
            return
            
        if not self.channel_stats:
            self.update()
            
        if self.channel_stats:
            if force_clear:
                self.display_manager.clear()
                
            display_image = self._create_display(self.channel_stats)
            if display_image:
                self.display_manager.image = display_image
                self.display_manager.update_display()
            
    def cleanup(self):
        """Clean up resources."""
        if self.enabled:
            self.display_manager.clear()

if __name__ == "__main__":
    # Example usage
    youtube_display = YouTubeDisplay()
    youtube_display.display()
    youtube_display.cleanup() 