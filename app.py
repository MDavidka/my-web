import os
import shutil
import subprocess
import psutil
from flask import Flask, render_template_string, request, redirect, url_for, jsonify
from pymongo import MongoClient
from bson.objectid import ObjectId
import certifi

app = Flask(__name__)

# --- App Configuration ---
app.config['MONGO_URI'] = "mongodb+srv://Cebelian12:testke12@cluster0.0p3pv8x.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
app.config['MONGO_DB_NAME'] = "dash-bot"

# --- Globals for Process Management ---
# This will be refactored to handle multiple processes
bot_processes = {} # e.g., {(user_id, bot_index): process_object}
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')

# --- Database Helper ---
def get_db():
    client = MongoClient(app.config['MONGO_URI'], tlsCAFile=certifi.where())
    return client[app.config['MONGO_DB_NAME']]

# --- File System Root ---
ROOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'user_files')

# Create root directories if they don't exist
if not os.path.exists(ROOT_DIR):
    os.makedirs(ROOT_DIR)
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# --- Templates ---

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>File Manager</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: linear-gradient(to right, #232526, #414345);
            color: #e0e0e0;
            margin: 0;
            padding: 20px;
        }
        .container {
            max-width: 900px;
            margin: auto;
            background: rgba(30, 30, 30, 0.6);
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 20px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        }
        h1 {
            color: #fff;
            border-bottom: 1px solid rgba(255, 255, 255, 0.2);
            padding-bottom: 10px;
            margin-bottom: 20px;
            font-weight: 300;
        }
        .breadcrumb {
            margin-bottom: 20px;
        }
        .breadcrumb a {
            color: #00aaff;
            text-decoration: none;
        }
        .file-list {
            list-style: none;
            padding: 0;
        }
        .file-item {
            display: flex;
            align-items: center;
            padding: 10px;
            border-radius: 8px;
            transition: background-color 0.2s;
        }
        .file-item:hover {
            background-color: rgba(255, 255, 255, 0.05);
        }
        .file-item a {
            color: #e0e0e0;
            text-decoration: none;
            flex-grow: 1;
            margin-left: 10px;
        }
        .file-item .icon {
            width: 20px;
            height: 20px;
        }
        .folder { color: #58a6ff; }
        .file { color: #c9d1d9; }

        .actions {
            margin-top: 20px;
        }

        input[type="text"] {
            background-color: rgba(0,0,0,0.2);
            color: #eee;
            border: 1px solid rgba(255,255,255,0.2);
            padding: 8px 12px;
            border-radius: 5px;
            margin-right: 10px;
        }

        button {
            background-color: #333;
            color: #eee;
            border: 1px solid #555;
            padding: 8px 12px;
            border-radius: 5px;
            cursor: pointer;
            transition: background-color 0.2s;
        }
        button:hover {
            background-color: #444;
        }

        .delete-btn {
            background: #d12d2d;
            color: white;
            border: none;
        }
        .delete-btn:hover {
            background: #b02121;
        }

        .console-container {
            margin-top: 20px;
            background-color: #0d1117;
            border: 1px solid rgba(255,255,255,0.2);
            border-radius: 8px;
            padding: 15px;
        }

        #console-output {
            height: 300px;
            overflow-y: auto;
            background-color: transparent;
            color: #c9d1d9;
            font-family: "Courier New", Courier, monospace;
            white-space: pre-wrap;
            word-wrap: break-word;
        }

        .status-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }

        #bot-status {
            color: #ffc107;
        }

        #bot-status.running {
            color: #28a745;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="status-bar">
            <div>
                <a href="{{ url_for('start_bot', user_id=user_id, bot_index=bot_index) }}" class="btn-start">Start Bot</a>
                <a href="{{ url_for('stop_bot', user_id=user_id, bot_index=bot_index) }}" class="btn-stop">Stop Bot</a>
            </div>
            <div>
                <span>Status: <b id="bot-status">STOPPED</b></span> |
                <span>RAM: <b id="ram-usage">0 MB</b></span>
            </div>
        </div>
        <h1>File Manager for Bot {{ bot_index }} (User: {{ user_id }})</h1>
        <div class="breadcrumb">
            <a href="{{ url_for('list_bots') }}">Home</a> /
            <a href="{{ url_for('file_manager_index', user_id=user_id, bot_index=bot_index) }}">/</a>
            {% for part in breadcrumb %}
            <a href="{{ url_for('file_manager_index', user_id=user_id, bot_index=bot_index, path=part.path) }}">{{ part.name }}</a> /
            {% endfor %}
        </div>
        <ul class="file-list">
            {% for item in items %}
            <li class="file-item">
                {% if item.is_dir %}
                    <span class="icon folder">&#128193;</span> <!-- Folder Icon -->
                    <a href="{{ url_for('file_manager_index', user_id=user_id, bot_index=bot_index, path=item.path) }}">{{ item.name }}</a>
                {% else %}
                    <span class="icon file">&#128196;</span> <!-- File Icon -->
                    <a href="{{ url_for('edit_file', user_id=user_id, bot_index=bot_index, path=item.path) }}">{{ item.name }}</a>
                {% endif %}
                <form action="{{ url_for('delete_item', user_id=user_id, bot_index=bot_index) }}" method="post" style="margin-left: auto;">
                    <input type="hidden" name="path" value="{{ item.path }}">
                    <button type="submit" class="delete-btn" onclick="return confirm('Are you sure you want to delete this item?');">Delete</button>
                </form>
            </li>
            {% endfor %}
        </ul>
        <div class="actions">
            <form action="{{ url_for('create_file', user_id=user_id, bot_index=bot_index) }}" method="post" style="display:inline-block;">
                <input type="hidden" name="path" value="{{ current_path }}">
                <input type="text" name="filename" placeholder="New file name" required>
                <button type="submit">Create File</button>
            </form>
            <form action="{{ url_for('create_folder', user_id=user_id, bot_index=bot_index) }}" method="post" style="display:inline-block;">
                <input type="hidden" name="path" value="{{ current_path }}">
                <input type="text" name="foldername" placeholder="New folder name" required>
                <button type="submit">Create Folder</button>
            </form>
        </div>
    </div>
    <div class="container console-container">
        <h2>Console</h2>
        <div id="console-output"></div>
    </div>

    <script>
        const consoleOutput = document.getElementById('console-output');
        const botStatus = document.getElementById('bot-status');
        const ramUsage = document.getElementById('ram-usage');

        let lastLogSize = 0;

        async function fetchLogs() {
            // Only fetch logs if the console is visible
            if (!consoleOutput) return;
            const url = "{{ url_for('get_console_logs', user_id=user_id, bot_index=bot_index) }}?size=" + lastLogSize;
            const response = await fetch(url);
            if (response.ok) {
                const data = await response.json();
                if (data.log_data) {
                    consoleOutput.textContent += data.log_data;
                    consoleOutput.scrollTop = consoleOutput.scrollHeight;
                }
                lastLogSize = data.log_size;
            }
        }

        async function fetchStatus() {
            const url = "{{ url_for('get_bot_status', user_id=user_id, bot_index=bot_index) }}";
            const response = await fetch(url);
            if (response.ok) {
                const data = await response.json();
                botStatus.textContent = data.status;
                ramUsage.textContent = data.ram_usage + " MB";
                if (data.status === "RUNNING") {
                    botStatus.className = 'running';
                } else {
                    botStatus.className = '';
                }
            }
        }

        // Check if the status elements exist before fetching
        if (botStatus && ramUsage) {
            // Initial fetches
            fetchStatus();
            fetchLogs();

            // Poll
            setInterval(fetchStatus, 5000);
            setInterval(fetchLogs, 3000);
        }
    </script>
