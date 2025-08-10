#!/usr/bin/env python3
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_socketio import SocketIO, emit
import json
import os
import subprocess
import threading
import time
import base64
import psutil
from pathlib import Path
from src.config_manager import ConfigManager
from src.display_manager import DisplayManager
from PIL import Image
import io
import signal
import sys
import logging

app = Flask(__name__)
app.secret_key = os.urandom(24)
# Prefer eventlet if available for stable websockets on Pi; fall back gracefully
async_mode = None
try:
    import eventlet  # noqa: F401
    async_mode = 'eventlet'
except Exception:
    async_mode = 'threading'

socketio = SocketIO(app, cors_allowed_origins="*", async_mode=async_mode)

# Global variables
config_manager = ConfigManager()
display_manager = None
display_thread = None
display_running = False
editor_mode = False
current_display_data = {}

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class DisplayMonitor:
    def __init__(self):
        self.running = False
        self.thread = None

    def start(self):
        if not self.running:
            self.running = True
            # Use SocketIO background task for better async compatibility
            self.thread = socketio.start_background_task(self._monitor_loop)

    def stop(self):
        self.running = False
        # Background task will exit on next loop; no join needed

    def _monitor_loop(self):
        global display_manager, current_display_data
        snapshot_path = "/tmp/led_matrix_preview.png"
        while self.running:
            try:
                # Prefer service-provided snapshot if available (works when ledmatrix service is running)
                if os.path.exists(snapshot_path):
                    with open(snapshot_path, 'rb') as f:
                        img_bytes = f.read()
                    img_str = base64.b64encode(img_bytes).decode()
                    # If we can infer dimensions from display_manager, include them; else leave 0
                    width = display_manager.width if display_manager else 0
                    height = display_manager.height if display_manager else 0
                    current_display_data = {
                        'image': img_str,
                        'width': width,
                        'height': height,
                        'timestamp': time.time()
                    }
                    socketio.emit('display_update', current_display_data)
                elif display_manager and hasattr(display_manager, 'image'):
                    # Fallback to in-process manager image
                    img_buffer = io.BytesIO()
                    display_manager.image.save(img_buffer, format='PNG')
                    img_str = base64.b64encode(img_buffer.getvalue()).decode()
                    current_display_data = {
                        'image': img_str,
                        'width': display_manager.width,
                        'height': display_manager.height,
                        'timestamp': time.time()
                    }
                    socketio.emit('display_update', current_display_data)

            except Exception as e:
                logger.error(f"Display monitor error: {e}", exc_info=True)

            # Yield to the async loop; target ~5-10 FPS
            try:
                socketio.sleep(0.2)
            except Exception:
                time.sleep(0.2)

display_monitor = DisplayMonitor()

@app.route('/')
def index():
    try:
        main_config = config_manager.load_config()
        schedule_config = main_config.get('schedule', {})
        
        # Get system status including CPU utilization
        system_status = get_system_status()
        
        # Get raw config data for JSON editors
        main_config_data = config_manager.get_raw_file_content('main')
        secrets_config_data = config_manager.get_raw_file_content('secrets')
        main_config_json = json.dumps(main_config_data, indent=4)
        secrets_config_json = json.dumps(secrets_config_data, indent=4)
        
        return render_template('index_v2.html', 
                             schedule_config=schedule_config,
                             main_config=main_config,
                             main_config_data=main_config_data,
                             secrets_config=secrets_config_data,
                             main_config_json=main_config_json,
                             secrets_config_json=secrets_config_json,
                             main_config_path=config_manager.get_config_path(),
                             secrets_config_path=config_manager.get_secrets_path(),
                             system_status=system_status,
                             editor_mode=editor_mode)
                             
    except Exception as e:
        flash(f"Error loading configuration: {e}", "error")
        return render_template('index_v2.html', 
                             schedule_config={},
                             main_config={},
                             main_config_data={},
                             secrets_config={},
                             main_config_json="{}",
                             secrets_config_json="{}",
                             main_config_path="",
                             secrets_config_path="",
                             system_status={},
                             editor_mode=False)

