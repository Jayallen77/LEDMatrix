#!/usr/bin/env python3
"""
LED Matrix Web Interface V2 Startup Script
Modern, lightweight web interface with real-time display preview and editor mode.
"""

import os
import sys
import subprocess
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/web_interface_v2.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def check_dependencies():
    """Check if required dependencies are installed."""
    required_packages = [
        'flask',
        'flask_socketio',
        'PIL',
        'socketio',
        'eventlet'
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        logger.warning(f"Missing packages: {missing_packages}")
        logger.info("Installing missing packages...")
        try:
            subprocess.check_call([
                sys.executable, '-m', 'pip', 'install', '-r', 'requirements_web_v2.txt'
            ])
            logger.info("Dependencies installed successfully")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to install dependencies: {e}")
            return False
    
    return True

def check_permissions():
    """Check if we have necessary permissions for system operations."""
    try:
        # Test sudo access
        result = subprocess.run(['sudo', '-n', 'true'], capture_output=True)
        if result.returncode != 0:
            logger.warning("Sudo access not available. Some system features may not work.")
            return False
        return True
    except Exception as e:
        logger.error(f"Error checking permissions: {e}")
        return False

def main():
    """Main startup function."""
    logger.info("Starting LED Matrix Web Interface V2...")
    
    # Change to script directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    # Check dependencies
    if not check_dependencies():
        logger.error("Dependency check failed. Exiting.")
        sys.exit(1)
    
    # Check permissions
    check_permissions()
    
    # Import and start the web interface
    try:
        from web_interface_v2 import app, socketio
        logger.info("Web interface loaded successfully")
        
        # Start the server
        logger.info("Starting web server on http://0.0.0.0:5001")
        socketio.run(
            app, 
            host='0.0.0.0', 
            port=5001,  # Use port 5001 to avoid conflicts
            debug=False,
            allow_unsafe_werkzeug=True
        )
        
    except ImportError as e:
        logger.error(f"Failed to import web interface: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to start web interface: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()