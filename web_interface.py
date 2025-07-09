from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import json
import os
import subprocess
from src.config_manager import ConfigManager

app = Flask(__name__)
app.secret_key = os.urandom(24)
config_manager = ConfigManager()

@app.route('/')
def index():
    try:
        main_config = config_manager.load_config()
        schedule_config = main_config.get('schedule', {})
        
        main_config_data = config_manager.get_raw_file_content('main')
        secrets_config_data = config_manager.get_raw_file_content('secrets')
        main_config_json = json.dumps(main_config_data, indent=4)
        secrets_config_json = json.dumps(secrets_config_data, indent=4)
        
    except Exception as e:
        flash(f"Error loading configuration: {e}", "error")
        schedule_config = {}
        main_config_json = "{}"
        secrets_config_json = "{}"

    return render_template('index.html', 
                           schedule_config=schedule_config,
                           main_config_json=main_config_json,
                           secrets_config_json=secrets_config_json,
                           main_config_path=config_manager.get_config_path(),
                           secrets_config_path=config_manager.get_secrets_path())

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
        
        flash("Schedule updated successfully! Restart the display for changes to take effect.", "success")

    except Exception as e:
        flash(f"Error saving schedule: {e}", "error")

    return redirect(url_for('index'))

@app.route('/save_config', methods=['POST'])
def save_config_route():
    config_type = request.form.get('config_type')
    config_data_str = request.form.get('config_data')
    
    try:
        new_data = json.loads(config_data_str)
        config_manager.save_raw_file_content(config_type, new_data)
        flash(f"{config_type.capitalize()} configuration saved successfully!", "success")
    except json.JSONDecodeError:
        flash(f"Error: Invalid JSON format for {config_type} config.", "error")
    except Exception as e:
        flash(f"Error saving {config_type} configuration: {e}", "error")

    return redirect(url_for('index'))

@app.route('/run_action', methods=['POST'])
def run_action_route():
    data = request.get_json()
    action = data.get('action')
    
    commands = {
        'start_display': ["sudo", "python3", "display_controller.py"],
        'stop_display': ["sudo", "pkill", "-f", "display_controller.py"],
        'enable_autostart': ["sudo", "systemctl", "enable", "ledmatrix.service"],
        'disable_autostart': ["sudo", "systemctl", "disable", "ledmatrix.service"],
        'reboot_system': ["sudo", "reboot"],
        'git_pull': ["git", "pull"]
    }

    command_parts = commands.get(action)

    if not command_parts:
        return jsonify({"status": "error", "message": "Invalid action."}), 400

    try:
        result = subprocess.run(command_parts, capture_output=True, text=True, check=False)
        
        status = "success" if result.returncode == 0 else "error"
        message = f"Action '{action}' completed."
        
        return jsonify({
            "status": status,
            "message": message,
            "stdout": result.stdout,
            "stderr": result.stderr
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000) 