def get_system_status():
    """Get current system status including display state, performance metrics, and CPU utilization."""
    try:
        # Check if display service is running
        result = subprocess.run(['systemctl', 'is-active', 'ledmatrix'], 
                              capture_output=True, text=True)
        service_active = result.stdout.strip() == 'active'
        
        # Get memory usage using psutil for better accuracy
        memory = psutil.virtual_memory()
        mem_used_percent = round(memory.percent, 1)
        
        # Get CPU utilization (non-blocking to avoid stalling the event loop)
        cpu_percent = round(psutil.cpu_percent(interval=None), 1)
        
        # Get CPU temperature
        try:
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                temp = int(f.read().strip()) / 1000
        except:
            temp = 0
            
        # Get uptime
        with open('/proc/uptime', 'r') as f:
            uptime_seconds = float(f.read().split()[0])
        
        uptime_hours = int(uptime_seconds // 3600)
        uptime_minutes = int((uptime_seconds % 3600) // 60)
        
        # Get disk usage
        disk = psutil.disk_usage('/')
        disk_used_percent = round((disk.used / disk.total) * 100, 1)
        
        return {
            'service_active': service_active,
            'memory_used_percent': mem_used_percent,
            'cpu_percent': cpu_percent,
            'cpu_temp': round(temp, 1),
            'disk_used_percent': disk_used_percent,
            'uptime': f"{uptime_hours}h {uptime_minutes}m",
            'display_connected': display_manager is not None,
            'editor_mode': editor_mode
        }
    except Exception as e:
        return {
            'service_active': False,
            'memory_used_percent': 0,
            'cpu_percent': 0,
            'cpu_temp': 0,
            'disk_used_percent': 0,
            'uptime': '0h 0m',
            'display_connected': False,
            'editor_mode': False,
            'error': str(e)
        }

@app.route('/api/display/start', methods=['POST'])
def start_display():
    """Start the LED matrix display."""
    global display_manager, display_running
    
    try:
        if not display_manager:
            config = config_manager.load_config()
            try:
                display_manager = DisplayManager(config)
                logger.info("DisplayManager initialized successfully")
            except Exception as dm_error:
                logger.error(f"Failed to initialize DisplayManager: {dm_error}")
                # Re-attempt with explicit fallback mode for web preview
                display_manager = DisplayManager({'display': {'hardware': {}}}, force_fallback=True)
                logger.info("Using fallback DisplayManager for web simulation")
            
            display_monitor.start()
            # Immediately publish a snapshot for the client
            try:
                img_buffer = io.BytesIO()
                display_manager.image.save(img_buffer, format='PNG')
                img_str = base64.b64encode(img_buffer.getvalue()).decode()
                snapshot = {
                    'image': img_str,
                    'width': display_manager.width,
                    'height': display_manager.height,
                    'timestamp': time.time()
                }
                # Update global and notify clients
                global current_display_data
                current_display_data = snapshot
                socketio.emit('display_update', snapshot)
            except Exception as snap_err:
                logger.error(f"Failed to publish initial snapshot: {snap_err}")
            
        display_running = True
        
        return jsonify({
            'status': 'success',
            'message': 'Display started successfully',
            'dimensions': {
                'width': getattr(display_manager, 'width', 0),
                'height': getattr(display_manager, 'height', 0)
            },
            'fallback': display_manager.matrix is None
        })
    except Exception as e:
        logger.error(f"Error in start_display: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': f'Error starting display: {e}'
        }), 500

@app.route('/api/display/stop', methods=['POST'])
def stop_display():
    """Stop the LED matrix display."""
    global display_manager, display_running
    
    try:
        display_running = False
        display_monitor.stop()
        
        if display_manager:
            display_manager.clear()
            display_manager.cleanup()
            display_manager = None
            
        return jsonify({
            'status': 'success',
            'message': 'Display stopped successfully'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error stopping display: {e}'
        }), 500

@app.route('/api/editor/toggle', methods=['POST'])
def toggle_editor_mode():
    """Toggle display editor mode."""
    global editor_mode, display_running, display_manager
    
    try:
        editor_mode = not editor_mode
        
        if editor_mode:
            # Stop normal display operation
            display_running = False
            # Initialize display manager for editor if needed
            if not display_manager:
                config = config_manager.load_config()
                try:
                    display_manager = DisplayManager(config)
                    logger.info("DisplayManager initialized for editor mode")
                except Exception as dm_error:
                    logger.error(f"Failed to initialize DisplayManager for editor: {dm_error}")
                    # Create a fallback display manager for web simulation
                    display_manager = DisplayManager(config, force_fallback=True)
                    logger.info("Using fallback DisplayManager for editor simulation")
                display_monitor.start()
        else:
            # Resume normal display operation
            display_running = True
            
        return jsonify({
            'status': 'success',
            'editor_mode': editor_mode,
            'message': f'Editor mode {"enabled" if editor_mode else "disabled"}'
        })
    except Exception as e:
        logger.error(f"Error toggling editor mode: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': f'Error toggling editor mode: {e}'
        }), 500

