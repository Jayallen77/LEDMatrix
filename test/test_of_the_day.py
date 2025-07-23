#!/usr/bin/env python3

import sys
import os
import json
from datetime import date

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.of_the_day_manager import OfTheDayManager
from src.display_manager import DisplayManager
from src.config_manager import ConfigManager

def test_of_the_day_manager():
    """Test the OfTheDayManager functionality."""
    
    print("Testing OfTheDayManager...")
    
    # Load config
    config_manager = ConfigManager()
    config = config_manager.load_config()
    
    # Create a mock display manager (we won't actually display)
    display_manager = DisplayManager(config)
    
    # Create the OfTheDayManager
    of_the_day = OfTheDayManager(display_manager, config)
    
    print(f"OfTheDayManager enabled: {of_the_day.enabled}")
    print(f"Categories loaded: {list(of_the_day.categories.keys())}")
    print(f"Data files loaded: {list(of_the_day.data_files.keys())}")
    
    # Test loading today's items
    today = date.today()
    day_of_year = today.timetuple().tm_yday
    print(f"Today is day {day_of_year} of the year")
    
    of_the_day._load_todays_items()
    print(f"Today's items: {list(of_the_day.current_items.keys())}")
    
    # Test data file loading
    for category_name, data in of_the_day.data_files.items():
        print(f"Category '{category_name}': {len(data)} items loaded")
        if str(day_of_year) in data:
            item = data[str(day_of_year)]
            print(f"  Today's item: {item.get('title', 'No title')}")
        else:
            print(f"  No item found for day {day_of_year}")
    
    # Test text wrapping
    test_text = "This is a very long text that should be wrapped to fit on the LED matrix display"
    wrapped = of_the_day._wrap_text(test_text, 60, display_manager.extra_small_font, max_lines=3)
    print(f"Text wrapping test: {wrapped}")
    
    print("OfTheDayManager test completed successfully!")

def test_data_files():
    """Test that all data files are valid JSON."""
    
    print("\nTesting data files...")
    
    data_dir = "of_the_day"
    if not os.path.exists(data_dir):
        print(f"Data directory {data_dir} not found!")
        return
    
    for filename in os.listdir(data_dir):
        if filename.endswith('.json'):
            filepath = os.path.join(data_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                print(f"✓ {filename}: {len(data)} items")
                
                # Check for today's entry
                today = date.today()
                day_of_year = today.timetuple().tm_yday
                if str(day_of_year) in data:
                    item = data[str(day_of_year)]
                    print(f"  Today's item: {item.get('title', 'No title')}")
                else:
                    print(f"  No item for day {day_of_year}")
                    
            except Exception as e:
                print(f"✗ {filename}: Error - {e}")
    
    print("Data files test completed!")

def test_config():
    """Test the configuration is valid."""
    
    print("\nTesting configuration...")
    
    config_manager = ConfigManager()
    config = config_manager.load_config()
    
    of_the_day_config = config.get('of_the_day', {})
    
    if not of_the_day_config:
        print("✗ No 'of_the_day' configuration found in config.json")
        return
    
    print(f"✓ OfTheDay configuration found")
    print(f"  Enabled: {of_the_day_config.get('enabled', False)}")
    print(f"  Update interval: {of_the_day_config.get('update_interval', 'Not set')}")
    
    categories = of_the_day_config.get('categories', {})
    print(f"  Categories: {list(categories.keys())}")
    
    for category_name, category_config in categories.items():
        enabled = category_config.get('enabled', False)
        data_file = category_config.get('data_file', 'Not set')
        print(f"    {category_name}: enabled={enabled}, data_file={data_file}")
    
    # Check display duration
    display_durations = config.get('display', {}).get('display_durations', {})
    of_the_day_duration = display_durations.get('of_the_day', 'Not set')
    print(f"  Display duration: {of_the_day_duration} seconds")
    
    print("Configuration test completed!")

if __name__ == "__main__":
    print("=== OfTheDay System Test ===\n")
    
    try:
        test_config()
        test_data_files()
        test_of_the_day_manager()
        
        print("\n=== All tests completed successfully! ===")
        print("\nTo test the display on the Raspberry Pi, run:")
        print("python3 run.py")
        
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc() 