</body>
</html>
"""

EDITOR_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Edit File</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: linear-gradient(to right, #232526, #414345);
            color: #e0e0e0;
            margin: 0;
            padding: 20px;
        }
        .container {
            max-width: 900px;
            margin: auto;
            background: rgba(30, 30, 30, 0.6);
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 20px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        }
        h1 {
            color: #fff;
            border-bottom: 1px solid rgba(255, 255, 255, 0.2);
            padding-bottom: 10px;
            margin-bottom: 20px;
            font-weight: 300;
        }
        textarea {
            width: calc(100% - 22px); /* 100% - padding and border */
            height: 60vh;
            background-color: rgba(0,0,0,0.2);
            color: #f0f0f0;
            border: 1px solid rgba(255,255,255,0.2);
            border-radius: 8px;
            padding: 10px;
            font-family: "Courier New", Courier, monospace;
            box-sizing: border-box;
        }
        .btn-save {
            background: #007bff;
            color: white;
            border: none;
            padding: 10px 15px;
            border-radius: 5px;
            cursor: pointer;
            margin-top: 10px;
            transition: background-color 0.2s;
        }
        .btn-save:hover {
            background: #0056b3;
        }
        .btn-cancel {
            color: #aaa;
            text-decoration: none;
            margin-left: 15px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Edit: {{ path }}</h1>
        <form action="{{ url_for('save_file', user_id=user_id, bot_index=bot_index) }}" method="post">
            <input type="hidden" name="path" value="{{ path }}">
            <textarea name="content">{{ content }}</textarea>
            <br>
            <button type="submit" class="btn-save">Save Changes</button>
            <a href="{{ url_for('file_manager_index', user_id=user_id, bot_index=bot_index, path=parent_path) }}" class="btn-cancel">Cancel</a>
        </form>
    </div>
</body>
</html>
"""