@app.route('/api/editor/preview', methods=['POST'])
def preview_display():
    """Preview display with custom layout."""
    global display_manager
    
    try:
        if not display_manager:
            return jsonify({
                'status': 'error',
                'message': 'Display not initialized'
            }), 400
            
        layout_data = request.get_json()
        
        # Clear display
        display_manager.clear()
        
        # Render preview based on layout data
        for element in layout_data.get('elements', []):
            render_element(display_manager, element)
            
        display_manager.update_display()
        
        return jsonify({
            'status': 'success',
            'message': 'Preview updated'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error updating preview: {e}'
        }), 500

def render_element(display_manager, element):
    """Render a single display element."""
    element_type = element.get('type')
    x = element.get('x', 0)
    y = element.get('y', 0)
    
    if element_type == 'text':
        text = element.get('text', 'Sample Text')
        color = tuple(element.get('color', [255, 255, 255]))
        font_size = element.get('font_size', 'normal')
        
        font = display_manager.small_font if font_size == 'small' else display_manager.regular_font
        display_manager.draw_text(text, x, y, color, font=font)
        
    elif element_type == 'weather_icon':
        condition = element.get('condition', 'sunny')
        size = element.get('size', 16)
        display_manager.draw_weather_icon(condition, x, y, size)
        
    elif element_type == 'rectangle':
        width = element.get('width', 10)
        height = element.get('height', 10)
        color = tuple(element.get('color', [255, 255, 255]))
        display_manager.draw.rectangle([x, y, x + width, y + height], outline=color)
        
    elif element_type == 'line':
        x2 = element.get('x2', x + 10)
        y2 = element.get('y2', y)
        color = tuple(element.get('color', [255, 255, 255]))
        display_manager.draw.line([x, y, x2, y2], fill=color)

@app.route('/api/config/save', methods=['POST'])
def save_config():
    """Save configuration changes."""
    try:
        data = request.get_json()
        config_type = data.get('type', 'main')
        config_data = data.get('data', {})
        
        if config_type == 'main':
            current_config = config_manager.load_config()
            # Deep merge the changes
            merge_dict(current_config, config_data)
            config_manager.save_config(current_config)
        elif config_type == 'layout':
            # Save custom layout configuration
            with open('config/custom_layouts.json', 'w') as f:
                json.dump(config_data, f, indent=2)
                
        return jsonify({
            'status': 'success',
            'message': 'Configuration saved successfully'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error saving configuration: {e}'
        }), 500

def merge_dict(target, source):
    """Deep merge source dict into target dict."""
    for key, value in source.items():
        if key in target and isinstance(target[key], dict) and isinstance(value, dict):
            merge_dict(target[key], value)
        else:
            target[key] = value

