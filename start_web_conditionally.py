import json
import os
import sys
import subprocess
from pathlib import Path

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(PROJECT_DIR, 'config', 'config.json')
WEB_INTERFACE_SCRIPT = os.path.join(PROJECT_DIR, 'web_interface_v2.py')

def setup_virtual_environment():
    """Set up a virtual environment for the web interface if it doesn't exist."""
    venv_path = Path(PROJECT_DIR) / 'venv_web_v2'
    
    if not venv_path.exists():
        print("Creating virtual environment...")
        try:
            subprocess.check_call([
                sys.executable, '-m', 'venv', str(venv_path)
            ])
            print("Virtual environment created successfully")
        except subprocess.CalledProcessError as e:
            print(f"Failed to create virtual environment: {e}")
            return None
    
    return venv_path

def get_venv_python(venv_path):
    """Get the Python executable path from the virtual environment."""
    if os.name == 'nt':  # Windows
        return venv_path / 'Scripts' / 'python.exe'
    else:  # Unix/Linux
        return venv_path / 'bin' / 'python'

def get_venv_pip(venv_path):
    """Get the pip executable path from the virtual environment."""
    if os.name == 'nt':  # Windows
        return venv_path / 'Scripts' / 'pip.exe'
    else:  # Unix/Linux
        return venv_path / 'bin' / 'pip'

def install_dependencies(venv_path):
    """Install required dependencies in the virtual environment."""
    print("Installing dependencies...")
    try:
        venv_pip = get_venv_pip(venv_path)
        requirements_file = os.path.join(PROJECT_DIR, 'requirements_web_v2.txt')
        subprocess.check_call([
            str(venv_pip), 'install', '-r', requirements_file
        ])
        print("Dependencies installed successfully")
        
        # Install rgbmatrix module from local source
        print("Installing rgbmatrix module...")
        rgbmatrix_path = Path(PROJECT_DIR) / 'rpi-rgb-led-matrix-master' / 'bindings' / 'python'
        if rgbmatrix_path.exists():
            subprocess.check_call([
                str(venv_pip), 'install', '-e', str(rgbmatrix_path)
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("rgbmatrix module installed successfully")
        
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to install dependencies: {e}")
        return False

def get_python_executable():
    """Prefer the venv_web_v2 Python if present, else fall back to current interpreter."""
    project_dir = PROJECT_DIR
    venv_path = Path(project_dir) / 'venv_web_v2'
    
    if venv_path.exists():
        venv_python = get_venv_python(venv_path)
        if venv_python.exists():
            return str(venv_python)
    
    return sys.executable

def main():
    try:
        with open(CONFIG_FILE, 'r') as f:
            config_data = json.load(f)
    except FileNotFoundError:
        print(f"Config file {CONFIG_FILE} not found. Web interface will not start.")
        sys.exit(0) # Exit gracefully, don't start
    except Exception as e:
        print(f"Error reading config file {CONFIG_FILE}: {e}. Web interface will not start.")
        sys.exit(1) # Exit with error, service might restart depending on config

    autostart_enabled = config_data.get("web_display_autostart", False)

    if autostart_enabled is True: # Explicitly check for True
        print("Configuration 'web_display_autostart' is true. Starting web interface...")
        
        # Set up virtual environment if it doesn't exist
        venv_path = setup_virtual_environment()
        if venv_path:
            # Install dependencies
            if not install_dependencies(venv_path):
                print("Failed to install dependencies. Exiting.")
                sys.exit(1)
        
        try:
            # Replace the current process with web_interface.py
            # This is important for systemd to correctly manage the web server process.
            # Ensure PYTHONPATH is set correctly if web_interface.py has relative imports to src
            # The WorkingDirectory in systemd service should handle this for web_interface.py
            py_exec = get_python_executable()
            os.execvp(py_exec, [py_exec, WEB_INTERFACE_SCRIPT])
        except Exception as e:
            print(f"Failed to exec web interface: {e}")
            sys.exit(1) # Failed to start
    else:
        print("Configuration 'web_display_autostart' is false or not set. Web interface will not be started.")
        sys.exit(0) # Exit gracefully, service considered successful

if __name__ == '__main__':
    main() 