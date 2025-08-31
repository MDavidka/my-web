import os
import shutil
import subprocess
import psutil
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file
from pymongo import MongoClient
from bson.objectid import ObjectId
import certifi
from datetime import datetime
from functools import wraps

app = Flask(__name__)

# Config
REPO_URL = "https://github.com/MDavidka/my-web.git"
BRANCH = "feature/modern-file-editor"
DEST_DIR = os.path.dirname(os.path.abspath(__file__))

# --- App Configuration ---
app.config['MONGO_URI'] = "mongodb+srv://Cebelian12:testke12@cluster0.0p3pv8x.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
app.config['MONGO_DB_NAME'] = "dash-bot"

# --- Globals & Setup ---
bot_processes = {}
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
ROOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'user_files')
if not os.path.exists(ROOT_DIR):
    os.makedirs(ROOT_DIR)
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

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

# --- Database & Path Helpers ---
def get_db():
    client = MongoClient(app.config['MONGO_URI'], tlsCAFile=certifi.where())
    return client[app.config['MONGO_DB_NAME']]

def get_bot_info(user_id, bot_index):
    db = get_db()
    try:
        user = db.users.find_one({"_id": ObjectId(user_id)})
    except:
        user = db.users.find_one({"userId": user_id})

    if not user or 'servers' not in user or len(user['servers']) <= int(bot_index):
        return None, None, None

    bot_token = user['servers'][int(bot_index)].get('botToken')
    bot_path = os.path.join(ROOT_DIR, str(user.get('_id')), str(bot_index))
    log_file = os.path.join(LOG_DIR, f"{user_id}_{bot_index}.log")
    return bot_path, bot_token, log_file

def get_safe_path(base_path, user_path=''):
    safe_path = os.path.normpath(os.path.join(base_path, user_path))
    if not safe_path.startswith(os.path.normpath(base_path)):
        return None
    return safe_path

def get_last_modified(path):
    if not os.path.exists(path):
        return None

    latest_mtime = 0
    for root, _, files in os.walk(path):
        for file in files:
            try:
                mtime = os.path.getmtime(os.path.join(root, file))
                if mtime > latest_mtime:
                    latest_mtime = mtime
            except OSError:
                continue

    return latest_mtime if latest_mtime > 0 else None

# --- Main Routes ---
@app.route('/')
def list_bots():
    bots = []
    try:
        db = get_db()
        for user in db.users.find():
            user_id = str(user.get('_id'))
            if 'servers' in user and isinstance(user['servers'], list):
                for i, server in enumerate(user['servers']):
                    if 'botToken' in server:
                        bot_key = (user_id, i)
                        status = "RUNNING" if bot_key in bot_processes and bot_processes[bot_key].poll() is None else "STOPPED"

                        bot_path, _, _ = get_bot_info(user_id, i)
                        last_modified_timestamp = get_last_modified(bot_path)
                        last_modified_str = "Never"
                        if last_modified_timestamp:
                            last_modified_str = datetime.fromtimestamp(last_modified_timestamp).strftime('%b %d, %Y at %I:%M %p')

                        bot_name = server.get('name', f"Bot {i}")

                        bots.append({
                            'user_id': user_id,
                            'bot_index': i,
                            'name': bot_name,
                            'status': status,
                            'last_modified': last_modified_str
                        })
    except Exception as e:
        print(f"DB Error: {e}")
    return render_template("bot_list.html", bots=bots)

def get_file_tree(root_path, dir_path):
    items = []
    for name in sorted(os.listdir(dir_path)):
        full_path = os.path.join(dir_path, name)
        is_dir = os.path.isdir(full_path)
        item = {
            'name': name,
            'path': os.path.relpath(full_path, root_path),
            'is_dir': is_dir,
        }
        if is_dir:
            item['children'] = get_file_tree(root_path, full_path)
        items.append(item)
    return items