@app.route('/api/system/action', methods=['POST'])
def system_action():
    """Execute system actions like restart, update, etc."""
    try:
        data = request.get_json()
        action = data.get('action')
        
        if action == 'restart_service':
            result = subprocess.run(['sudo', '-n', 'systemctl', 'restart', 'ledmatrix'], 
                                  capture_output=True, text=True)
        elif action == 'stop_service':
            result = subprocess.run(['sudo', '-n', 'systemctl', 'stop', 'ledmatrix'], 
                                  capture_output=True, text=True)
        elif action == 'start_service':
            result = subprocess.run(['sudo', '-n', 'systemctl', 'start', 'ledmatrix'], 
                                  capture_output=True, text=True)
        elif action == 'reboot_system':
            result = subprocess.run(['sudo', '-n', 'reboot'], 
                                  capture_output=True, text=True)
        elif action == 'shutdown_system':
            result = subprocess.run(['sudo', '-n', 'poweroff'], 
                                  capture_output=True, text=True)
        elif action == 'git_pull':
            # Run git pull from the repository directory where this file lives
            repo_dir = Path(__file__).resolve().parent
            if not (repo_dir / '.git').exists():
                return jsonify({
                    'status': 'error',
                    'message': f'Not a git repository: {repo_dir}'
                }), 400
            result = subprocess.run(['git', 'pull'],
                                   capture_output=True, text=True, cwd=str(repo_dir), check=False)
        else:
            return jsonify({
                'status': 'error',
                'message': f'Unknown action: {action}'
            }), 400
            
        return jsonify({
            'status': 'success' if result.returncode == 0 else 'error',
            'message': f'Action {action} completed',
            'output': result.stdout,
            'error': result.stderr
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error executing action: {e}. If this action requires sudo, ensure NOPASSWD is configured or run the command manually.'
        }), 500

@app.route('/api/system/status')
def get_system_status_api():
    """Get system status as JSON."""
    return jsonify(get_system_status())

# Add all the routes from the original web interface for compatibility
@app.route('/save_schedule', methods=['POST'])
def save_schedule_route():
    try:
        main_config = config_manager.load_config()
        
        schedule_data = {
            'enabled': 'schedule_enabled' in request.form,
            'start_time': request.form.get('start_time', '07:00'),
            'end_time': request.form.get('end_time', '22:00')
        }
        
        main_config['schedule'] = schedule_data
        config_manager.save_config(main_config)
        
        return jsonify({
            'status': 'success',
            'message': 'Schedule updated successfully! Restart the display for changes to take effect.'
        })

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error saving schedule: {e}'
        }), 400

@app.route('/save_config', methods=['POST'])
def save_config_route():
    config_type = request.form.get('config_type')
    config_data_str = request.form.get('config_data')
    
    try:
        if config_type == 'main':
            # Handle form-based configuration updates
            main_config = config_manager.load_config()
            
            # Update display settings
            if 'rows' in request.form:
                main_config['display']['hardware']['rows'] = int(request.form.get('rows', 32))
                main_config['display']['hardware']['cols'] = int(request.form.get('cols', 64))
                main_config['display']['hardware']['chain_length'] = int(request.form.get('chain_length', 2))
                main_config['display']['hardware']['parallel'] = int(request.form.get('parallel', 1))
                main_config['display']['hardware']['brightness'] = int(request.form.get('brightness', 95))
                main_config['display']['hardware']['hardware_mapping'] = request.form.get('hardware_mapping', 'adafruit-hat-pwm')
                main_config['display']['runtime']['gpio_slowdown'] = int(request.form.get('gpio_slowdown', 3))
                # Add all the missing LED Matrix hardware options
                main_config['display']['hardware']['scan_mode'] = int(request.form.get('scan_mode', 0))
                main_config['display']['hardware']['pwm_bits'] = int(request.form.get('pwm_bits', 9))
                main_config['display']['hardware']['pwm_dither_bits'] = int(request.form.get('pwm_dither_bits', 1))
                main_config['display']['hardware']['pwm_lsb_nanoseconds'] = int(request.form.get('pwm_lsb_nanoseconds', 130))
                main_config['display']['hardware']['disable_hardware_pulsing'] = 'disable_hardware_pulsing' in request.form
                main_config['display']['hardware']['inverse_colors'] = 'inverse_colors' in request.form
                main_config['display']['hardware']['show_refresh_rate'] = 'show_refresh_rate' in request.form
                main_config['display']['hardware']['limit_refresh_rate_hz'] = int(request.form.get('limit_refresh_rate_hz', 120))
                main_config['display']['use_short_date_format'] = 'use_short_date_format' in request.form
            
            # If config_data is provided as JSON, merge it
            if config_data_str:
                try:
                    new_data = json.loads(config_data_str)
                    # Merge the new data with existing config
                    for key, value in new_data.items():
                        if key in main_config:
                            if isinstance(value, dict) and isinstance(main_config[key], dict):
                                merge_dict(main_config[key], value)
                            else:
                                main_config[key] = value
                        else:
                            main_config[key] = value
                except json.JSONDecodeError:
                    return jsonify({
                        'status': 'error',
                        'message': 'Error: Invalid JSON format in config data.'
                    }), 400
            
            config_manager.save_config(main_config)
            return jsonify({
                'status': 'success',
                'message': 'Main configuration saved successfully!'
            })
            
        elif config_type == 'secrets':
            # Handle secrets configuration
            secrets_config = config_manager.get_raw_file_content('secrets')
            
            # If config_data is provided as JSON, use it
            if config_data_str:
                try:
                    new_data = json.loads(config_data_str)
                    config_manager.save_raw_file_content('secrets', new_data)
                except json.JSONDecodeError:
                    return jsonify({
                        'status': 'error',
                        'message': 'Error: Invalid JSON format for secrets config.'
                    }), 400
            else:
                config_manager.save_raw_file_content('secrets', secrets_config)
            
            return jsonify({
                'status': 'success',
                'message': 'Secrets configuration saved successfully!'
            })
        
    except json.JSONDecodeError:
        return jsonify({
            'status': 'error',
            'message': f'Error: Invalid JSON format for {config_type} config.'
        }), 400
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error saving {config_type} configuration: {e}'
        }), 400

