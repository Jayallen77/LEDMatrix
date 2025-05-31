from flask import Flask, render_template_string, request, redirect, url_for
import json # Added import for json
from src.config_manager import ConfigManager

app = Flask(__name__)
config_manager = ConfigManager()

CONFIG_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>LED Matrix Config</title>
    <style>
        body { font-family: sans-serif; margin: 20px; }
        label { display: block; margin-top: 10px; }
        input[type="text"], textarea { width: 100%; padding: 8px; margin-top: 5px; border-radius: 4px; border: 1px solid #ccc; box-sizing: border-box; }
        input[type="submit"] { background-color: #4CAF50; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; margin-top: 20px;}
        input[type="submit"]:hover { background-color: #45a049; }
        .container { max-width: 600px; margin: auto; background: #f9f9f9; padding: 20px; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
        h1 { text-align: center; }
    </style>
</head>
<body>
    <div class="container">
        <h1>LED Matrix Configuration</h1>
        <form method="post" action="{{ url_for('save_config_route') }}">
            <label for="config_data">Configuration (JSON):</label>
            <textarea name="config_data" rows="20" cols="80">{{ config_json }}</textarea><br>
            <input type="submit" value="Save Configuration">
        </form>
    </div>
</body>
</html>
"""

@app.route('/')
def display_config_route():
    try:
        current_config = config_manager.load_config()
        # Pretty print JSON for the textarea
        config_json = json.dumps(current_config, indent=4)
        return render_template_string(CONFIG_TEMPLATE, config_json=config_json)
    except Exception as e:
        return f"Error loading configuration: {str(e)}", 500

@app.route('/save', methods=['POST'])
def save_config_route():
    try:
        new_config_str = request.form['config_data']
        new_config = json.loads(new_config_str) # Parse the JSON string from textarea
        config_manager.save_config(new_config)
        return redirect(url_for('display_config_route'))
    except json.JSONDecodeError:
        return "Error: Invalid JSON format submitted.", 400
    except Exception as e:
        return f"Error saving configuration: {str(e)}", 500

if __name__ == '__main__':
    # Make sure to run with debug=True only for development
    # In a production environment, use a proper WSGI server like Gunicorn
    app.run(debug=True, host='0.0.0.0', port=5000) 