@app.route('/bot/<user_id>/<int:bot_index>/')
def file_manager_index(user_id, bot_index):
    bot_path, bot_token, _ = get_bot_info(user_id, bot_index)
    if not bot_path: return "Bot not found", 404

    if not os.path.exists(bot_path):
        os.makedirs(bot_path)
    if not os.path.exists(os.path.join(bot_path, 'main.py')):
        bot_code = f"# Bot Token: {bot_token}\n"
        bot_code += """import discord
import os

TOKEN = ""
with open(__file__, 'r') as f:
    first_line = f.readline()
    if 'Bot Token: ' in first_line:
        TOKEN = first_line.split('Bot Token: ')[1].strip()

if not TOKEN:
    print("FATAL: Bot token not found in the first line of main.py.")
    print("Please ensure the first line is '# Bot Token: YOUR_TOKEN_HERE'")
    exit()

class MyClient(discord.Client):
    async def on_ready(self):
        print(f'Logged on as {self.user}!')

    async def on_message(self, message):
        if message.author == self.user:
            return

        if message.content == '$ping':
            await message.channel.send('pong')

intents = discord.Intents.default()
intents.message_content = True
client = MyClient(intents=intents)
try:
    client.run(TOKEN)
except discord.errors.LoginFailure:
    print("FATAL: Improper token has been passed.")
    print("Please make sure you have the correct bot token in the first line of main.py")
except Exception as e:
    print(f"An unexpected error occurred: {e}")
"""
        with open(os.path.join(bot_path, 'main.py'), 'w') as f:
            f.write(bot_code)

    file_tree = get_file_tree(bot_path, bot_path)
    return render_template("file_manager.html", items=file_tree, user_id=user_id, bot_index=bot_index)

@app.route('/bot/<user_id>/<int:bot_index>/edit')
def edit_file(user_id, bot_index):
    bot_path, _, _ = get_bot_info(user_id, bot_index)
    if not bot_path: return "Bot not found", 404

    path_rel = request.args.get('path', '')
    path_abs = get_safe_path(bot_path, path_rel)
    if not path_abs or not os.path.isfile(path_abs):
        return redirect(url_for('file_manager_index', user_id=user_id, bot_index=bot_index))

    with open(path_abs, 'r') as f:
        content = f.read()

    return render_template("editor.html", content=content, path=path_rel, user_id=user_id, bot_index=bot_index)

@app.route('/bot/<user_id>/<int:bot_index>/save', methods=['POST'])
def save_file(user_id, bot_index):
    bot_path, _, _ = get_bot_info(user_id, bot_index)
    if not bot_path:
        return jsonify(success=False, message="Bot not found"), 404

    path_rel = request.form.get('path')
    path_abs = get_safe_path(bot_path, path_rel)
    if not path_abs:
        return jsonify(success=False, message="Invalid path"), 400

    try:
        with open(path_abs, 'w') as f:
            f.write(request.form.get('content', ''))
        return jsonify(success=True, message=f"File '{os.path.basename(path_rel)}' saved successfully.")
    except Exception as e:
        return jsonify(success=False, message=str(e)), 500

@app.route('/bot/<user_id>/<int:bot_index>/create', methods=['POST'])
def create_item(user_id, bot_index):
    bot_path, _, _ = get_bot_info(user_id, bot_index)
    if not bot_path: return jsonify(success=False, message="Bot not found"), 404

    item_type = request.form.get('type')
    item_name = request.form.get('name')
    base_rel_path = request.form.get('path', '')

    if not item_type or not item_name:
        return jsonify(success=False, message="Missing parameters"), 400
    if '/' in item_name or '..' in item_name:
        return jsonify(success=False, message="Invalid name"), 400

    base_abs_path = get_safe_path(bot_path, base_rel_path)
    if not base_abs_path or not os.path.isdir(base_abs_path):
        return jsonify(success=False, message="Invalid base path"), 400

    new_path = os.path.join(base_abs_path, item_name)
    if os.path.exists(new_path):
        return jsonify(success=False, message=f"'{item_name}' already exists"), 400

    try:
        if item_type == 'file':
            with open(new_path, 'w') as f: f.write('')
        elif item_type == 'folder':
            os.makedirs(new_path)
        else:
            return jsonify(success=False, message="Invalid type"), 400
        return jsonify(success=True, message=f"{item_type.capitalize()} '{item_name}' created")
    except OSError as e:
        return jsonify(success=False, message=str(e)), 500