@app.route('/run_action', methods=['POST'])
def run_action_route():
    try:
        data = request.get_json()
        action = data.get('action')
        
        if action == 'start_display':
            result = subprocess.run(['sudo', '-n', 'systemctl', 'start', 'ledmatrix'], 
                                 capture_output=True, text=True)
        elif action == 'stop_display':
            result = subprocess.run(['sudo', '-n', 'systemctl', 'stop', 'ledmatrix'], 
                                 capture_output=True, text=True)
        elif action == 'enable_autostart':
            result = subprocess.run(['sudo', '-n', 'systemctl', 'enable', 'ledmatrix'], 
                                 capture_output=True, text=True)
        elif action == 'disable_autostart':
            result = subprocess.run(['sudo', '-n', 'systemctl', 'disable', 'ledmatrix'], 
                                 capture_output=True, text=True)
        elif action == 'reboot_system':
            result = subprocess.run(['sudo', '-n', 'reboot'], 
                                 capture_output=True, text=True)
        elif action == 'shutdown_system':
            result = subprocess.run(['sudo', '-n', 'poweroff'], 
                                  capture_output=True, text=True)
        elif action == 'git_pull':
            repo_dir = Path(__file__).resolve().parent
            if not (repo_dir / '.git').exists():
                return jsonify({
                    'status': 'error',
                    'message': f'Not a git repository: {repo_dir}'
                }), 400
            result = subprocess.run(['git', 'pull'],
                                 capture_output=True, text=True, cwd=str(repo_dir), check=False)
        else:
            return jsonify({
                'status': 'error',
                'message': f'Unknown action: {action}'
            }), 400
        
        return jsonify({
            'status': 'success' if result.returncode == 0 else 'error',
            'message': f'Action {action} completed with return code {result.returncode}',
            'stdout': result.stdout,
            'stderr': result.stderr
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error running action: {e}'
        }), 400

