from flask import Flask, render_template_string, request, redirect, url_for, flash
import json
import os # Added os import
from src.config_manager import ConfigManager

app = Flask(__name__)
app.secret_key = os.urandom(24) # Needed for flash messages
config_manager = ConfigManager()

CONFIG_PAGE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>LED Matrix Config</title>
    <style>
        body { font-family: sans-serif; margin: 20px; background-color: #f4f4f4; color: #333; }
        .container { max-width: 800px; margin: auto; background: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 0 15px rgba(0,0,0,0.1); }
        h1 { text-align: center; color: #333; }
        .tabs {
            display: flex;
            border-bottom: 1px solid #ccc;
            margin-bottom: 20px;
        }
        .tab-button {
            padding: 10px 20px;
            cursor: pointer;
            border: none;
            background-color: transparent;
            font-size: 16px;
            border-bottom: 3px solid transparent;
        }
        .tab-button.active {
            border-bottom: 3px solid #4CAF50;
            font-weight: bold;
        }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        label { display: block; margin-top: 10px; font-weight: bold; }
        textarea { 
            width: 100%; 
            padding: 10px; 
            margin-top: 5px; 
            border-radius: 4px; 
            border: 1px solid #ccc; 
            box-sizing: border-box; 
            font-family: monospace;
            min-height: 300px;
        }
        input[type="submit"] { 
            background-color: #4CAF50; 
            color: white; 
            padding: 12px 25px; 
            border: none; 
            border-radius: 4px; 
            cursor: pointer; 
            margin-top: 20px;
            font-size: 16px;
        }
        input[type="submit"]:hover { background-color: #45a049; }
        .flash-messages {
            list-style: none;
            padding: 0;
            margin-bottom: 15px;
        }
        .flash-messages li {
            padding: 10px;
            margin-bottom: 10px;
            border-radius: 4px;
        }
        .flash-messages .success { background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .flash-messages .error { background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        .filepath { font-family: monospace; background-color: #eee; padding: 2px 5px; border-radius: 3px; font-size: 0.9em;}
        /* CodeMirror styling */
        .CodeMirror { border: 1px solid #ccc; border-radius: 4px; min-height: 300px; font-family: monospace; font-size: 14px; }
    </style>
    <!-- CodeMirror CSS -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/theme/material-palenight.min.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/addon/lint/lint.min.css">

</head>
<body>
    <div class="container">
        <h1>LED Matrix Configuration</h1>
        
        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            <ul class="flash-messages">
            {% for category, message in messages %}
              <li class="{{ category }}">{{ message }}</li>
            {% endfor %}
            </ul>
          {% endif %}
        {% endwith %}

        <div class="tabs">
            <button class="tab-button {% if active_tab == 'main' %}active{% endif %}" onclick="openTab('main')" data-tab="main">Main Config</button>
            <button class="tab-button {% if active_tab == 'secrets' %}active{% endif %}" onclick="openTab('secrets')" data-tab="secrets">Secrets Config</button>
        </div>

        <form method="post" action="{{ url_for('save_config_route') }}">
            <input type="hidden" name="config_type" id="config_type_hidden" value="{{ active_tab }}">
            
            <div id="main" class="tab-content {% if active_tab == 'main' %}active{% endif %}">
                <h2>Main Configuration (<span class="filepath">{{ main_config_path }}</span>)</h2>
                <label for="main_config_data">Edit {{ main_config_path }}:</label>
                <textarea name="main_config_data" rows="25">{{ main_config_json }}</textarea>
            </div>

            <div id="secrets" class="tab-content {% if active_tab == 'secrets' %}active{% endif %}">
                <h2>Secrets Configuration (<span class="filepath">{{ secrets_config_path }}</span>)</h2>
                <label for="secrets_config_data">Edit {{ secrets_config_path }}:</label>
                <textarea name="secrets_config_data" rows="25">{{ secrets_config_json }}</textarea>
            </div>
            
            <input type="submit" value="Save Current Tab's Configuration">
        </form>
    </div>

    <script>
        var mainEditor = null; // Declare editors in a scope accessible to openTab
        var secretsEditor = null;

        function openTab(tabName) {
            history.pushState(null, null, '{{ url_for("display_config_route") }}?tab=' + tabName);

            var i, tabcontent, tabbuttons;
            tabcontent = document.getElementsByClassName("tab-content");
            for (i = 0; i < tabcontent.length; i++) {
                tabcontent[i].classList.remove("active");
            }
            tabbuttons = document.getElementsByClassName("tab-button");
            for (i = 0; i < tabbuttons.length; i++) {
                tabbuttons[i].classList.remove("active");
            }

            document.getElementById(tabName).classList.add("active");
            document.querySelector(".tab-button[data-tab='" + tabName + "']").classList.add("active");
            document.getElementById("config_type_hidden").value = tabName;

            // Refresh the corresponding CodeMirror instance
            if (tabName === 'main' && mainEditor) {
                mainEditor.refresh();
            }
            if (tabName === 'secrets' && secretsEditor) {
                secretsEditor.refresh();
            }
        }

        document.addEventListener('DOMContentLoaded', function() {
            // Initialize CodeMirror for the main config textarea
            var mainConfigTextArea = document.querySelector("textarea[name='main_config_data']");
            if (mainConfigTextArea) {
                mainEditor = CodeMirror.fromTextArea(mainConfigTextArea, {
                    lineNumbers: true,
                    mode: {name: "javascript", json: true},
                    theme: "material-palenight",
                    gutters: ["CodeMirror-lint-markers"],
                    lint: true
                });
                new MutationObserver(() => mainEditor.refresh()).observe(document.getElementById('main'), {attributes: true, childList: false, subtree: false});
            }

            // Initialize CodeMirror for the secrets config textarea
            var secretsConfigTextArea = document.querySelector("textarea[name='secrets_config_data']");
            if (secretsConfigTextArea) {
                secretsEditor = CodeMirror.fromTextArea(secretsConfigTextArea, {
                    lineNumbers: true,
                    mode: {name: "javascript", json: true},
                    theme: "material-palenight",
                    gutters: ["CodeMirror-lint-markers"],
                    lint: true
                });
                new MutationObserver(() => secretsEditor.refresh()).observe(document.getElementById('secrets'), {attributes: true, childList: false, subtree: false});
            }
            
            // Ensure CodeMirror instances save their content back to textareas before form submission
            const form = document.querySelector('form');
            if (form) {
                form.addEventListener('submit', function() {
                    if (mainEditor) {
                        mainEditor.save();
                    }
                    if (secretsEditor) {
                        secretsEditor.save();
                    }
                });
            }
            
            // Initial tab setup from URL or default
            const params = new URLSearchParams(window.location.search);
            const initialTab = params.get('tab') || 'main';
            openTab(initialTab);
        });
    </script>

    <!-- CodeMirror JS (Corrected Order) -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jsonlint/1.6.3/jsonlint.min.js"></script> <!-- Defines global jsonlint -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/javascript/javascript.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/addon/lint/lint.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/addon/lint/json-lint.min.js"></script> <!-- Uses global jsonlint -->

</body>
</html>
"""

@app.route('/')
def display_config_route():
    active_tab = request.args.get('tab', 'main') # Default to 'main' tab
    main_config_data = {}
    secrets_config_data = {}
    error_message = None

    try:
        main_config_data = config_manager.get_raw_file_content('main')
    except Exception as e:
        flash(f"Error loading main config: {str(e)}", "error")

    try:
        secrets_config_data = config_manager.get_raw_file_content('secrets')
    except Exception as e:
        flash(f"Error loading secrets config: {str(e)}", "error")

    main_config_json = json.dumps(main_config_data, indent=4)
    secrets_config_json = json.dumps(secrets_config_data, indent=4)
    
    return render_template_string(CONFIG_PAGE_TEMPLATE, 
                                main_config_json=main_config_json, 
                                secrets_config_json=secrets_config_json, 
                                active_tab=active_tab,
                                main_config_path=config_manager.get_config_path(),
                                secrets_config_path=config_manager.get_secrets_path())

@app.route('/save', methods=['POST'])
def save_config_route():
    config_type = request.form.get('config_type', 'main')
    data_to_save_str = ""

    if config_type == 'main':
        data_to_save_str = request.form['main_config_data']
    elif config_type == 'secrets':
        data_to_save_str = request.form['secrets_config_data']
    else:
        flash("Invalid configuration type specified for saving.", "error")
        return redirect(url_for('display_config_route'))

    try:
        new_data = json.loads(data_to_save_str)
        config_manager.save_raw_file_content(config_type, new_data)
        flash(f"{config_type.capitalize()} configuration saved successfully!", "success")
    except json.JSONDecodeError:
        flash(f"Error: Invalid JSON format submitted for {config_type} config.", "error")
    except Exception as e:
        flash(f"Error saving {config_type} configuration: {str(e)}", "error")
    
    return redirect(url_for('display_config_route', tab=config_type)) # Redirect back to the same tab

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000) 