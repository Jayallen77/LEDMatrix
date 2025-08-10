import json
import os
import sys
import subprocess

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(PROJECT_DIR, 'config', 'config.json')
WEB_INTERFACE_SCRIPT = os.path.join(PROJECT_DIR, 'web_interface_v2.py')
def get_python_executable():
    """Prefer the venv_web_v2 Python if present, else fall back to current interpreter."""
    project_dir = PROJECT_DIR
    if os.name == 'nt':
        venv_python = os.path.join(project_dir, 'venv_web_v2', 'Scripts', 'python.exe')
    else:
        venv_python = os.path.join(project_dir, 'venv_web_v2', 'bin', 'python')
    if os.path.exists(venv_python):
        return venv_python
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