@app.route('/get_logs', methods=['GET'])
def get_logs():
    try:
        # Get logs from journalctl for the ledmatrix service
        result = subprocess.run(
            ['journalctl', '-u', 'ledmatrix.service', '-n', '500', '--no-pager'],
            capture_output=True, text=True, check=False
        )
        if result.returncode == 0:
            return jsonify({'status': 'success', 'logs': result.stdout})
        # Permission denied or other error: fall back to web UI log and return hint
        fallback_logs = ''
        try:
            with open('/tmp/web_interface_v2.log', 'r') as f:
                fallback_logs = f.read()
        except Exception:
            fallback_logs = '(No fallback web UI logs found)'
        hint = 'Insufficient permissions to read system journal. Add the web user to the systemd-journal group or configure sudoers for journalctl.'
        return jsonify({'status': 'error', 'message': f'Error fetching logs: {result.stderr or "permission denied"}\n\nHint: {hint}', 'fallback': fallback_logs}), 500
    except subprocess.CalledProcessError as e:
        # If the command fails, return the error
        error_message = f"Error fetching logs: {e.stderr}"
        return jsonify({'status': 'error', 'message': error_message}), 500
    except Exception as e:
        # Handle other potential exceptions
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/save_raw_json', methods=['POST'])
def save_raw_json_route():
    try:
        data = request.get_json()
        config_type = data.get('config_type')
        config_data = data.get('config_data')
        
        if not config_type or not config_data:
            return jsonify({
                'status': 'error',
                'message': 'Missing config_type or config_data'
            }), 400
        
        if config_type not in ['main', 'secrets']:
            return jsonify({
                'status': 'error',
                'message': 'Invalid config_type. Must be "main" or "secrets"'
            }), 400
        
        # Validate JSON format
        try:
            parsed_data = json.loads(config_data)
        except json.JSONDecodeError as e:
            return jsonify({
                'status': 'error',
                'message': f'Invalid JSON format: {str(e)}'
            }), 400
        
        # Save the raw JSON
        config_manager.save_raw_file_content(config_type, parsed_data)
        
        return jsonify({
            'status': 'success',
            'message': f'{config_type.capitalize()} configuration saved successfully!'
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error saving raw JSON: {str(e)}'
        }), 400

# Add news manager routes for compatibility
@app.route('/news_manager/status', methods=['GET'])
def get_news_manager_status():
    """Get news manager status and configuration"""
    try:
        config = config_manager.load_config()
        news_config = config.get('news_manager', {})
        
        # Try to get status from the running display controller if possible
        status = {
            'enabled': news_config.get('enabled', False),
            'enabled_feeds': news_config.get('enabled_feeds', []),
            'available_feeds': [
                'MLB', 'NFL', 'NCAA FB', 'NHL', 'NBA', 'TOP SPORTS', 
                'BIG10', 'NCAA', 'Other'
            ],
            'headlines_per_feed': news_config.get('headlines_per_feed', 2),
            'rotation_enabled': news_config.get('rotation_enabled', True),
            'custom_feeds': news_config.get('custom_feeds', {})
        }
        
        return jsonify({
            'status': 'success',
            'data': status
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error getting news manager status: {str(e)}'
        }), 400

@app.route('/news_manager/update_feeds', methods=['POST'])
def update_news_feeds():
    """Update enabled news feeds"""
    try:
        data = request.get_json()
        enabled_feeds = data.get('enabled_feeds', [])
        headlines_per_feed = data.get('headlines_per_feed', 2)
        
        config = config_manager.load_config()
        if 'news_manager' not in config:
            config['news_manager'] = {}
            
        config['news_manager']['enabled_feeds'] = enabled_feeds
        config['news_manager']['headlines_per_feed'] = headlines_per_feed
        
        config_manager.save_config(config)
        
        return jsonify({
            'status': 'success',
            'message': 'News feeds updated successfully!'
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error updating news feeds: {str(e)}'
        }), 400

@app.route('/news_manager/add_custom_feed', methods=['POST'])
def add_custom_news_feed():
    """Add a custom RSS feed"""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        url = data.get('url', '').strip()
        
        if not name or not url:
            return jsonify({
                'status': 'error',
                'message': 'Name and URL are required'
            }), 400
            
        config = config_manager.load_config()
        if 'news_manager' not in config:
            config['news_manager'] = {}
        if 'custom_feeds' not in config['news_manager']:
            config['news_manager']['custom_feeds'] = {}
            
        config['news_manager']['custom_feeds'][name] = url
        config_manager.save_config(config)
        
        return jsonify({
            'status': 'success',
            'message': f'Custom feed "{name}" added successfully!'
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error adding custom feed: {str(e)}'
        }), 400

