import os
import shutil
import subprocess
import psutil
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file
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

# --- Git Auto-Puller ---
REPO_URL = "https://github.com/MDavidka/my-web.git"
BRANCH = "feature/flask-file-manager"
DEST_DIR = "/home/container"

def git_pull():
    """
    Pull latest changes or initialize repo if empty
    """
    git_dir = os.path.join(DEST_DIR, ".git")
    try:
        if not os.path.exists(git_dir):
            # Initialize repo if folder exists but is empty
            subprocess.run(["git", "init", DEST_DIR], capture_output=True, text=True)
            subprocess.run(["git", "-C", DEST_DIR, "remote", "add", "origin", REPO_URL], capture_output=True, text=True)
            subprocess.run(["git", "-C", DEST_DIR, "fetch", "--all"], capture_output=True, text=True)
            result = subprocess.run(["git", "-C", DEST_DIR, "reset", "--hard", f"origin/{BRANCH}"], capture_output=True, text=True)
            return result.stdout + result.stderr
        else:
            # Repo already exists, just fetch & reset
            fetch = subprocess.run(["git", "-C", DEST_DIR, "fetch", "--all"], capture_output=True, text=True)
            reset = subprocess.run(["git", "-C", DEST_DIR, "reset", "--hard", f"origin/{BRANCH}"], capture_output=True, text=True)
            return fetch.stdout + fetch.stderr + "\n" + reset.stdout + reset.stderr
    except Exception as e:
        return str(e)

@app.route("/update", methods=["GET"])
def update_repo():
    output = git_pull()
    return jsonify({"status": "done", "output": output})

# --- File System Root ---
ROOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'user_files')

# Create root directories if they don't exist
if not os.path.exists(ROOT_DIR):
    os.makedirs(ROOT_DIR)
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

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

        return render_template("bot_list.html", bots=bots)

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
    try:
        if not os.path.exists(bot_path):
            os.makedirs(bot_path, exist_ok=True)

        main_py_path = os.path.join(bot_path, 'main.py')
        if not os.path.exists(main_py_path):
            main_py_content = f'''
# Auto-generated main.py: A minimal, runnable Discord bot.
import discord
import os

# --- Configuration ---
# The bot token is securely passed in from the environment.
TOKEN = "{bot_token}"

# It's recommended to use intents for modern discord.py bots.
# Make sure to enable the 'Message Content Intent' in your bot's
# settings on the Discord Developer Portal.
intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

@client.event
async def on_ready():
    """Called when the bot is ready and logged in."""
    print(f'Successfully logged in as {{client.user}}')
    print('This is a minimal, working bot. You can now add your own commands and logic.')
    print('------')

@client.event
async def on_message(message):
    """Called every time a message is received."""
    # Don't let the bot reply to its own messages.
    if message.author == client.user:
        return

    if message.content.startswith('!hello'):
        await message.channel.send('Hello!')

# --- Running the Bot ---
try:
    print("Attempting to connect to Discord...")
    client.run(TOKEN)
except discord.errors.LoginFailure:
    print("\\n[ERROR] Login failed: An improper token was passed. Please check your bot's token in the database.")
except Exception as e:
    print(f"\\n[ERROR] An unexpected error occurred: {{e}}")
'''
            with open(main_py_path, 'w', encoding='utf-8') as f:
                f.write(main_py_content)
    except OSError as e:
        print(f"Error during initial setup for bot {user_id}/{bot_index}: {e}")
        return "<h1>Error: File System Permission Denied</h1><p>The application was unable to create necessary files or directories. Please check the server permissions.</p>", 500

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

    return render_template("file_manager.html",
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

    try:
        if not os.path.exists(file_path):
            with open(file_path, 'w') as f:
                f.write('')
    except OSError as e:
        print(f"Error creating file {file_path}: {e}")
        # Optionally, flash a message to the user about the error

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

    try:
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
    except OSError as e:
        print(f"Error creating folder {folder_path}: {e}")
        # Optionally, flash a message to the user about the error

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
    return render_template("editor.html", path=path, content=content, parent_path=parent_path, user_id=user_id, bot_index=bot_index)

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
    except OSError as e:
        print(f"Error writing to file {safe_path}: {e}")
        # Optionally, flash a message to the user
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
        # Optionally, flash a message to the user
        pass

    return redirect(url_for('file_manager_index', user_id=user_id, bot_index=bot_index, path=parent_path))

@app.route('/bot/<user_id>/<int:bot_index>/rename_item', methods=['POST'])
def rename_item(user_id, bot_index):
    bot_path, _, _ = get_bot_info(user_id, bot_index)
    if not bot_path: return "Bot not found", 404

    original_path_rel = request.form.get('original_path')
    new_name = request.form.get('new_name')

    if not original_path_rel or not new_name:
        return redirect(url_for('file_manager_index', user_id=user_id, bot_index=bot_index))

    original_path_abs = os.path.normpath(os.path.join(bot_path, original_path_rel))
    if not original_path_abs.startswith(bot_path) or original_path_abs == bot_path:
        return redirect(url_for('file_manager_index', user_id=user_id, bot_index=bot_index))

    parent_dir = os.path.dirname(original_path_abs)
    new_path_abs = os.path.join(parent_dir, new_name)

    try:
        os.rename(original_path_abs, new_path_abs)
    except OSError as e:
        print(f"Error renaming {original_path_abs} to {new_path_abs}: {e}")
        # Optionally, flash a message to the user
        pass

    parent_path_rel = os.path.dirname(original_path_rel)
    return redirect(url_for('file_manager_index', user_id=user_id, bot_index=bot_index, path=parent_path_rel))

@app.route('/bot/<user_id>/<int:bot_index>/download')
def download_file(user_id, bot_index):
    bot_path, _, _ = get_bot_info(user_id, bot_index)
    if not bot_path: return "Bot not found", 404

    path = request.args.get('path', '')
    if not path:
        return redirect(url_for('file_manager_index', user_id=user_id, bot_index=bot_index))

    safe_path = os.path.normpath(os.path.join(bot_path, path))
    if not safe_path.startswith(bot_path) or not os.path.isfile(safe_path):
        return redirect(url_for('file_manager_index', user_id=user_id, bot_index=bot_index))

    return send_file(safe_path, as_attachment=True)


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
    print("Pulling latest repo on start...")
    print(git_pull())

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

    app.run(host='0.0.0.0', port=30158, debug=False)
