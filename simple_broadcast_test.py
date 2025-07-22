#!/usr/bin/env python3
"""
Simple broadcast logo test script
Tests the core broadcast logo functionality without complex dependencies
"""

import os
import sys
import logging
from PIL import Image

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_broadcast_logo_files():
    """Test if broadcast logo files exist and can be loaded"""
    print("=== Testing Broadcast Logo Files ===")
    
    broadcast_logos_dir = "assets/broadcast_logos"
    if not os.path.exists(broadcast_logos_dir):
        print(f"ERROR: Broadcast logos directory not found: {broadcast_logos_dir}")
        return False
    
    print(f"Found broadcast logos directory: {broadcast_logos_dir}")
    
    # List all files in the directory
    files = os.listdir(broadcast_logos_dir)
    print(f"Files in directory: {files}")
    
    # Test a few key logos
    test_logos = ["espn", "fox", "cbs", "nbc", "tbs", "tnt"]
    
    for logo_name in test_logos:
        logo_path = os.path.join(broadcast_logos_dir, f"{logo_name}.png")
        if os.path.exists(logo_path):
            try:
                logo = Image.open(logo_path)
                print(f"✓ {logo_name}.png - Size: {logo.size}")
            except Exception as e:
                print(f"✗ {logo_name}.png - Error loading: {e}")
        else:
            print(f"✗ {logo_name}.png - File not found")
    
    return True

def test_broadcast_logo_mapping():
    """Test the broadcast logo mapping logic"""
    print("\n=== Testing Broadcast Logo Mapping ===")
    
    # Define the broadcast logo mapping (copied from odds_ticker_manager.py)
    BROADCAST_LOGO_MAP = {
        "ACC Network": "accn",
        "ACCN": "accn",
        "ABC": "abc",
        "BTN": "btn",
        "CBS": "cbs",
        "CBSSN": "cbssn",
        "CBS Sports Network": "cbssn",
        "ESPN": "espn",
        "ESPN2": "espn2",
        "ESPN3": "espn3",
        "ESPNU": "espnu",
        "ESPNEWS": "espn",
        "ESPN+": "espn",
        "ESPN Plus": "espn",
        "FOX": "fox",
        "FS1": "fs1",
        "FS2": "fs2",
        "MLBN": "mlbn",
        "MLB Network": "mlbn",
        "NBC": "nbc",
        "NFLN": "nfln",
        "NFL Network": "nfln",
        "PAC12": "pac12n",
        "Pac-12 Network": "pac12n",
        "SECN": "espn-sec-us",
        "TBS": "tbs",
        "TNT": "tnt",
        "truTV": "tru",
        "Peacock": "nbc",
        "Paramount+": "cbs",
        "Hulu": "espn",
        "Disney+": "espn",
        "Apple TV+": "nbc"
    }
    
    # Test various broadcast names that might appear in the API
    test_cases = [
        ["ESPN"],
        ["FOX"],
        ["CBS"],
        ["NBC"],
        ["ESPN2"],
        ["FS1"],
        ["ESPNEWS"],
        ["ESPN+"],
        ["ESPN Plus"],
        ["Peacock"],
        ["Paramount+"],
        ["ABC"],
        ["TBS"],
        ["TNT"],
        ["Unknown Channel"],
        []
    ]
    
    for broadcast_names in test_cases:
        print(f"\nTesting broadcast names: {broadcast_names}")
        
        # Simulate the logo mapping logic
        logo_name = None
        sorted_keys = sorted(BROADCAST_LOGO_MAP.keys(), key=len, reverse=True)
        
        for b_name in broadcast_names:
            for key in sorted_keys:
                if key in b_name:
                    logo_name = BROADCAST_LOGO_MAP[key]
                    print(f"  Matched '{key}' to '{logo_name}' for '{b_name}'")
                    break
            if logo_name:
                break
        
        print(f"  Final mapped logo name: '{logo_name}'")
        
        if logo_name:
            # Test loading the actual logo
            logo_path = os.path.join('assets', 'broadcast_logos', f"{logo_name}.png")
            print(f"  Logo path: {logo_path}")
            print(f"  File exists: {os.path.exists(logo_path)}")
            
            if os.path.exists(logo_path):
                try:
                    logo = Image.open(logo_path)
                    print(f"  ✓ Successfully loaded logo: {logo.size} pixels")
                except Exception as e:
                    print(f"  ✗ Error loading logo: {e}")
            else:
                print("  ✗ Logo file not found!")

def test_simple_image_creation():
    """Test creating a simple image with a broadcast logo"""
    print("\n=== Testing Simple Image Creation ===")
    
    try:
        # Create a simple test image
        width, height = 64, 32
        image = Image.new('RGB', (width, height), color=(0, 0, 0))
        
        # Try to load and paste a broadcast logo
        logo_path = os.path.join('assets', 'broadcast_logos', 'espn.png')
        if os.path.exists(logo_path):
            logo = Image.open(logo_path)
            print(f"Loaded ESPN logo: {logo.size}")
            
            # Resize logo to fit
            logo_height = height - 4
            ratio = logo_height / logo.height
            logo_width = int(logo.width * ratio)
            logo = logo.resize((logo_width, logo_height), Image.Resampling.LANCZOS)
            
            # Paste logo in the center
            x = (width - logo_width) // 2
            y = (height - logo_height) // 2
            image.paste(logo, (x, y), logo if logo.mode == 'RGBA' else None)
            
            # Save the test image
            output_path = 'test_simple_broadcast_logo.png'
            image.save(output_path)
            print(f"✓ Created test image: {output_path}")
            
        else:
            print("✗ ESPN logo not found")
            
    except Exception as e:
        print(f"✗ Error creating test image: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("=== Simple Broadcast Logo Test ===\n")
    
    # Test 1: Check if broadcast logo files exist
    test_broadcast_logo_files()
    
    # Test 2: Test broadcast logo mapping
    test_broadcast_logo_mapping()
    
    # Test 3: Test simple image creation
    test_simple_image_creation()
    
    print("\n=== Test Complete ===")
    print("Check the generated PNG files to see if broadcast logos are working.") 