@app.route('/news_manager/remove_custom_feed', methods=['POST'])
def remove_custom_news_feed():
    """Remove a custom RSS feed"""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        
        if not name:
            return jsonify({
                'status': 'error',
                'message': 'Feed name is required'
            }), 400
            
        config = config_manager.load_config()
        custom_feeds = config.get('news_manager', {}).get('custom_feeds', {})
        
        if name in custom_feeds:
            del custom_feeds[name]
            config_manager.save_config(config)
            
            return jsonify({
                'status': 'success',
                'message': f'Custom feed "{name}" removed successfully!'
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f'Custom feed "{name}" not found'
            }), 404
            
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error removing custom feed: {str(e)}'
        }), 400

@app.route('/news_manager/toggle', methods=['POST'])
def toggle_news_manager():
    """Toggle news manager on/off"""
    try:
        data = request.get_json()
        enabled = data.get('enabled', False)
        
        config = config_manager.load_config()
        if 'news_manager' not in config:
            config['news_manager'] = {}
            
        config['news_manager']['enabled'] = enabled
        config_manager.save_config(config)
        
        return jsonify({
            'status': 'success',
            'message': f'News manager {"enabled" if enabled else "disabled"} successfully!'
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error toggling news manager: {str(e)}'
        }), 400

@app.route('/logs')
def view_logs():
    """View system logs."""
    try:
        result = subprocess.run(
            ['journalctl', '-u', 'ledmatrix.service', '-n', '500', '--no-pager'],
            capture_output=True, text=True, check=False
        )
        logs = result.stdout if result.returncode == 0 else ''
        if result.returncode != 0:
            try:
                with open('/tmp/web_interface_v2.log', 'r') as f:
                    logs = f.read()
            except Exception:
                logs = 'Insufficient permissions to read journal. Add user to systemd-journal or configure sudoers for journalctl.'
        
        # Return logs as HTML page
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>System Logs</title>
            <style>
                body {{ font-family: monospace; background: #1e1e1e; color: #fff; padding: 20px; }}
                .log-container {{ background: #2d2d2d; padding: 20px; border-radius: 8px; }}
                .log-line {{ margin: 2px 0; }}
                .error {{ color: #ff6b6b; }}
                .warning {{ color: #feca57; }}
                .info {{ color: #48dbfb; }}
            </style>
        </head>
        <body>
            <h1>LED Matrix Service Logs</h1>
            <div class="log-container">
                <pre>{logs}</pre>
            </div>
            <script>
                // Auto-scroll to bottom
                window.scrollTo(0, document.body.scrollHeight);
            </script>
        </body>
        </html>
        """
    except subprocess.CalledProcessError as e:
        return f"Error fetching logs: {e.stderr}", 500
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/api/display/current')
def get_current_display():
    """Get current display image as base64."""
    return jsonify(current_display_data)

@app.route('/api/editor/layouts', methods=['GET'])
def get_custom_layouts():
    """Return saved custom layouts for the editor if available."""
    try:
        layouts_path = Path('config') / 'custom_layouts.json'
        if not layouts_path.exists():
            return jsonify({'status': 'success', 'data': {'elements': []}})
        with open(layouts_path, 'r') as f:
            data = json.load(f)
        return jsonify({'status': 'success', 'data': data})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    emit('connected', {'status': 'Connected to LED Matrix Interface'})
    # Send current display state immediately after connect
    try:
        if display_manager and hasattr(display_manager, 'image'):
            img_buffer = io.BytesIO()
            display_manager.image.save(img_buffer, format='PNG')
            img_str = base64.b64encode(img_buffer.getvalue()).decode()
            payload = {
                'image': img_str,
                'width': display_manager.width,
                'height': display_manager.height,
                'timestamp': time.time()
            }
            emit('display_update', payload)
        elif current_display_data:
            emit('display_update', current_display_data)
    except Exception as e:
        logger.error(f"Error sending initial display_update on connect: {e}")

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    print('Client disconnected')

def signal_handler(sig, frame):
    """Handle shutdown signals."""
    print('Shutting down web interface...')
    display_monitor.stop()
    if display_manager:
        display_manager.cleanup()
    sys.exit(0)

if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start the display monitor (runs even if display is not started yet for web preview)
    display_monitor.start()
    
    # Run the app
    # eventlet/gevent provide a proper WSGI server; Werkzeug is fine for dev
    socketio.run(app, host='0.0.0.0', port=5001, debug=False)