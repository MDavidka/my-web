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

# --- Globals & Setup ---
bot_processes = {}
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
ROOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'user_files')
if not os.path.exists(ROOT_DIR):
    os.makedirs(ROOT_DIR)
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

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
                        bots.append({'user_id': user_id, 'bot_index': i})
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
        with open(os.path.join(bot_path, 'main.py'), 'w') as f:
            f.write(f'# Bot Token: {bot_token}\nprint("Hello, bot!")')

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
    if not bot_path: return "Bot not found", 404

    path_rel = request.form.get('path')
    path_abs = get_safe_path(bot_path, path_rel)
    if not path_abs:
        return redirect(url_for('file_manager_index', user_id=user_id, bot_index=bot_index))

    with open(path_abs, 'w') as f:
        f.write(request.form.get('content', ''))

    return redirect(url_for('file_manager_index', user_id=user_id, bot_index=bot_index))

@app.route('/bot/<user_id>/<int:bot_index>/create', methods=['POST'])
def create_item(user_id, bot_index):
    bot_path, _, _ = get_bot_info(user_id, bot_index)
    if not bot_path: return "Bot not found", 404

    path_rel = request.form.get('path', '')
    base_path = get_safe_path(bot_path, path_rel)
    if not base_path:
        return redirect(url_for('file_manager_index', user_id=user_id, bot_index=bot_index))

    if 'filename' in request.form and request.form['filename']:
        new_path = os.path.join(base_path, request.form['filename'])
        if not os.path.exists(new_path):
            with open(new_path, 'w') as f: f.write('')
    elif 'foldername' in request.form and request.form['foldername']:
        new_path = os.path.join(base_path, request.form['foldername'])
        if not os.path.exists(new_path):
            os.makedirs(new_path)

    return redirect(url_for('file_manager_index', user_id=user_id, bot_index=bot_index))

@app.route('/bot/<user_id>/<int:bot_index>/delete', methods=['POST'])
def delete_item(user_id, bot_index):
    bot_path, _, _ = get_bot_info(user_id, bot_index)
    if not bot_path: return "Bot not found", 404

    path_rel = request.form.get('path')
    path_abs = get_safe_path(bot_path, path_rel)
    if not path_abs or path_abs == bot_path:
        return redirect(url_for('file_manager_index', user_id=user_id, bot_index=bot_index))

    if os.path.isfile(path_abs):
        os.remove(path_abs)
    elif os.path.isdir(path_abs):
        shutil.rmtree(path_abs)

    return redirect(url_for('file_manager_index', user_id=user_id, bot_index=bot_index))

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

# --- Main ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=30158, debug=False)