@app.route('/bot/<user_id>/<int:bot_index>/rename', methods=['POST'])
def rename_item(user_id, bot_index):
    bot_path, _, _ = get_bot_info(user_id, bot_index)
    if not bot_path: return jsonify(success=False, message="Bot not found"), 404

    path_rel = request.form.get('path')
    new_name = request.form.get('new_name')

    if not path_rel or not new_name:
        return jsonify(success=False, message="Missing parameters"), 400
    if '/' in new_name or '..' in new_name:
        return jsonify(success=False, message="Invalid name"), 400

    old_path_abs = get_safe_path(bot_path, path_rel)
    if not old_path_abs or not os.path.exists(old_path_abs):
        return jsonify(success=False, message="Item not found"), 404

    new_path_abs = os.path.join(os.path.dirname(old_path_abs), new_name)
    if os.path.exists(new_path_abs):
        return jsonify(success=False, message="An item with that name already exists"), 400

    try:
        os.rename(old_path_abs, new_path_abs)
        return jsonify(success=True, message="Renamed successfully")
    except OSError as e:
        return jsonify(success=False, message=str(e)), 500


@app.route('/bot/<user_id>/<int:bot_index>/delete', methods=['POST'])
def delete_item(user_id, bot_index):
    bot_path, _, _ = get_bot_info(user_id, bot_index)
    if not bot_path: return jsonify(success=False, message="Bot not found"), 404

    path_rel = request.form.get('path')
    path_abs = get_safe_path(bot_path, path_rel)
    if not path_abs or path_abs == bot_path or not os.path.exists(path_abs):
        return jsonify(success=False, message="Item not found or is root"), 404

    try:
        if os.path.isfile(path_abs):
            os.remove(path_abs)
        elif os.path.isdir(path_abs):
            shutil.rmtree(path_abs)
        return jsonify(success=True, message="Item deleted successfully")
    except OSError as e:
        return jsonify(success=False, message=str(e)), 500

@app.route("/update", methods=["GET"])
def update_repo():
    output = git_pull()
    return jsonify({"status": "done", "output": output})

# --- Process Management ---
@app.route('/bot/<user_id>/<int:bot_index>/start')
def start_bot(user_id, bot_index):
    bot_key = (user_id, bot_index)
    if bot_key in bot_processes and bot_processes[bot_key].poll() is None:
        return redirect(url_for('file_manager_index', user_id=user_id, bot_index=bot_index))

    bot_path, _, log_file = get_bot_info(user_id, bot_index)
    if not bot_path: return "Bot not found", 404

    main_py = os.path.join(bot_path, 'main.py')
    if not os.path.exists(main_py):
        return "main.py not found", 404

    with open(log_file, 'w') as f:
        f.write('--- Starting bot... ---\n')
    log_handle = open(log_file, 'a')
    process = subprocess.Popen(['python', '-u', main_py], stdout=log_handle, stderr=log_handle, cwd=bot_path)
    bot_processes[bot_key] = process
    return redirect(url_for('file_manager_index', user_id=user_id, bot_index=bot_index))

@app.route('/bot/<user_id>/<int:bot_index>/stop')
def stop_bot(user_id, bot_index):
    bot_key = (user_id, bot_index)
    if bot_key in bot_processes and bot_processes[bot_key].poll() is None:
        try:
            parent = psutil.Process(bot_processes[bot_key].pid)
            for child in parent.children(recursive=True):
                child.kill()
            parent.kill()
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
    if bot_key in bot_processes and bot_processes[bot_key].poll() is None:
        try:
            p = psutil.Process(bot_processes[bot_key].pid)
            status = "RUNNING"
            ram = round(p.memory_info().rss / (1024 * 1024), 2)
        except psutil.NoSuchProcess:
            status = "STOPPED"
            if bot_key in bot_processes:
                del bot_processes[bot_key]
    return jsonify(status=status, ram_usage=ram)

@app.route('/bot/<user_id>/<int:bot_index>/logs')
def get_console_logs(user_id, bot_index):
    _, _, log_file = get_bot_info(user_id, bot_index)
    if not os.path.exists(log_file):
        return jsonify(log_data="", log_size=0)

    last_size = int(request.args.get('size', 0))
    current_size = os.path.getsize(log_file)

    if current_size > last_size:
        with open(log_file, 'r', encoding='utf-8') as f:
            f.seek(last_size)
            new_logs = f.read()
        return jsonify(log_data=new_logs, log_size=current_size)

    return jsonify(log_data="", log_size=current_size)

# --- API Routes ---
# NOTE: In a real-world app, API keys should be securely generated,
# stored, and retrieved per user from the database.
HARDCODED_API_KEY = "your-super-secret-api-key"

