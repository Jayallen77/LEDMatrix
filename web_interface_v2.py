#!/usr/bin/env python3
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_socketio import SocketIO, emit
import json
import os
import subprocess
import threading
import time
import base64
from pathlib import Path
from src.config_manager import ConfigManager
from src.display_manager import DisplayManager
from PIL import Image
import io
import signal
import sys

app = Flask(__name__)
app.secret_key = os.urandom(24)
socketio = SocketIO(app, cors_allowed_origins="*")

# Global variables
config_manager = ConfigManager()
display_manager = None
display_thread = None
display_running = False
editor_mode = False
current_display_data = {}

class DisplayMonitor:
    def __init__(self):
        self.running = False
        self.thread = None
        
    def start(self):
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._monitor_loop)
            self.thread.daemon = True
            self.thread.start()
            
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()
            
    def _monitor_loop(self):
        global display_manager, current_display_data
        while self.running:
            try:
                if display_manager and hasattr(display_manager, 'image'):
                    # Convert PIL image to base64 for web display
                    img_buffer = io.BytesIO()
                    # Scale up the image for better visibility
                    scaled_img = display_manager.image.resize((
                        display_manager.image.width * 4,
                        display_manager.image.height * 4
                    ), Image.NEAREST)
                    scaled_img.save(img_buffer, format='PNG')
                    img_str = base64.b64encode(img_buffer.getvalue()).decode()
                    
                    current_display_data = {
                        'image': img_str,
                        'width': display_manager.width,
                        'height': display_manager.height,
                        'timestamp': time.time()
                    }
                    
                    # Emit to all connected clients
                    socketio.emit('display_update', current_display_data)
                    
            except Exception as e:
                print(f"Display monitor error: {e}")
                
            time.sleep(0.1)  # Update 10 times per second

display_monitor = DisplayMonitor()

@app.route('/')
def index():
    try:
        main_config = config_manager.load_config()
        schedule_config = main_config.get('schedule', {})
        
        # Get system status
        system_status = get_system_status()
        
        return render_template('index_v2.html', 
                             schedule_config=schedule_config,
                             main_config=main_config,
                             system_status=system_status,
                             editor_mode=editor_mode)
                             
    except Exception as e:
        flash(f"Error loading configuration: {e}", "error")
        return render_template('index_v2.html', 
                             schedule_config={},
                             main_config={},
                             system_status={},
                             editor_mode=False)

def get_system_status():
    """Get current system status including display state and performance metrics."""
    try:
        # Check if display service is running
        result = subprocess.run(['sudo', 'systemctl', 'is-active', 'ledmatrix'], 
                              capture_output=True, text=True)
        service_active = result.stdout.strip() == 'active'
        
        # Get memory usage
        with open('/proc/meminfo', 'r') as f:
            meminfo = f.read()
        
        mem_total = int([line for line in meminfo.split('\n') if 'MemTotal' in line][0].split()[1])
        mem_available = int([line for line in meminfo.split('\n') if 'MemAvailable' in line][0].split()[1])
        mem_used_percent = round((mem_total - mem_available) / mem_total * 100, 1)
        
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
        
        return {
            'service_active': service_active,
            'memory_used_percent': mem_used_percent,
            'cpu_temp': round(temp, 1),
            'uptime': f"{uptime_hours}h {uptime_minutes}m",
            'display_connected': display_manager is not None,
            'editor_mode': editor_mode
        }
    except Exception as e:
        return {
            'service_active': False,
            'memory_used_percent': 0,
            'cpu_temp': 0,
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
            display_manager = DisplayManager(config)
            display_monitor.start()
            
        display_running = True
        
        return jsonify({
            'status': 'success',
            'message': 'Display started successfully'
        })
    except Exception as e:
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
    global editor_mode, display_running
    
    try:
        editor_mode = not editor_mode
        
        if editor_mode:
            # Stop normal display operation
            display_running = False
            # Initialize display manager for editor if needed
            if not display_manager:
                config = config_manager.load_config()
                display_manager = DisplayManager(config)
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
            result = subprocess.run(['sudo', 'systemctl', 'restart', 'ledmatrix'], 
                                  capture_output=True, text=True)
        elif action == 'stop_service':
            result = subprocess.run(['sudo', 'systemctl', 'stop', 'ledmatrix'], 
                                  capture_output=True, text=True)
        elif action == 'start_service':
            result = subprocess.run(['sudo', 'systemctl', 'start', 'ledmatrix'], 
                                  capture_output=True, text=True)
        elif action == 'reboot_system':
            result = subprocess.run(['sudo', 'reboot'], 
                                  capture_output=True, text=True)
        elif action == 'git_pull':
            result = subprocess.run(['git', 'pull'], 
                                  capture_output=True, text=True, cwd='/workspace')
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
            'message': f'Error executing action: {e}'
        }), 500

@app.route('/api/system/status')
def get_system_status_api():
    """Get system status as JSON."""
    return jsonify(get_system_status())

@app.route('/logs')
def view_logs():
    """View system logs."""
    try:
        result = subprocess.run(
            ['sudo', 'journalctl', '-u', 'ledmatrix.service', '-n', '500', '--no-pager'],
            capture_output=True, text=True, check=True
        )
        logs = result.stdout
        
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

@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    emit('connected', {'status': 'Connected to LED Matrix Interface'})
    # Send current display state
    if current_display_data:
        emit('display_update', current_display_data)

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
    
    # Start the display monitor
    display_monitor.start()
    
    # Run the app
    socketio.run(app, host='0.0.0.0', port=5001, debug=False, allow_unsafe_werkzeug=True)