BOT_LIST_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Select a Bot</title>
    <style>
        /* Reusing styles from the main template for consistency */
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: linear-gradient(to right, #232526, #414345);
            color: #e0e0e0;
            margin: 0;
            padding: 20px;
        }
        .container {
            max-width: 900px;
            margin: auto;
            background: rgba(30, 30, 30, 0.6);
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 20px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        }
        h1 {
            color: #fff;
            border-bottom: 1px solid rgba(255, 255, 255, 0.2);
            padding-bottom: 10px;
            margin-bottom: 20px;
            font-weight: 300;
        }
        .file-list { list-style: none; padding: 0; }
        .file-item {
            display: flex;
            align-items: center;
            padding: 10px;
            border-radius: 8px;
            transition: background-color 0.2s;
        }
        .file-item:hover { background-color: rgba(255, 255, 255, 0.05); }
        .file-item a {
            color: #58a6ff;
            text-decoration: none;
            flex-grow: 1;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Select a Bot to Manage</h1>
        {% if bots %}
        <ul class="file-list">
            {% for bot in bots %}
            <li class="file-item">
                <a href="{{ url_for('file_manager_index', user_id=bot.user_id, bot_index=bot.bot_index) }}">
                    Bot {{ loop.index }} (User: {{ bot.user_id }})
                </a>
            </li>
            {% endfor %}
        </ul>
        {% else %}
        <p>No bots found in the database.</p>
        {% endif %}
    </div>
</body>
</html>
"""

# --- Routes ---

@app.route('/')
def list_bots():
    try:
        db = get_db()
        # Assuming 'users' collection exists and documents have 'userId' and a 'servers' array.
        all_users = list(db.users.find())

        bots = []
        for user in all_users:
            # The user's document might use '_id' or a custom 'userId' field.
            # Here I am trying to be flexible. Let's assume 'userId' is the key.
            # If not present, I'll fall back to string representation of '_id'.
            user_id = user.get('userId', str(user.get('_id')))

            if 'servers' in user and isinstance(user['servers'], list):
                for i, server in enumerate(user['servers']):
                    if 'botToken' in server: # We only care about servers with a bot token
                        bots.append({
                            'user_id': user_id,
                            'bot_index': i
                        })

        return render_template_string(BOT_LIST_TEMPLATE, bots=bots)

    except Exception as e:
        print(f"Database connection failed: {e}")
        # Render a friendly error page if the DB is down
        return "<h1>Error connecting to the database.</h1><p>Please check the connection settings and ensure the database is running.</p>"

# --- Bot-Specific Helpers and Routes ---

def get_bot_info(user_id, bot_index):
    """A helper to retrieve bot-specific path and token."""
    db = get_db()

    # In a real app, you'd have a more robust way to find the user,
    # perhaps by a unique username or after a login.
    # For now, we assume user_id is the string representation of the MongoDB ObjectId
    if not ObjectId.is_valid(user_id):
        # A simple fallback for non-ObjectId userIds, though less robust.
        user = db.users.find_one({"userId": user_id})
    else:
        user = db.users.find_one({"_id": ObjectId(user_id)})

    if not user or 'servers' not in user or len(user['servers']) <= int(bot_index):
        return None, None, None

    bot_token = user['servers'][int(bot_index)].get('botToken')
    bot_path = os.path.join(ROOT_DIR, user_id, str(bot_index))
    log_file = os.path.join(LOG_DIR, f"{user_id}_{bot_index}.log")

    return bot_path, bot_token, log_file

@app.route('/bot/<user_id>/<int:bot_index>/files/')
def file_manager_index(user_id, bot_index):
    bot_path, bot_token, _ = get_bot_info(user_id, bot_index)
    if not bot_path:
        return "Bot not found", 404

    # Auto-generate main.py if it doesn't exist
    if not os.path.exists(bot_path):
        os.makedirs(bot_path)

    main_py_path = os.path.join(bot_path, 'main.py')
    if not os.path.exists(main_py_path):
        main_py_content = f'"""\nAuto-generated main.py for your bot.\nYour token is securely passed as an environment variable.\n"""\n\nimport os\n\nTOKEN = "{bot_token}"\n\nprint(f"Bot with token prefix {TOKEN[:8]}... is starting!")\n\n# Add your discord.py code here\n'
        with open(main_py_path, 'w', encoding='utf-8') as f:
            f.write(main_py_content)

    # File listing logic (adapted from old index route)
    req_path = request.args.get('path', '')
    # Security: ensure req_path is relative and doesn't escape the bot_path
    # os.path.normpath helps prevent '..' traversal. lstrip removes leading slashes.
    safe_req_path = os.path.normpath(req_path).lstrip('./\\')
    current_dir = os.path.join(bot_path, safe_req_path)

    if not os.path.normpath(current_dir).startswith(bot_path):
        return redirect(url_for('file_manager_index', user_id=user_id, bot_index=bot_index))

    if not os.path.exists(current_dir) or not os.path.isdir(current_dir):
         return redirect(url_for('file_manager_index', user_id=user_id, bot_index=bot_index))

    items = []
    for name in sorted(os.listdir(current_dir)):
        full_path = os.path.join(current_dir, name)
        # The path for links should be relative to the bot's root
        rel_path = os.path.relpath(full_path, bot_path)
        items.append({
            'name': name,
            'path': rel_path,
            'is_dir': os.path.isdir(full_path)
        })

    # Breadcrumb navigation
    breadcrumb = []
    if req_path:
        parts = req_path.split(os.sep)
        for i, part in enumerate(parts):
            breadcrumb.append({
                'name': part,
                'path': os.sep.join(parts[:i+1])
            })

    return render_template_string(HTML_TEMPLATE,
                                  items=items,
                                  breadcrumb=breadcrumb,
                                  current_path=req_path,
                                  user_id=user_id,
                                  bot_index=bot_index)


@app.route('/bot/<user_id>/<int:bot_index>/create_file', methods=['POST'])
def create_file(user_id, bot_index):
    bot_path, _, _ = get_bot_info(user_id, bot_index)
    if not bot_path: return "Bot not found", 404

    path = request.form.get('path', '')
    filename = request.form.get('filename')

    if not filename:
        return redirect(url_for('file_manager_index', user_id=user_id, bot_index=bot_index, path=path))

    safe_path = os.path.normpath(os.path.join(bot_path, path))
    if not safe_path.startswith(bot_path):
        return redirect(url_for('file_manager_index', user_id=user_id, bot_index=bot_index))

    file_path = os.path.join(safe_path, filename)

    if not os.path.exists(file_path):
        with open(file_path, 'w') as f:
            f.write('')

    return redirect(url_for('file_manager_index', user_id=user_id, bot_index=bot_index, path=path))

@app.route('/bot/<user_id>/<int:bot_index>/create_folder', methods=['POST'])
def create_folder(user_id, bot_index):
    bot_path, _, _ = get_bot_info(user_id, bot_index)
    if not bot_path: return "Bot not found", 404

    path = request.form.get('path', '')
    foldername = request.form.get('foldername')

    if not foldername:
        return redirect(url_for('file_manager_index', user_id=user_id, bot_index=bot_index, path=path))

    safe_path = os.path.normpath(os.path.join(bot_path, path))
    if not safe_path.startswith(bot_path):
        return redirect(url_for('file_manager_index', user_id=user_id, bot_index=bot_index))

    folder_path = os.path.join(safe_path, foldername)

    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    return redirect(url_for('file_manager_index', user_id=user_id, bot_index=bot_index, path=path))

@app.route('/bot/<user_id>/<int:bot_index>/edit')
def edit_file(user_id, bot_index):
    bot_path, _, _ = get_bot_info(user_id, bot_index)
    if not bot_path: return "Bot not found", 404

    path = request.args.get('path', '')
    if not path:
        return redirect(url_for('file_manager_index', user_id=user_id, bot_index=bot_index))

    safe_path = os.path.normpath(os.path.join(bot_path, path))
    if not safe_path.startswith(bot_path) or not os.path.isfile(safe_path):
        return redirect(url_for('file_manager_index', user_id=user_id, bot_index=bot_index))

    try:
        with open(safe_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading file {safe_path}: {e}")
        return redirect(url_for('file_manager_index', user_id=user_id, bot_index=bot_index, path=os.path.dirname(path)))

    parent_path = os.path.dirname(path)
    return render_template_string(EDITOR_TEMPLATE, path=path, content=content, parent_path=parent_path, user_id=user_id, bot_index=bot_index)

@app.route('/bot/<user_id>/<int:bot_index>/save', methods=['POST'])
def save_file(user_id, bot_index):
    bot_path, _, _ = get_bot_info(user_id, bot_index)
    if not bot_path: return "Bot not found", 404

    path = request.form.get('path')
    content = request.form.get('content', '')

    if not path:
        return redirect(url_for('file_manager_index', user_id=user_id, bot_index=bot_index))

    safe_path = os.path.normpath(os.path.join(bot_path, path))
    if not safe_path.startswith(bot_path):
        return redirect(url_for('file_manager_index', user_id=user_id, bot_index=bot_index))

    try:
        with open(safe_path, 'w', encoding='utf-8') as f:
            f.write(content)
    except Exception as e:
        print(f"Error writing to file {safe_path}: {e}")
        pass

    parent_path = os.path.dirname(path)
    return redirect(url_for('file_manager_index', user_id=user_id, bot_index=bot_index, path=parent_path))

@app.route('/bot/<user_id>/<int:bot_index>/delete_item', methods=['POST'])
def delete_item(user_id, bot_index):
    bot_path, _, _ = get_bot_info(user_id, bot_index)
    if not bot_path: return "Bot not found", 404

    path = request.form.get('path')

    if not path:
        return redirect(url_for('file_manager_index', user_id=user_id, bot_index=bot_index))

    safe_path = os.path.normpath(os.path.join(bot_path, path))
    if not safe_path.startswith(bot_path) or safe_path == bot_path:
        return redirect(url_for('file_manager_index', user_id=user_id, bot_index=bot_index))

    parent_path = os.path.dirname(path)

    try:
        if os.path.isfile(safe_path):
            os.remove(safe_path)
        elif os.path.isdir(safe_path):
            shutil.rmtree(safe_path)
    except OSError as e:
        print(f"Error deleting {safe_path}: {e}")
        pass

    return redirect(url_for('file_manager_index', user_id=user_id, bot_index=bot_index, path=parent_path))


# --- Process Management Routes (Refactored for Multi-Bot) ---

@app.route('/bot/<user_id>/<int:bot_index>/start')
def start_bot(user_id, bot_index):
    bot_key = (user_id, bot_index)

    if bot_key in bot_processes and bot_processes[bot_key]['process'].poll() is None:
        return redirect(url_for('file_manager_index', user_id=user_id, bot_index=bot_index))

    bot_path, _, log_file = get_bot_info(user_id, bot_index)
    if not bot_path: return "Bot not found", 404

    main_py_path = os.path.join(bot_path, 'main.py')
    if not os.path.exists(main_py_path):
        return redirect(url_for('file_manager_index', user_id=user_id, bot_index=bot_index))

    with open(log_file, 'w') as f:
        f.write('--- Starting bot... ---\n')

    log_file_handle = open(log_file, 'a')
    process = subprocess.Popen(
        ['python', '-u', main_py_path],
        stdout=log_file_handle,
        stderr=log_file_handle,
        cwd=bot_path
    )

    bot_processes[bot_key] = {
        'process': process,
        'log_file': log_file,
        'log_handle': log_file_handle
    }

    return redirect(url_for('file_manager_index', user_id=user_id, bot_index=bot_index))

@app.route('/bot/<user_id>/<int:bot_index>/stop')
def stop_bot(user_id, bot_index):
    bot_key = (user_id, bot_index)

    if bot_key in bot_processes and bot_processes[bot_key]['process'].poll() is None:
        try:
            proc_info = bot_processes[bot_key]
            process = proc_info['process']

            parent = psutil.Process(process.pid)
            for child in parent.children(recursive=True):
                child.kill()
            parent.kill()
            process.wait()

            proc_info['log_handle'].close()
        except psutil.NoSuchProcess:
            pass
        finally:
            del bot_processes[bot_key]

    return redirect(url_for('file_manager_index', user_id=user_id, bot_index=bot_index))

@app.route('/bot/<user_id>/<int:bot_index>/status')
def get_bot_status(user_id, bot_index):
    bot_key = (user_id, bot_index)
    status = "STOPPED"
    ram = 0

    if bot_key in bot_processes:
        process = bot_processes[bot_key]['process']
        if process.poll() is None:
            try:
                p = psutil.Process(process.pid)
                status = "RUNNING"
                ram = round(p.memory_info().rss / (1024 * 1024), 2)
            except psutil.NoSuchProcess:
                status = "STOPPED"
                del bot_processes[bot_key]
        else: # Process has terminated
            del bot_processes[bot_key]

    return jsonify(status=status, ram_usage=ram)

@app.route('/bot/<user_id>/<int:bot_index>/logs')
def get_console_logs(user_id, bot_index):
    bot_key = (user_id, bot_index)

    if bot_key not in bot_processes:
        # If process not running, check for a stale log file
        _, _, log_file = get_bot_info(user_id, bot_index)
        if not os.path.exists(log_file):
            return jsonify(log_data="", log_size=0)
    else:
        log_file = bot_processes[bot_key]['log_file']

    try:
        size = os.path.getsize(log_file)
        last_size = int(request.args.get('size', 0))
        if size > last_size:
            with open(log_file, 'r', encoding='utf-8') as f:
                f.seek(last_size)
                new_logs = f.read()
            return jsonify(log_data=new_logs, log_size=size)
    except FileNotFoundError:
        pass
    return jsonify(log_data="", log_size=0)


if __name__ == '__main__':
    # Clear any old log files on startup
    if os.path.exists(LOG_DIR):
        for filename in os.listdir(LOG_DIR):
            file_path = os.path.join(LOG_DIR, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print(f'Failed to delete {file_path}. Reason: {e}')

    app.run(debug=True, port=5000)