def require_api_key(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if not api_key or api_key != HARDCODED_API_KEY:
            return jsonify(error="Invalid or missing API key"), 403
        return func(*args, **kwargs)
    return decorated_function

@app.route('/api/bot/<user_id>/<int:bot_index>/file', methods=['GET'])
@require_api_key
def api_get_file(user_id, bot_index):
    bot_path, _, _ = get_bot_info(user_id, bot_index)
    if not bot_path:
        return jsonify(error="Bot not found"), 404

    # Ensure the base directory for the bot exists
    if not os.path.exists(bot_path):
        os.makedirs(bot_path)

    file_path_rel = request.args.get('path')
    if not file_path_rel:
        return jsonify(error="'path' query parameter is required"), 400

    file_path_abs = get_safe_path(bot_path, file_path_rel)
    if not file_path_abs or not os.path.isfile(file_path_abs):
        return jsonify(error="File not found"), 404

    try:
        with open(file_path_abs, 'r', encoding='utf-8') as f:
            content = f.read()
        return jsonify(path=file_path_rel, content=content)
    except Exception as e:
        return jsonify(error=str(e)), 500

@app.route('/api/bot/<user_id>/<int:bot_index>/file', methods=['POST'])
@require_api_key
def api_edit_file(user_id, bot_index):
    bot_path, _, _ = get_bot_info(user_id, bot_index)
    if not bot_path:
        return jsonify(error="Bot not found"), 404

    file_path_rel = request.args.get('path')
    if not file_path_rel:
        return jsonify(error="'path' query parameter is required"), 400

    file_path_abs = get_safe_path(bot_path, file_path_rel)
    if not file_path_abs: # Can be a new file
        return jsonify(error="Invalid file path"), 400

    if not request.is_json or 'content' not in request.json:
        return jsonify(error="Missing 'content' in JSON request body"), 400

    try:
        # Also ensure the subdirectory exists, if any
        dir_name = os.path.dirname(file_path_abs)
        if not os.path.exists(dir_name):
            os.makedirs(dir_name)

        with open(file_path_abs, 'w', encoding='utf-8') as f:
            f.write(request.json['content'])
        return jsonify(success=True, message=f"File '{file_path_rel}' updated successfully.")
    except Exception as e:
        return jsonify(error=str(e)), 500

@app.route('/api/bot/<user_id>/<int:bot_index>/start', methods=['POST'])
@require_api_key
def api_start_bot(user_id, bot_index):
    bot_key = (user_id, bot_index)
    if bot_key in bot_processes and bot_processes[bot_key].poll() is None:
        return jsonify(success=False, message="Bot is already running."), 409

    bot_path, _, log_file = get_bot_info(user_id, bot_index)
    if not bot_path:
        return jsonify(error="Bot not found"), 404

    main_py = os.path.join(bot_path, 'main.py')
    if not os.path.exists(main_py):
        return jsonify(error="main.py not found"), 404

    with open(log_file, 'w') as f:
        f.write('--- Starting bot via API... ---\n')
    log_handle = open(log_file, 'a')
    process = subprocess.Popen(['python', '-u', main_py], stdout=log_handle, stderr=log_handle, cwd=bot_path)
    bot_processes[bot_key] = process
    return jsonify(success=True, message="Bot started successfully.")

@app.route('/api/bot/<user_id>/<int:bot_index>/stop', methods=['POST'])
@require_api_key
def api_stop_bot(user_id, bot_index):
    bot_key = (user_id, bot_index)
    if bot_key not in bot_processes or bot_processes[bot_key].poll() is not None:
        return jsonify(success=False, message="Bot is not running."), 409

    try:
        parent = psutil.Process(bot_processes[bot_key].pid)
        for child in parent.children(recursive=True):
            child.kill()
        parent.kill()
        message = "Bot stopped successfully."
    except psutil.NoSuchProcess:
        message = "Process not found, but removed from tracking."
    finally:
        if bot_key in bot_processes:
            del bot_processes[bot_key]

    return jsonify(success=True, message=message)

@app.route('/api/docs')
def api_docs():
    return render_template('api_docs.html')


# --- Main ---
if __name__ == '__main__':
    # print("Pulling latest repo on start...")
    # print(git_pull())
    app.run(host='0.0.0.0', port=30158, debug=False)
