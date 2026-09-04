# -*- coding: utf-8 -*-
"""
SHR FREE HOSTING BOT (HYBRID FIXED VERSION)
Premium Telegram bot with Subscription & Payment System
Owner: @the_innocent_hacker_raj
"""

import telebot
import subprocess
import os
import zipfile
import tempfile
import shutil
from telebot import types
import time
from datetime import datetime, timedelta
import psutil
import sqlite3
import logging
import threading
import re
import sys
import atexit
import requests
from flask import Flask
from threading import Thread

# --- Flask Keep Alive ---
app = Flask('')

@app.route('/')
def home():
    return "🤖 SHR FREE HOSTING BOT IS ALIVE!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()
    print("🚀 Flask Keep-Alive server started.")
# --- End Flask Keep Alive ---

# --- Configuration ---
TOKEN = '8810060186:AAFdP1xZmbeXVsUjWNpKCRhrvZ63xnOD_54'
OWNER_ID = 6492138723
ADMIN_ID = 6492138723
YOUR_USERNAME = '@the_innocent_hacker_raj'
UPDATE_CHANNEL = 'https://t.me/cyber_shr_1k'
BOT_NAME = "SHR FREE HOSTING BOT"

# QR Code Image URL (Direct Image Link or Web Page)
QR_CODE_URL = "https://ibb.co/1ffjd6N8"

# Folder setup - Ensuring directories exist
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_BOTS_DIR = os.path.join(BASE_DIR, 'upload_bots')
IROTECH_DIR = os.path.join(BASE_DIR, 'inf')
DATABASE_PATH = os.path.join(IROTECH_DIR, 'bot_data.db')

# --- SUBSCRIPTION PLANS ---
PLANS = {
    'starter': {
        'id': 'starter',
        'name': '🌟 Starter Plan',
        'price': 199,
        'price_display': '₹199',
        'file_limit': 10,
        'file_types': ['py'],
        'validity_days': 30,
        'description': '✅ 10 Python Files\n✅ 30 Days Validity\n✅ Basic Support'
    },
    'pro': {
        'id': 'pro',
        'name': '🔥 Pro Plan',
        'price': 499,
        'price_display': '₹499',
        'file_limit': 100,
        'file_types': ['py', 'js'],
        'validity_days': 90,
        'description': '✅ 100 Files (Python & JS)\n✅ 90 Days Validity\n✅ Priority Support'
    },
    'ultimate': {
        'id': 'ultimate',
        'name': '👑 Ultimate Plan',
        'price': 999,
        'price_display': '₹999',
        'file_limit': float('inf'),
        'file_types': ['py', 'js'],
        'validity_days': 365,
        'description': '✅ Unlimited Files\n✅ 1 Year Validity\n✅ 24×7 Premium Support'
    }
}

# Free user limit
FREE_USER_LIMIT = 1

# Initialize bot
bot = telebot.TeleBot(TOKEN)

# --- Data structures ---
bot_scripts = {}
user_subscriptions = {}
user_files = {}
active_users = set()
admin_ids = {ADMIN_ID, OWNER_ID}

# --- Pending Payments & Approvals ---
pending_payments = {}
pending_approvals = {}
_pending_counter = 0

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Database Setup ---
def init_db():
    # Creating directories explicitly to prevent "unable to open database file"
    os.makedirs(UPLOAD_BOTS_DIR, exist_ok=True)
    os.makedirs(IROTECH_DIR, exist_ok=True)
    
    logger.info(f"Initializing database at: {DATABASE_PATH}")
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS subscriptions
                     (user_id INTEGER PRIMARY KEY, expiry TEXT, plan_id TEXT, file_limit INTEGER)''')
        c.execute('''CREATE TABLE IF NOT EXISTS user_files
                     (user_id INTEGER, file_name TEXT, file_type TEXT,
                      PRIMARY KEY (user_id, file_name))''')
        c.execute('''CREATE TABLE IF NOT EXISTS active_users
                     (user_id INTEGER PRIMARY KEY)''')
        c.execute('''CREATE TABLE IF NOT EXISTS admins
                     (user_id INTEGER PRIMARY KEY)''')
        c.execute('''CREATE TABLE IF NOT EXISTS payment_history
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      user_id INTEGER, plan_id TEXT, amount INTEGER,
                      status TEXT, timestamp TEXT)''')
        c.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (OWNER_ID,))
        if ADMIN_ID != OWNER_ID:
            c.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (ADMIN_ID,))
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Database initialization error: {e}", exc_info=True)

def load_data():
    logger.info("Loading data from database...")
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()

        c.execute('SELECT user_id, expiry, plan_id, file_limit FROM subscriptions')
        for user_id, expiry, plan_id, file_limit in c.fetchall():
            try:
                user_subscriptions[user_id] = {
                    'expiry': datetime.fromisoformat(expiry),
                    'plan_id': plan_id,
                    'file_limit': file_limit
                }
            except ValueError:
                logger.warning(f"Invalid expiry date for user {user_id}")

        c.execute('SELECT user_id, file_name, file_type FROM user_files')
        for user_id, file_name, file_type in c.fetchall():
            if user_id not in user_files:
                user_files[user_id] = []
            user_files[user_id].append((file_name, file_type))

        c.execute('SELECT user_id FROM active_users')
        active_users.update(user_id for (user_id,) in c.fetchall())

        c.execute('SELECT user_id FROM admins')
        admin_ids.update(user_id for (user_id,) in c.fetchall())

        conn.close()
        logger.info(f"Data loaded: {len(active_users)} users, {len(user_subscriptions)} subscriptions.")
    except Exception as e:
        logger.error(f"Error loading data: {e}", exc_info=True)

init_db()
load_data()

# --- Helper Functions ---
def get_user_folder(user_id):
    user_folder = os.path.join(UPLOAD_BOTS_DIR, str(user_id))
    os.makedirs(user_folder, exist_ok=True)
    return user_folder

def get_user_file_limit(user_id):
    if user_id == OWNER_ID:
        return float('inf')
    if user_id in admin_ids:
        return 99999
    if user_id in user_subscriptions:
        sub = user_subscriptions[user_id]
        if sub.get('expiry', datetime.min) > datetime.now():
            return sub.get('file_limit', FREE_USER_LIMIT)
    return FREE_USER_LIMIT

def get_user_file_count(user_id):
    return len(user_files.get(user_id, []))

def get_user_status(user_id):
    if user_id == OWNER_ID:
        return "👑 Owner"
    if user_id in admin_ids:
        return "🛡️ Admin"
    if user_id in user_subscriptions:
        sub = user_subscriptions[user_id]
        if sub.get('expiry', datetime.min) > datetime.now():
            days_left = (sub['expiry'] - datetime.now()).days
            plan_name = PLANS.get(sub.get('plan_id', ''), {}).get('name', 'Premium')
            return f"⭐ {plan_name} ({days_left}d left)"
    return "🆓 Free User"

def is_bot_running(script_owner_id, file_name):
    script_key = f"{script_owner_id}_{file_name}"
    script_info = bot_scripts.get(script_key)
    if script_info and script_info.get('process'):
        try:
            proc = psutil.Process(script_info['process'].pid)
            is_running = proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
            if not is_running:
                if 'log_file' in script_info and hasattr(script_info['log_file'], 'close') and not script_info['log_file'].closed:
                    try:
                        script_info['log_file'].close()
                    except Exception:
                        pass
                if script_key in bot_scripts:
                    del bot_scripts[script_key]
            return is_running
        except psutil.NoSuchProcess:
            if script_key in bot_scripts:
                if 'log_file' in bot_scripts[script_key] and hasattr(bot_scripts[script_key]['log_file'], 'close'):
                    try:
                        bot_scripts[script_key]['log_file'].close()
                    except Exception:
                        pass
                del bot_scripts[script_key]
            return False
        except Exception as e:
            logger.error(f"Error checking process for {script_key}: {e}")
            return False
    return False

def kill_process_tree(process_info):
    try:
        if 'log_file' in process_info and hasattr(process_info['log_file'], 'close') and not process_info['log_file'].closed:
            try:
                process_info['log_file'].close()
            except Exception:
                pass
        process = process_info.get('process')
        if process and hasattr(process, 'pid') and process.pid:
            try:
                parent = psutil.Process(process.pid)
                parent.terminate()
                try:
                    parent.wait(timeout=2)
                except psutil.TimeoutExpired:
                    parent.kill()
            except psutil.NoSuchProcess:
                pass
            except Exception as e:
                logger.error(f"Error killing process: {e}")
    except Exception as e:
        logger.error(f"Error in kill_process_tree: {e}")

def _new_pending_id():
    global _pending_counter
    _pending_counter += 1
    return f"pend_{_pending_counter}"

# --- Database Operations ---
DB_LOCK = threading.Lock()

def save_user_file(user_id, file_name, file_type='py'):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            c.execute('INSERT OR REPLACE INTO user_files (user_id, file_name, file_type) VALUES (?, ?, ?)',
                      (user_id, file_name, file_type))
            conn.commit()
            if user_id not in user_files:
                user_files[user_id] = []
            user_files[user_id] = [(fn, ft) for fn, ft in user_files[user_id] if fn != file_name]
            user_files[user_id].append((file_name, file_type))
        except Exception as e:
            logger.error(f"Error saving file: {e}")
        finally:
            conn.close()

def remove_user_file_db(user_id, file_name):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            c.execute('DELETE FROM user_files WHERE user_id = ? AND file_name = ?', (user_id, file_name))
            conn.commit()
            if user_id in user_files:
                user_files[user_id] = [f for f in user_files[user_id] if f[0] != file_name]
                if not user_files[user_id]:
                    del user_files[user_id]
        except Exception as e:
            logger.error(f"Error removing file: {e}")
        finally:
            conn.close()

def add_active_user(user_id):
    active_users.add(user_id)
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            c.execute('INSERT OR IGNORE INTO active_users (user_id) VALUES (?)', (user_id,))
            conn.commit()
        except Exception as e:
            logger.error(f"Error adding active user: {e}")
        finally:
            conn.close()

def save_subscription(user_id, expiry, plan_id, file_limit):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            expiry_str = expiry.isoformat()
            c.execute('INSERT OR REPLACE INTO subscriptions (user_id, expiry, plan_id, file_limit) VALUES (?, ?, ?, ?)',
                      (user_id, expiry_str, plan_id, file_limit))
            conn.commit()
            user_subscriptions[user_id] = {
                'expiry': expiry,
                'plan_id': plan_id,
                'file_limit': file_limit
            }
        except Exception as e:
            logger.error(f"Error saving subscription: {e}")
        finally:
            conn.close()

def remove_subscription_db(user_id):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            c.execute('DELETE FROM subscriptions WHERE user_id = ?', (user_id,))
            conn.commit()
            if user_id in user_subscriptions:
                del user_subscriptions[user_id]
        except Exception as e:
            logger.error(f"Error removing subscription: {e}")
        finally:
            conn.close()

def add_payment_record(user_id, plan_id, amount, status='pending'):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            c.execute('''INSERT INTO payment_history (user_id, plan_id, amount, status, timestamp)
                         VALUES (?, ?, ?, ?, ?)''',
                      (user_id, plan_id, amount, status, datetime.now().isoformat()))
            conn.commit()
        except Exception as e:
            logger.error(f"Error adding payment record: {e}")
        finally:
            conn.close()

def update_payment_status(user_id, status):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        try:
            c.execute('''UPDATE payment_history SET status = ? 
                         WHERE user_id = ? AND status = 'pending' 
                         ORDER BY id DESC LIMIT 1''', (status, user_id))
            conn.commit()
        except Exception as e:
            logger.error(f"Error updating payment status: {e}")
        finally:
            conn.close()

# --- Button Layouts ---
MAIN_MENU_BUTTONS = [
    ["📢 Updates Channel", "📤 Upload File"],
    ["📂 My Files", "⚡ Bot Speed"],
    ["💎 Subscription Plans", "📊 Statistics"],
    ["📞 Contact Owner"]
]

ADMIN_MENU_BUTTONS = [
    ["📢 Updates Channel", "📤 Upload File"],
    ["📂 My Files", "⚡ Bot Speed"],
    ["💎 Subscription Plans", "📊 Statistics"],
    ["💳 Manage Subscriptions", "📢 Broadcast"],
    ["🟢 Run All Scripts", "⏳ Pending Files"],
    ["📋 Running Files", "📋 Pending Payments"],   # <-- NEW ROW with both buttons
    ["👑 Admin Panel", "📞 Contact Owner"]
]

# --- Menu Functions ---
def create_main_menu_inline(user_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        types.InlineKeyboardButton('📢 Updates Channel', url=UPDATE_CHANNEL),
        types.InlineKeyboardButton('📤 Upload File', callback_data='upload'),
        types.InlineKeyboardButton('📂 My Files', callback_data='check_files'),
        types.InlineKeyboardButton('💎 Plans', callback_data='show_plans'),
        types.InlineKeyboardButton('⚡ Bot Speed', callback_data='speed'),
        types.InlineKeyboardButton('📊 Statistics', callback_data='stats'),
        types.InlineKeyboardButton('📞 Contact Owner', url=f'https://t.me/{YOUR_USERNAME.replace("@", "")}')
    ]
    
    if user_id in admin_ids:
        admin_buttons = [
            types.InlineKeyboardButton('💳 Subscriptions', callback_data='subscription'),
            types.InlineKeyboardButton('📢 Broadcast', callback_data='broadcast'),
            types.InlineKeyboardButton('👑 Admin Panel', callback_data='admin_panel'),
            types.InlineKeyboardButton('🟢 Run All Scripts', callback_data='run_all_scripts'),
            types.InlineKeyboardButton('⏳ Pending Files', callback_data='pending_files'),
            types.InlineKeyboardButton('📋 Pending Payments', callback_data='pending_payments_list')
        ]
        markup.add(buttons[0])
        markup.add(buttons[1], buttons[2])
        markup.add(buttons[3], buttons[4])
        markup.add(buttons[5], admin_buttons[0])
        markup.add(admin_buttons[1], admin_buttons[2])
        markup.add(admin_buttons[3], admin_buttons[4])
        markup.add(admin_buttons[5])
        markup.add(buttons[6])
    else:
        markup.add(buttons[0])
        markup.add(buttons[1], buttons[2])
        markup.add(buttons[3], buttons[4])
        markup.add(buttons[5])
        markup.add(buttons[6])
    
    return markup

def create_reply_keyboard_main_menu(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    layout = ADMIN_MENU_BUTTONS if user_id in admin_ids else MAIN_MENU_BUTTONS
    for row in layout:
        markup.add(*[types.KeyboardButton(text) for text in row])
    return markup

def create_plans_markup():
    markup = types.InlineKeyboardMarkup(row_width=1)
    for plan_id, plan in PLANS.items():
        markup.add(types.InlineKeyboardButton(
            f"{plan['name']} - {plan['price_display']}",
            callback_data=f"buy_plan_{plan_id}"
        ))
    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data='back_to_main'))
    return markup

def create_control_buttons(script_owner_id, file_name, is_running=True):
    markup = types.InlineKeyboardMarkup(row_width=2)
    if is_running:
        markup.row(
            types.InlineKeyboardButton("🔴 Stop", callback_data=f'stop_{script_owner_id}_{file_name}'),
            types.InlineKeyboardButton("🔄 Restart", callback_data=f'restart_{script_owner_id}_{file_name}')
        )
        markup.row(
            types.InlineKeyboardButton("🗑️ Delete", callback_data=f'delete_{script_owner_id}_{file_name}'),
            types.InlineKeyboardButton("📜 Logs", callback_data=f'logs_{script_owner_id}_{file_name}')
        )
    else:
        markup.row(
            types.InlineKeyboardButton("🟢 Start", callback_data=f'start_{script_owner_id}_{file_name}'),
            types.InlineKeyboardButton("🗑️ Delete", callback_data=f'delete_{script_owner_id}_{file_name}')
        )
        markup.row(
            types.InlineKeyboardButton("📜 View Logs", callback_data=f'logs_{script_owner_id}_{file_name}')
        )
    markup.add(types.InlineKeyboardButton("🔙 Back to Files", callback_data='check_files'))
    return markup

def create_admin_panel():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.row(
        types.InlineKeyboardButton('➕ Add Admin', callback_data='add_admin'),
        types.InlineKeyboardButton('➖ Remove Admin', callback_data='remove_admin')
    )
    markup.row(types.InlineKeyboardButton('📋 List Admins', callback_data='list_admins'))
    markup.row(types.InlineKeyboardButton('📊 Payment History', callback_data='payment_history'))
    markup.row(types.InlineKeyboardButton('🔙 Back to Main', callback_data='back_to_main'))
    return markup

def create_subscription_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.row(
        types.InlineKeyboardButton('➕ Add Subscription', callback_data='add_subscription'),
        types.InlineKeyboardButton('➖ Remove Subscription', callback_data='remove_subscription')
    )
    markup.row(types.InlineKeyboardButton('🔍 Check Subscription', callback_data='check_subscription'))
    markup.row(types.InlineKeyboardButton('📊 Payment History', callback_data='payment_history'))
    markup.row(types.InlineKeyboardButton('🔙 Back to Main', callback_data='back_to_main'))
    return markup

def create_confirm_payment_markup():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.row(
        types.InlineKeyboardButton('✅ Confirm Payment', callback_data='confirm_payment'),
        types.InlineKeyboardButton('❌ Cancel', callback_data='cancel_payment')
    )
    return markup

# --- Script Runner Functions ---
TELEGRAM_MODULES = {
    'telebot': 'pyTelegramBotAPI',
    'telegram': 'python-telegram-bot',
    'aiogram': 'aiogram',
    'pyrogram': 'pyrogram',
    'telethon': 'telethon',
    'requests': 'requests',
    'flask': 'Flask',
    'psutil': 'psutil',
    'sqlite3': None,
    'json': None,
    'datetime': None,
    'os': None,
    'sys': None,
    're': None,
    'time': None,
    'math': None,
    'random': None,
    'logging': None,
    'threading': None,
    'subprocess': None,
    'zipfile': None,
    'tempfile': None,
    'shutil': None,
    'atexit': None,
    'signal': None,
}

def attempt_install_pip(module_name, message):
    package_name = TELEGRAM_MODULES.get(module_name.lower(), module_name)
    if package_name is None:
        return False
    try:
        bot.reply_to(message, f"🐍 Installing <code>{package_name}</code>...", parse_mode='HTML')
        command = [sys.executable, '-m', 'pip', 'install', package_name]
        result = subprocess.run(command, capture_output=True, text=True, check=False, encoding='utf-8', errors='ignore')
        if result.returncode == 0:
            bot.reply_to(message, f"✅ Package <code>{package_name}</code> installed.", parse_mode='HTML')
            return True
        else:
            bot.reply_to(message, f"❌ Failed to install <code>{package_name}</code>.", parse_mode='HTML')
            return False
    except Exception as e:
        bot.reply_to(message, f"❌ Install error: {str(e)}")
        return False

def run_script(script_path, script_owner_id, user_folder, file_name, message_obj, attempt=1):
    max_attempts = 2
    if attempt > max_attempts:
        return

    script_key = f"{script_owner_id}_{file_name}"
    logger.info(f"Running script: {script_path} for user {script_owner_id}")

    try:
        if not os.path.exists(script_path):
            bot.reply_to(message_obj, f"❌ Script '{file_name}' not found!")
            remove_user_file_db(script_owner_id, file_name)
            return

        if attempt == 1:
            check_command = [sys.executable, script_path]
            check_proc = None
            try:
                check_proc = subprocess.Popen(check_command, cwd=user_folder, 
                                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                             text=True, encoding='utf-8', errors='ignore')
                stdout, stderr = check_proc.communicate(timeout=5)
                if check_proc.returncode != 0 and stderr:
                    match = re.search(r"ModuleNotFoundError: No module named '(.+?)'", stderr)
                    if match:
                        module_name = match.group(1)
                        if attempt_install_pip(module_name, message_obj):
                            time.sleep(2)
                            threading.Thread(target=run_script, args=(
                                script_path, script_owner_id, user_folder, file_name, message_obj, attempt + 1
                            )).start()
                            return
                    bot.reply_to(message_obj, f"❌ Script error:\n<pre>{stderr[:500]}</pre>", parse_mode='HTML')
                    return
            except subprocess.TimeoutExpired:
                if check_proc and check_proc.poll() is None:
                    check_proc.kill()
                    check_proc.communicate()
            except Exception as e:
                bot.reply_to(message_obj, f"❌ Check error: {str(e)}")
                return
            finally:
                if check_proc and check_proc.poll() is None:
                    check_proc.kill()
                    check_proc.communicate()

        log_file_path = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}.log")
        log_file = open(log_file_path, 'w', encoding='utf-8', errors='ignore')
        
        process = subprocess.Popen(
            [sys.executable, script_path],
            cwd=user_folder,
            stdout=log_file,
            stderr=log_file,
            stdin=subprocess.PIPE,
            encoding='utf-8',
            errors='ignore'
        )
        
        bot_scripts[script_key] = {
            'process': process,
            'log_file': log_file,
            'file_name': file_name,
            'script_owner_id': script_owner_id,
            'start_time': datetime.now(),
            'user_folder': user_folder,
            'type': 'py',
            'script_key': script_key
        }
        
        bot.reply_to(message_obj, f"✅ Script '{file_name}' started! (PID: {process.pid})")

    except Exception as e:
        logger.error(f"Error running script: {e}")
        bot.reply_to(message_obj, f"❌ Error: {str(e)}")
        if script_key in bot_scripts:
            kill_process_tree(bot_scripts[script_key])
            del bot_scripts[script_key]

def run_js_script(script_path, script_owner_id, user_folder, file_name, message_obj, attempt=1):
    max_attempts = 2
    if attempt > max_attempts:
        return

    script_key = f"{script_owner_id}_{file_name}"
    logger.info(f"Running JS script: {script_path} for user {script_owner_id}")

    try:
        if not os.path.exists(script_path):
            bot.reply_to(message_obj, f"❌ Script '{file_name}' not found!")
            remove_user_file_db(script_owner_id, file_name)
            return

        if attempt == 1:
            check_command = ['node', script_path]
            check_proc = None
            try:
                check_proc = subprocess.Popen(check_command, cwd=user_folder,
                                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                             text=True, encoding='utf-8', errors='ignore')
                stdout, stderr = check_proc.communicate(timeout=5)
                if check_proc.returncode != 0 and stderr:
                    match = re.search(r"Cannot find module '(.+?)'", stderr)
                    if match:
                        module_name = match.group(1)
                        if not module_name.startswith('.') and not module_name.startswith('/'):
                            bot.reply_to(message_obj, f"🟠 Installing <code>{module_name}</code>...", parse_mode='HTML')
                            npm_result = subprocess.run(['npm', 'install', module_name], 
                                                       cwd=user_folder, capture_output=True,
                                                       text=True, encoding='utf-8', errors='ignore')
                            if npm_result.returncode == 0:
                                bot.reply_to(message_obj, f"✅ NPM package installed.", parse_mode='HTML')
                                time.sleep(2)
                                threading.Thread(target=run_js_script, args=(
                                    script_path, script_owner_id, user_folder, file_name, message_obj, attempt + 1
                                )).start()
                                return
                    bot.reply_to(message_obj, f"❌ JS Error:\n<pre>{stderr[:500]}</pre>", parse_mode='HTML')
                    return
            except subprocess.TimeoutExpired:
                if check_proc and check_proc.poll() is None:
                    check_proc.kill()
                    check_proc.communicate()
            except FileNotFoundError:
                bot.reply_to(message_obj, "❌ Node.js not found! Please install Node.js.")
                return
            except Exception as e:
                bot.reply_to(message_obj, f"❌ Check error: {str(e)}")
                return
            finally:
                if check_proc and check_proc.poll() is None:
                    check_proc.kill()
                    check_proc.communicate()

        log_file_path = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}.log")
        log_file = open(log_file_path, 'w', encoding='utf-8', errors='ignore')
        
        process = subprocess.Popen(
            ['node', script_path],
            cwd=user_folder,
            stdout=log_file,
            stderr=log_file,
            stdin=subprocess.PIPE,
            encoding='utf-8',
            errors='ignore'
        )
        
        bot_scripts[script_key] = {
            'process': process,
            'log_file': log_file,
            'file_name': file_name,
            'script_owner_id': script_owner_id,
            'start_time': datetime.now(),
            'user_folder': user_folder,
            'type': 'js',
            'script_key': script_key
        }
        
        bot.reply_to(message_obj, f"✅ JS Script '{file_name}' started! (PID: {process.pid})")

    except Exception as e:
        logger.error(f"Error running JS script: {e}")
        bot.reply_to(message_obj, f"❌ Error: {str(e)}")
        if script_key in bot_scripts:
            kill_process_tree(bot_scripts[script_key])
            del bot_scripts[script_key]

# --- File Handling ---
def handle_zip_file(downloaded_file_content, file_name_zip, message):
    user_id = message.from_user.id
    user_folder = get_user_folder(user_id)
    temp_dir = None
    
    try:
        temp_dir = tempfile.mkdtemp(prefix=f"user_{user_id}_zip_")
        zip_path = os.path.join(temp_dir, file_name_zip)
        
        with open(zip_path, 'wb') as f:
            f.write(downloaded_file_content)
            
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            for member in zip_ref.infolist():
                member_path = os.path.abspath(os.path.join(temp_dir, member.filename))
                if not member_path.startswith(os.path.abspath(temp_dir)):
                    raise zipfile.BadZipFile("Unsafe path in zip")
            zip_ref.extractall(temp_dir)

        extracted_items = os.listdir(temp_dir)
        py_files = [f for f in extracted_items if f.endswith('.py')]
        js_files = [f for f in extracted_items if f.endswith('.js')]
        
        # Check for requirements.txt
        if 'requirements.txt' in extracted_items:
            req_path = os.path.join(temp_dir, 'requirements.txt')
            bot.reply_to(message, "🔄 Installing Python dependencies...")
            result = subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', req_path],
                                   capture_output=True, text=True, encoding='utf-8', errors='ignore')
            if result.returncode == 0:
                bot.reply_to(message, "✅ Dependencies installed.")
            else:
                bot.reply_to(message, f"❌ Failed to install dependencies:\n<pre>{result.stderr[:300]}</pre>", parse_mode='HTML')

        # Find main script
        main_script_name = None
        file_type = None
        
        for p in ['main.py', 'bot.py', 'app.py']:
            if p in py_files:
                main_script_name = p
                file_type = 'py'
                break
                
        if not main_script_name:
            for p in ['index.js', 'main.js', 'bot.js', 'app.js']:
                if p in js_files:
                    main_script_name = p
                    file_type = 'js'
                    break
                    
        if not main_script_name and py_files:
            main_script_name = py_files[0]
            file_type = 'py'
        elif not main_script_name and js_files:
            main_script_name = js_files[0]
            file_type = 'js'
            
        if not main_script_name:
            bot.reply_to(message, "❌ No Python or JS script found in zip!")
            return

        # Move files to user folder
        for item in os.listdir(temp_dir):
            src = os.path.join(temp_dir, item)
            dst = os.path.join(user_folder, item)
            if os.path.isdir(dst):
                shutil.rmtree(dst)
            elif os.path.exists(dst):
                os.remove(dst)
            shutil.move(src, dst)

        save_user_file(user_id, main_script_name, file_type)
        main_script_path = os.path.join(user_folder, main_script_name)
        
        bot.reply_to(message, f"✅ Extracted and starting <code>{main_script_name}</code>...", parse_mode='HTML')
        
        if file_type == 'py':
            threading.Thread(target=run_script, args=(main_script_path, user_id, user_folder, main_script_name, message)).start()
        else:
            threading.Thread(target=run_js_script, args=(main_script_path, user_id, user_folder, main_script_name, message)).start()

    except zipfile.BadZipFile as e:
        bot.reply_to(message, f"❌ Invalid zip file: {e}")
    except Exception as e:
        logger.error(f"Error processing zip: {e}")
        bot.reply_to(message, f"❌ Error: {str(e)}")
    finally:
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except Exception:
                pass

def handle_py_file(file_path, script_owner_id, user_folder, file_name, message):
    try:
        save_user_file(script_owner_id, file_name, 'py')
        threading.Thread(target=run_script, args=(file_path, script_owner_id, user_folder, file_name, message)).start()
    except Exception as e:
        logger.error(f"Error handling py file: {e}")
        bot.reply_to(message, f"❌ Error: {str(e)}")

def handle_js_file(file_path, script_owner_id, user_folder, file_name, message):
    try:
        save_user_file(script_owner_id, file_name, 'js')
        threading.Thread(target=run_js_script, args=(file_path, script_owner_id, user_folder, file_name, message)).start()
    except Exception as e:
        logger.error(f"Error handling js file: {e}")
        bot.reply_to(message, f"❌ Error: {str(e)}")

# --- Core Logic Functions ---
def _logic_send_welcome(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    user_name = message.from_user.first_name
    user_username = message.from_user.username

    logger.info(f"Welcome: {user_id}")

    if user_id not in active_users:
        add_active_user(user_id)
        try:
            owner_msg = f"🎉 New User!\n👤 Name: {user_name}\n🆔 ID: <code>{user_id}</code>"
            bot.send_message(OWNER_ID, owner_msg, parse_mode='HTML')
        except Exception:
            pass

    file_limit = get_user_file_limit(user_id)
    current_files = get_user_file_count(user_id)
    limit_str = "∞" if file_limit == float('inf') else str(file_limit)
    status = get_user_status(user_id)
    
    # Check if user needs to upgrade
    needs_upgrade = (user_id not in admin_ids and user_id != OWNER_ID and 
                     user_id not in user_subscriptions)

    welcome_msg = f"""
╔══════════════════════╗
║   🤖 {BOT_NAME}  🤖
╚══════════════════════╝

👋 Welcome, {user_name}!

🆔 Your ID: <code>{user_id}</code>
✳️ Username: @{user_username or 'Not set'}
🔰 Status: {status}
📁 Files: {current_files} / {limit_str}

━━━━━━━━━━━━━━━━━━━━━━━━━
<b>📌 How to Use:</b>
• Upload <code>.py</code>, <code>.js</code>, or <code>.zip</code> files
• Each file runs in its own process
• View logs and manage files

📤 <b>Free Users:</b> Only 1 file allowed
💎 <b>Premium Users:</b> Unlimited files
━━━━━━━━━━━━━━━━━━━━━━━━━
"""

    if needs_upgrade:
        welcome_msg += """
💡 <b>Want to host more files?</b>
🔹 Get premium for unlimited hosting!
🔹 Click 💎 Subscription Plans

🎯 <b>Premium Benefits:</b>
• Unlimited file hosting
• 24×7 bot uptime
• 24×7 Priority support
• More file types supported
"""

    welcome_msg += "\n👇 Use the buttons below to get started!"

    # Try to send user's profile photo with the welcome message (DP)
    sent_with_photo = False
    try:
        photos = bot.get_user_profile_photos(user_id, limit=1)
        if photos and photos.photos:
            file_id = photos.photos[0][-1].file_id
            bot.send_photo(
                chat_id, 
                file_id, 
                caption=welcome_msg,
                reply_markup=create_reply_keyboard_main_menu(user_id),
                parse_mode='HTML'
            )
            sent_with_photo = True
    except Exception as e:
        logger.error(f"Error sending photo: {e}")

    # Fallback if photo fails or user doesn't have DP
    if not sent_with_photo:
        try:
            bot.send_message(
                chat_id, 
                welcome_msg, 
                reply_markup=create_reply_keyboard_main_menu(user_id),
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Error sending welcome: {e}")
            # Ultimate fallback: send without parse_mode and with keyboard
            bot.send_message(
                chat_id, 
                welcome_msg.replace('<b>', '').replace('</b>', '').replace('<code>', '').replace('</code>', ''),
                reply_markup=create_reply_keyboard_main_menu(user_id)
            )

def _logic_show_plans(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    plans_text = "━━━ <b>💎 SUBSCRIPTION PLANS</b> ━━━\n\n"
    
    for plan_id, plan in PLANS.items():
        plans_text += f"""
<b>{plan['name']}</b>
━━━━━━━━━━━━━━━━━━━
💰 Price: {plan['price_display']}
📅 Validity: {plan['validity_days']} days
📁 File Limit: {plan['file_limit'] if plan['file_limit'] != float('inf') else '∞'}
📂 File Types: {', '.join(plan['file_types']).upper()}

{plan['description']}
━━━━━━━━━━━━━━━━━━━
"""
    
    plans_text += """
📌 <b>How to Purchase:</b>
1️⃣ Select your plan below
2️⃣ Pay via UPI/QR Code
3️⃣ Send payment screenshot
4️⃣ Admin approves & activates

✨ All plans include 24×7 support!
"""

    try:
        bot.send_message(chat_id, plans_text, 
                        reply_markup=create_plans_markup(),
                        parse_mode='HTML')
    except Exception as e:
        logger.error(f"Error showing plans: {e}")
        bot.reply_to(message, "💎 Check plans via /plans command.")

def _logic_buy_plan(call, plan_id):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    plan = PLANS.get(plan_id)
    if not plan:
        bot.answer_callback_query(call.id, "❌ Plan not found!")
        return
    
    # Check if user already has active subscription
    if user_id in user_subscriptions:
        sub = user_subscriptions[user_id]
        if sub.get('expiry', datetime.min) > datetime.now():
            bot.answer_callback_query(call.id, "⚠️ You already have an active subscription!", show_alert=True)
            return
    
    # Store pending payment
    pending_payments[user_id] = {
        'plan_id': plan_id,
        'timestamp': datetime.now()
    }
    
    payment_text = f"""
╔══════════════════════╗
║   💳 <b>Payment Instructions</b>   💳
╚══════════════════════╝

📋 <b>Plan Details:</b>
━━━━━━━━━━━━━━━━━━━━━
📌 Plan: {plan['name']}
💰 Amount: {plan['price_display']}
📅 Validity: {plan['validity_days']} days
━━━━━━━━━━━━━━━━━━━━━

📌 <b>How to Pay:</b>
1️⃣ Scan QR Code below or Open QR Website
2️⃣ Pay {plan['price_display']} via UPI
3️⃣ Click "✅ Confirm Payment"
4️⃣ Send payment screenshot
5️⃣ Wait for admin approval

⚠️ <b>Note:</b> Your plan activates only after admin approval.

🔹 <b>UPI ID:</b> 70suman28@okicici
"""
    
    # Create markup with QR code link
    qr_markup = types.InlineKeyboardMarkup(row_width=1)
    qr_markup.row(
        types.InlineKeyboardButton('🌐 Open QR Website', url=QR_CODE_URL),
        types.InlineKeyboardButton('✅ Confirm Payment', callback_data='confirm_payment'),
        types.InlineKeyboardButton('❌ Cancel', callback_data='cancel_payment')
    )
    
    try:
        # Attempt to send QR code directly as an image.
        bot.send_photo(
            chat_id,
            QR_CODE_URL,
            caption=payment_text,
            reply_markup=qr_markup,
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"QR Image send error: {e}")
        # Fallback: Send text with URL button
        bot.send_message(
            chat_id,
            payment_text,
            reply_markup=qr_markup,
            parse_mode='HTML'
        )
    
    bot.answer_callback_query(call.id, "💳 Payment instructions sent!")

def _logic_confirm_payment(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    if user_id not in pending_payments:
        bot.answer_callback_query(call.id, "⚠️ No pending payment found!", show_alert=True)
        return
    
    plan_id = pending_payments[user_id]['plan_id']
    plan = PLANS.get(plan_id)
    if not plan:
        bot.answer_callback_query(call.id, "❌ Plan error!", show_alert=True)
        return
    
    try:
        # Add payment record
        add_payment_record(user_id, plan_id, plan['price'], 'pending')
        
        # Notify user
        bot.send_message(chat_id, """
✅ <b>Payment Initiated!</b>

📤 Please send the payment screenshot here.
🔹 Make sure the screenshot shows:
   - UPI transaction ID
   - Payment amount
   - Date and time

⏳ Admin will verify and activate your plan.

Type /cancel_payment to cancel this request.
""", parse_mode='HTML')
        
        # Notify admins: A preliminary request notification
        for admin_id in admin_ids:
            try:
                admin_msg = f"""
╔══════════════════════╗
║   💰 <b>New Payment Request</b>   💰
╚══════════════════════╝

👤 User ID: <code>{user_id}</code>
👤 Username: @{call.from_user.username or 'N/A'}
📋 Plan: {plan['name']}
💰 Amount: {plan['price_display']}
📅 Duration: {plan['validity_days']} days

📌 <b>Instructions:</b>
⏳ Waiting for screenshot from user...
"""
                bot.send_message(admin_id, admin_msg, parse_mode='HTML')
            except Exception:
                pass
        
        bot.answer_callback_query(call.id, "✅ Payment initiated! Please send the screenshot.")
    except Exception as e:
        logger.error(f"Confirm payment error: {e}")
        bot.answer_callback_query(call.id, "❌ An error occurred. Please try again.", show_alert=True)

def _logic_cancel_payment(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    if user_id in pending_payments:
        del pending_payments[user_id]
        bot.send_message(chat_id, "❌ Payment cancelled.")
    
    bot.answer_callback_query(call.id, "Payment cancelled.")
    _logic_send_welcome(call.message)

def _logic_upload_file(message):
    user_id = message.from_user.id
    
    # Check file limit
    file_limit = get_user_file_limit(user_id)
    current_files = get_user_file_count(user_id)
    
    if current_files >= file_limit:
        limit_str = "∞" if file_limit == float('inf') else str(file_limit)
        status = get_user_status(user_id)
        
        upgrade_msg = f"""
⚠️ <b>File Limit Reached!</b>

📁 Current: {current_files} / {limit_str}
👤 Status: {status}

💎 <b>Upgrade to Premium:</b>
• Unlimited file hosting
• 24×7 bot uptime
• Priority support
• More file types

🔹 Click 💎 Subscription Plans to upgrade!
"""
        bot.reply_to(message, upgrade_msg, parse_mode='HTML')
        return
    
    bot.reply_to(message, """
📤 <b>Upload File</b>

Send your file:
• <code>.py</code> - Python script
• <code>.js</code> - JavaScript script
• <code>.zip</code> - Archive with files

📁 Files will run automatically after upload.
🔹 Max file size: 20 MB
""", parse_mode='HTML')

def _logic_check_files(message):
    user_id = message.from_user.id
    user_files_list = user_files.get(user_id, [])
    
    if not user_files_list:
        bot.reply_to(message, "📂 <b>Your Files</b>\n\nNo files uploaded yet.", parse_mode='HTML')
        return
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for file_name, file_type in sorted(user_files_list):
        is_running = is_bot_running(user_id, file_name)
        status = "🟢 Running" if is_running else "🔴 Stopped"
        markup.add(types.InlineKeyboardButton(
            f"{file_name} ({file_type}) - {status}",
            callback_data=f'file_{user_id}_{file_name}'
        ))
    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data='back_to_main'))
    
    bot.reply_to(message, "📂 <b>Your Files</b>\nClick to manage:", 
                reply_markup=markup, parse_mode='HTML')

def _logic_bot_speed(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    start_time = time.time()
    wait_msg = bot.reply_to(message, "⏳ Testing speed...")
    
    try:
        bot.send_chat_action(chat_id, 'typing')
        response_time = round((time.time() - start_time) * 1000, 2)
        
        speed_msg = f"""
⚡ <b>Bot Speed & Status</b>

⏱️ Response: {response_time} ms
👤 Your Status: {get_user_status(user_id)}

📊 System Info:
• Python: {sys.version.split()[0]}
• Uptime: Running
• Processes: {len(bot_scripts)} running
"""
        bot.edit_message_text(speed_msg, chat_id, wait_msg.message_id, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Speed test error: {e}")
        bot.edit_message_text("❌ Speed test failed.", chat_id, wait_msg.message_id)

def _logic_statistics(message):
    user_id = message.from_user.id
    
    total_users = len(active_users)
    total_files = sum(len(files) for files in user_files.values())
    running_bots = len(bot_scripts)
    premium_users = sum(1 for uid, sub in user_subscriptions.items() 
                       if sub.get('expiry', datetime.min) > datetime.now())
    
    stats_msg = f"""
📊 <b>Bot Statistics</b>

👥 Total Users: {total_users}
⭐ Premium Users: {premium_users}
📁 Total Files: {total_files}
🟢 Running Bots: {running_bots}
📂 File Types: Python, JavaScript
💰 Free Limit: {FREE_USER_LIMIT} file

━━━━━━━━━━━━━━━━━━
🤖 {BOT_NAME}
📢 {UPDATE_CHANNEL}
"""
    
    if user_id in admin_ids:
        stats_msg += f"""
━━━━━━━━━━━━━━━━━━
🛡️ <b>Admin Info</b>
👑 Owner: <code>{OWNER_ID}</code>
📋 Admins: {len(admin_ids)}
"""
    
    bot.reply_to(message, stats_msg, parse_mode='HTML')

def _logic_contact_owner(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton('📞 Contact Owner', url=f'https://t.me/{YOUR_USERNAME.replace("@", "")}'))
    bot.reply_to(message, "📞 <b>Contact Owner</b>\n\nClick below to message the bot owner.", 
                reply_markup=markup, parse_mode='HTML')

def _logic_updates_channel(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton('📢 Join Updates Channel', url=UPDATE_CHANNEL))
    bot.reply_to(message, "📢 <b>Updates Channel</b>\n\nJoin for latest updates and announcements!",
                reply_markup=markup, parse_mode='HTML')

# --- NEW: View all running files for admin ---
def _logic_view_running_files(message):
    """Display a list of all currently running scripts for admin to manage."""
    user_id = message.from_user.id
    if user_id not in admin_ids:
        bot.reply_to(message, "⚠️ Admin only.")
        return

    if not bot_scripts:
        bot.reply_to(message, "📋 No scripts are currently running.")
        return

    markup = types.InlineKeyboardMarkup(row_width=1)
    for script_key, info in bot_scripts.items():
        # script_key format: owner_id_file_name
        parts = script_key.split('_', 1)
        if len(parts) == 2:
            owner_id_str, file_name = parts
            owner_id = int(owner_id_str)
            # Button text shows file name and owner
            btn_text = f"📄 {file_name} (User {owner_id})"
            markup.add(types.InlineKeyboardButton(
                btn_text,
                callback_data=f'file_{owner_id}_{file_name}'
            ))
        else:
            # fallback, should not happen
            markup.add(types.InlineKeyboardButton(
                f"📄 Unknown ({script_key})",
                callback_data='back_to_main'
            ))

    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data='back_to_main'))
    bot.reply_to(message, "📋 <b>Running Scripts</b>\nClick a file to manage it:", 
                reply_markup=markup, parse_mode='HTML')

# --- Admin Logic Functions ---
def _logic_subscriptions_panel(message):
    if message.from_user.id not in admin_ids:
        bot.reply_to(message, "⚠️ Admin only.")
        return
    bot.reply_to(message, "💳 <b>Subscription Management</b>\n\nManage user subscriptions:", 
                reply_markup=create_subscription_menu(), parse_mode='HTML')

def _logic_broadcast_init(message):
    if message.from_user.id not in admin_ids:
        bot.reply_to(message, "⚠️ Admin only.")
        return
    msg = bot.reply_to(message, "📢 <b>Broadcast Message</b>\n\nSend the message to broadcast to all users.\nSend /cancel to cancel.", 
                      parse_mode='HTML')
    bot.register_next_step_handler(msg, process_broadcast_message)

def process_broadcast_message(message):
    if message.from_user.id not in admin_ids:
        return
    if message.text and message.text.lower() == '/cancel':
        bot.reply_to(message, "❌ Broadcast cancelled.")
        return
    
    broadcast_text = message.text
    target_count = len(active_users)
    
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("✅ Confirm", callback_data=f"confirm_broadcast_{message.message_id}"),
        types.InlineKeyboardButton("❌ Cancel", callback_data="cancel_broadcast")
    )
    
    preview = broadcast_text[:500] + ("..." if len(broadcast_text) > 500 else "")
    bot.reply_to(message, f"⚠️ <b>Confirm Broadcast</b>\n\nTo {target_count} users:\n\n<pre>{preview}</pre>\n\nSend?",
                reply_markup=markup, parse_mode='HTML')

def execute_broadcast(broadcast_text, admin_chat_id):
    sent = 0
    failed = 0
    
    for user_id in list(active_users):
        try:
            bot.send_message(user_id, broadcast_text, parse_mode='HTML')
            sent += 1
            time.sleep(0.1)
        except Exception:
            failed += 1
            continue
        
        if sent % 20 == 0:
            time.sleep(0.5)
    
    result_msg = f"""
📢 <b>Broadcast Complete</b>

✅ Sent: {sent}
❌ Failed: {failed}
👥 Total: {len(active_users)}
"""
    bot.send_message(admin_chat_id, result_msg, parse_mode='HTML')

def _logic_admin_panel(message):
    if message.from_user.id not in admin_ids:
        bot.reply_to(message, "⚠️ Admin only.")
        return
    bot.reply_to(message, "👑 <b>Admin Panel</b>\n\nManage bot settings:", 
                reply_markup=create_admin_panel(), parse_mode='HTML')

def _logic_pending_files(message):
    if message.from_user.id not in admin_ids:
        bot.reply_to(message, "⚠️ Admin only.")
        return
    
    if not pending_approvals:
        bot.reply_to(message, "⏳ No pending files.")
        return
    
    for pid, info in list(pending_approvals.items()):
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("✅ Approve", callback_data=f"approve_{pid}"),
            types.InlineKeyboardButton("❌ Reject", callback_data=f"reject_{pid}")
        )
        bot.send_message(
            message.chat.id,
            f"📄 <b>Pending File</b>\n👤 User: <code>{info['user_id']}</code>\n📄 File: <code>{info['file_name']}</code>\n"
            f"🗂️ Type: <code>{info['file_type'].upper()}</code>\n🕐 Time: {info['timestamp']}",
            reply_markup=markup, parse_mode='HTML'
        )

def _logic_run_all_scripts(message_or_call):
    if isinstance(message_or_call, types.CallbackQuery):
        user_id = message_or_call.from_user.id
        chat_id = message_or_call.message.chat.id
        reply_func = lambda text, **kwargs: bot.send_message(chat_id, text, **kwargs)
        msg_obj = message_or_call.message
    else:
        user_id = message_or_call.from_user.id
        chat_id = message_or_call.chat.id
        reply_func = lambda text, **kwargs: bot.reply_to(message_or_call, text, **kwargs)
        msg_obj = message_or_call
    
    if user_id not in admin_ids:
        reply_func("⚠️ Admin only.")
        return
    
    reply_func("🔄 Starting all scripts...")
    started = 0
    
    for target_user_id, files in list(user_files.items()):
        user_folder = get_user_folder(target_user_id)
        for file_name, file_type in files:
            if not is_bot_running(target_user_id, file_name):
                file_path = os.path.join(user_folder, file_name)
                if os.path.exists(file_path):
                    try:
                        if file_type == 'py':
                            threading.Thread(target=run_script, args=(
                                file_path, target_user_id, user_folder, file_name, msg_obj
                            )).start()
                        else:
                            threading.Thread(target=run_js_script, args=(
                                file_path, target_user_id, user_folder, file_name, msg_obj
                            )).start()
                        started += 1
                        time.sleep(0.5)
                    except Exception as e:
                        logger.error(f"Error starting {file_name}: {e}")
    
    reply_func(f"✅ Started {started} scripts.")

def _logic_pending_payments_list(message):
    """Admin: Show all pending payment requests."""
    if message.from_user.id not in admin_ids:
        bot.reply_to(message, "⚠️ Admin only.")
        return
    
    if not pending_payments:
        bot.reply_to(message, "📋 No pending payments right now.")
        return
    
    response = "📋 <b>Pending Payment Requests:</b>\n\n"
    
    for uid, pay_info in list(pending_payments.items()):
        try:
            # Fetch user info
            chat = bot.get_chat(uid)
            first_name = chat.first_name or "Unknown"
            username = f"@{chat.username}" if chat.username else "N/A"
        except Exception:
            first_name = "Unknown"
            username = "N/A"
        
        plan_id = pay_info['plan_id']
        plan = PLANS.get(plan_id, {'name': 'Unknown Plan'})
        timestamp = pay_info.get('timestamp', datetime.now())
        time_str = timestamp.strftime('%Y-%m-%d %H:%M:%S')
        
        response += f"""
━━━━━━━━━━━━━━━━━━━
👤 User ID: <code>{uid}</code>
👤 Name: {first_name}
✳️ Username: {username}
📋 Plan: {plan['name']}
⏳ Since: {time_str}
━━━━━━━━━━━━━━━━━━━
"""
    
    bot.reply_to(message, response, parse_mode='HTML')

# --- Command Handlers ---
@bot.message_handler(commands=['start', 'help'])
def command_send_welcome(message):
    _logic_send_welcome(message)

@bot.message_handler(commands=['plans'])
def command_plans(message):
    _logic_show_plans(message)

@bot.message_handler(commands=['cancel_payment'])
def command_cancel_payment(message):
    user_id = message.from_user.id
    if user_id in pending_payments:
        del pending_payments[user_id]
        bot.reply_to(message, "❌ Payment cancelled.")
    else:
        bot.reply_to(message, "ℹ️ No pending payment found.")

# --- Text Handlers ---
BUTTON_TEXT_TO_LOGIC = {
    "📢 Updates Channel": _logic_updates_channel,
    "📤 Upload File": _logic_upload_file,
    "📂 My Files": _logic_check_files,
    "⚡ Bot Speed": _logic_bot_speed,
    "💎 Subscription Plans": _logic_show_plans,
    "📊 Statistics": _logic_statistics,
    "📞 Contact Owner": _logic_contact_owner,
    "💳 Manage Subscriptions": _logic_subscriptions_panel,
    "📢 Broadcast": _logic_broadcast_init,
    "🟢 Run All Scripts": _logic_run_all_scripts,
    "👑 Admin Panel": _logic_admin_panel,
    "⏳ Pending Files": _logic_pending_files,
    "📋 Pending Payments": _logic_pending_payments_list,      # Already existed but now accessible via text button
    "📋 Running Files": _logic_view_running_files,             # NEW
}

@bot.message_handler(func=lambda message: message.text in BUTTON_TEXT_TO_LOGIC)
def handle_button_text(message):
    logic_func = BUTTON_TEXT_TO_LOGIC.get(message.text)
    if logic_func:
        logic_func(message)

@bot.message_handler(content_types=['document', 'photo'])
def handle_file_upload(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Check if user has a pending payment
    if user_id in pending_payments:
        # This is a payment screenshot!
        plan_id = pending_payments[user_id]['plan_id']
        plan = PLANS.get(plan_id, {'name': 'Unknown Plan'})
        
        # Notify user that screenshot is received
        bot.reply_to(message, "✅ Screenshot received! Admin will review it shortly.")
        
        # Prepare Approve/Reject buttons for admins
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("✅ Approve Payment", callback_data=f"approve_payment_{user_id}"),
            types.InlineKeyboardButton("❌ Reject Payment", callback_data=f"reject_payment_{user_id}")
        )
        
        # Forward the screenshot to all admins with details
        for admin_id in admin_ids:
            try:
                # Forward the message (photo or document)
                bot.forward_message(admin_id, chat_id, message.message_id)
                
                admin_msg = f"""
╔══════════════════════╗
║   📸 <b>Payment Screenshot Received</b>   📸
╚══════════════════════╝

👤 User ID: <code>{user_id}</code>
👤 First Name: {message.from_user.first_name}
✳️ Username: @{message.from_user.username or 'N/A'}
📋 Plan Requested: {plan['name']}
💰 Amount: {plan['price_display']}

📌 <b>Actions:</b>
"""
                bot.send_message(admin_id, admin_msg, parse_mode='HTML', reply_markup=markup)
            except Exception:
                pass
        
        return
    
    # --- Regular File Upload Process (For Hosting Scripts) ---
    doc = message.document
    if not doc:
        bot.reply_to(message, "❌ Please send a valid file.")
        return

    # Check file limit
    file_limit = get_user_file_limit(user_id)
    current_files = get_user_file_count(user_id)
    
    if current_files >= file_limit:
        limit_str = "∞" if file_limit == float('inf') else str(file_limit)
        upgrade_msg = f"""
⚠️ <b>File Limit Reached!</b> ({current_files}/{limit_str})

💎 Upgrade to Premium:
• Unlimited files
• 24×7 uptime
• Priority support

Click 💎 Subscription Plans to upgrade.
"""
        bot.reply_to(message, upgrade_msg, parse_mode='HTML')
        return
    
    file_name = doc.file_name
    if not file_name:
        bot.reply_to(message, "❌ No file name!")
        return
    
    file_ext = os.path.splitext(file_name)[1].lower()
    if file_ext not in ['.py', '.js', '.zip']:
        bot.reply_to(message, "❌ Only <code>.py</code>, <code>.js</code>, <code>.zip</code> files allowed!", parse_mode='HTML')
        return
    
    max_size = 20 * 1024 * 1024
    if doc.file_size > max_size:
        bot.reply_to(message, "❌ File too large! Max 20 MB.")
        return
    
    try:
        wait_msg = bot.reply_to(message, f"⏳ Downloading <code>{file_name}</code>...", parse_mode='HTML')
        file_info = bot.get_file(doc.file_id)
        file_content = bot.download_file(file_info.file_path)
        bot.edit_message_text(f"✅ Downloaded <code>{file_name}</code>", chat_id, wait_msg.message_id, parse_mode='HTML')
        
        # Admin uploads go directly
        if user_id in admin_ids:
            user_folder = get_user_folder(user_id)
            if file_ext == '.zip':
                handle_zip_file(file_content, file_name, message)
            else:
                file_path = os.path.join(user_folder, file_name)
                with open(file_path, 'wb') as f:
                    f.write(file_content)
                if file_ext == '.py':
                    handle_py_file(file_path, user_id, user_folder, file_name, message)
                else:
                    handle_js_file(file_path, user_id, user_folder, file_name, message)
            return
        
        # Regular user - send for approval
        pending_id = _new_pending_id()
        file_type = file_ext.lstrip('.')
        pending_approvals[pending_id] = {
            'user_id': user_id,
            'file_name': file_name,
            'file_type': file_type,
            'file_data': file_content,
            'chat_id': chat_id,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        bot.reply_to(message, f"📨 File <code>{file_name}</code> sent for admin <b>approval</b>.\nYou'll be notified when approved.", 
                    parse_mode='HTML')
        
        # Notify admins
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("✅ Approve", callback_data=f"approve_{pending_id}"),
            types.InlineKeyboardButton("❌ Reject", callback_data=f"reject_{pending_id}")
        )
        
        for admin_id in admin_ids:
            try:
                bot.forward_message(admin_id, chat_id, message.message_id)
                bot.send_message(admin_id, 
                    f"📥 <b>New File - Approval Required</b>\n\n"
                    f"👤 User: <code>{user_id}</code>\n"
                    f"📄 File: <code>{file_name}</code>\n"
                    f"🗂️ Type: <code>{file_type.upper()}</code>\n"
                    f"🕐 Time: {pending_approvals[pending_id]['timestamp']}",
                    reply_markup=markup, parse_mode='HTML'
                )
            except Exception:
                pass
                
    except Exception as e:
        logger.error(f"File upload error: {e}")
        bot.reply_to(message, f"❌ Error: {str(e)}")

# --- Callback Handlers ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    data = call.data
    chat_id = call.message.chat.id
    
    try:
        # --- Payment Confirm/Reject ---
        if data == 'confirm_payment':
            _logic_confirm_payment(call)
            return
        elif data == 'cancel_payment':
            _logic_cancel_payment(call)
            return
        
        # --- Plan Purchase ---
        elif data.startswith('buy_plan_'):
            plan_id = data.replace('buy_plan_', '')
            _logic_buy_plan(call, plan_id)
            return
        
        # --- Payment Approval (Admin) ---
        elif data.startswith('approve_payment_'):
            if user_id not in admin_ids:
                bot.answer_callback_query(call.id, "⚠️ Admin only!", show_alert=True)
                return
            
            payer_id_str = data.replace('approve_payment_', '')
            try:
                payer_id = int(payer_id_str)
            except ValueError:
                bot.answer_callback_query(call.id, "❌ Invalid User ID.", show_alert=True)
                return

            if payer_id not in pending_payments:
                bot.answer_callback_query(call.id, "❌ Payment request not found or already processed!", show_alert=True)
                return
            
            plan_id = pending_payments[payer_id]['plan_id']
            plan = PLANS.get(plan_id)
            if plan:
                # Activate subscription
                expiry = datetime.now() + timedelta(days=plan['validity_days'])
                save_subscription(payer_id, expiry, plan_id, plan['file_limit'])
                update_payment_status(payer_id, 'approved')
                del pending_payments[payer_id]
                
                bot.send_message(payer_id, f"""
🎉 <b>Subscription Activated!</b>

{plan['name']} activated successfully!

📋 Details:
• Files: {plan['file_limit'] if plan['file_limit'] != float('inf') else '∞'} 
• Type: {', '.join(plan['file_types']).upper()}
• Valid till: {expiry.strftime('%Y-%m-%d')}

Thank you for choosing {BOT_NAME}! 🚀
""", parse_mode='HTML')
                
                bot.answer_callback_query(call.id, "✅ Payment approved! Subscription activated.")
                bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
                return
            
            bot.answer_callback_query(call.id, "❌ Plan not found!", show_alert=True)
            return
        
        elif data.startswith('reject_payment_'):
            if user_id not in admin_ids:
                bot.answer_callback_query(call.id, "⚠️ Admin only!", show_alert=True)
                return
            
            payer_id_str = data.replace('reject_payment_', '')
            try:
                payer_id = int(payer_id_str)
            except ValueError:
                bot.answer_callback_query(call.id, "❌ Invalid User ID.", show_alert=True)
                return
            
            if payer_id in pending_payments:
                update_payment_status(payer_id, 'rejected')
                del pending_payments[payer_id]
                bot.send_message(payer_id, "❌ Your payment was rejected. Please try again.")
            
            bot.answer_callback_query(call.id, "❌ Payment rejected.")
            bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
            return
        
        # --- File Approval (Admin) ---
        elif data.startswith('approve_'):
            if user_id not in admin_ids:
                bot.answer_callback_query(call.id, "⚠️ Admin only!", show_alert=True)
                return
            
            pending_id = data.replace('approve_', '')
            info = pending_approvals.get(pending_id)
            if not info:
                bot.answer_callback_query(call.id, "❌ Request not found!", show_alert=True)
                return
            
            bot.answer_callback_query(call.id, "✅ Approved!")
            bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
            
            target_uid = info['user_id']
            file_name = info['file_name']
            file_type = info['file_type']
            file_data = info['file_data']
            target_chat = info['chat_id']
            user_folder = get_user_folder(target_uid)
            
            # FIX: FakeMsg class with message_id to prevent 'obj' has no attribute 'message_id' error
            class FakeMsg:
                def __init__(self, cid, uid, fname):
                    self.chat = type('obj', (object,), {'id': cid})()
                    self.from_user = type('obj', (object,), {'id': uid})()
                    self.message_id = 0
                    self.text = fname
            
            try:
                if file_type == 'zip':
                    handle_zip_file(file_data, file_name, FakeMsg(target_chat, target_uid, file_name))
                else:
                    file_path = os.path.join(user_folder, file_name)
                    with open(file_path, 'wb') as f:
                        f.write(file_data)
                    fake_msg = FakeMsg(target_chat, target_uid, file_name)
                    if file_type == 'py':
                        handle_py_file(file_path, target_uid, user_folder, file_name, fake_msg)
                    else:
                        handle_js_file(file_path, target_uid, user_folder, file_name, fake_msg)
                
                bot.send_message(target_chat, f"✅ Your file <code>{file_name}</code> was <b>approved</b> and is running!", 
                               parse_mode='HTML')
                del pending_approvals[pending_id]
            except Exception as e:
                logger.error(f"Error approving file: {e}")
                bot.send_message(chat_id, f"❌ Error hosting: {str(e)}")
            
            return
        
        elif data.startswith('reject_'):
            if user_id not in admin_ids:
                bot.answer_callback_query(call.id, "⚠️ Admin only!", show_alert=True)
                return
            
            pending_id = data.replace('reject_', '')
            info = pending_approvals.get(pending_id)
            if not info:
                bot.answer_callback_query(call.id, "❌ Request not found!", show_alert=True)
                return
            
            bot.answer_callback_query(call.id, "❌ Rejected!")
            bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
            
            try:
                bot.send_message(info['chat_id'], f"❌ Your file <code>{info['file_name']}</code> was <b>rejected</b>.", 
                               parse_mode='HTML')
            except Exception:
                pass
            
            del pending_approvals[pending_id]
            return
        
        # --- Broadcast Confirm/Cancel ---
        elif data.startswith('confirm_broadcast_'):
            if user_id not in admin_ids:
                bot.answer_callback_query(call.id, "⚠️ Admin only!", show_alert=True)
                return
            
            bot.answer_callback_query(call.id, "📢 Broadcasting...")
            bot.edit_message_text("📢 Broadcasting...", chat_id, call.message.message_id, reply_markup=None)
            
            broadcast_text = call.message.reply_to_message.text if call.message.reply_to_message else ""
            if broadcast_text:
                threading.Thread(target=execute_broadcast, args=(broadcast_text, chat_id)).start()
            return
        
        elif data == 'cancel_broadcast':
            if user_id not in admin_ids:
                bot.answer_callback_query(call.id, "⚠️ Admin only!", show_alert=True)
                return
            
            bot.answer_callback_query(call.id, "❌ Cancelled.")
            bot.delete_message(chat_id, call.message.message_id)
            return
        
        # --- Show Plans ---
        elif data == 'show_plans':
            _logic_show_plans(call.message)
            bot.answer_callback_query(call.id)
            return
        
        # --- Upload ---
        elif data == 'upload':
            _logic_upload_file(call.message)
            bot.answer_callback_query(call.id)
            return
        
        # --- Check Files ---
        elif data == 'check_files':
            _logic_check_files(call.message)
            bot.answer_callback_query(call.id)
            return
        
        # --- File Control ---
        elif data.startswith('file_'):
            try:
                _, script_owner_id_str, file_name = data.split('_', 2)
                script_owner_id = int(script_owner_id_str)
                
                if user_id != script_owner_id and user_id not in admin_ids:
                    bot.answer_callback_query(call.id, "⚠️ Permission denied!", show_alert=True)
                    return
                
                is_running = is_bot_running(script_owner_id, file_name)
                status_text = '🟢 Running' if is_running else '🔴 Stopped'
                
                try:
                    bot.edit_message_text(
                        f"⚙️ <b>Control Panel</b>\n\n📄 File: <code>{file_name}</code>\nStatus: {status_text}\nUser: <code>{script_owner_id}</code>",
                        chat_id, call.message.message_id,
                        reply_markup=create_control_buttons(script_owner_id, file_name, is_running),
                        parse_mode='HTML'
                    )
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"File control error: {e}")
            
            bot.answer_callback_query(call.id)
            return
        
        # --- Start/Stop/Restart/Delete/Logs ---
        elif data.startswith('start_'):
            try:
                _, script_owner_id_str, file_name = data.split('_', 2)
                script_owner_id = int(script_owner_id_str)
                
                if user_id != script_owner_id and user_id not in admin_ids:
                    bot.answer_callback_query(call.id, "⚠️ Permission denied!", show_alert=True)
                    return
                
                user_folder = get_user_folder(script_owner_id)
                file_path = os.path.join(user_folder, file_name)
                file_type = None
                
                for fn, ft in user_files.get(script_owner_id, []):
                    if fn == file_name:
                        file_type = ft
                        break
                
                if not file_type or not os.path.exists(file_path):
                    bot.answer_callback_query(call.id, "❌ File not found!", show_alert=True)
                    return
                
                bot.answer_callback_query(call.id, f"🔄 Starting {file_name}...")
                
                if file_type == 'py':
                    threading.Thread(target=run_script, args=(file_path, script_owner_id, user_folder, file_name, call.message)).start()
                else:
                    threading.Thread(target=run_js_script, args=(file_path, script_owner_id, user_folder, file_name, call.message)).start()
                
                time.sleep(1)
                is_running = is_bot_running(script_owner_id, file_name)
                status_text = '🟢 Running' if is_running else '🟡 Starting...'
                
                try:
                    bot.edit_message_text(
                        f"⚙️ <b>Control Panel</b>\n\n📄 File: <code>{file_name}</code>\nStatus: {status_text}\nUser: <code>{script_owner_id}</code>",
                        chat_id, call.message.message_id,
                        reply_markup=create_control_buttons(script_owner_id, file_name, is_running),
                        parse_mode='HTML'
                    )
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"Start error: {e}")
            return
        
        elif data.startswith('stop_'):
            try:
                _, script_owner_id_str, file_name = data.split('_', 2)
                script_owner_id = int(script_owner_id_str)
                
                if user_id != script_owner_id and user_id not in admin_ids:
                    bot.answer_callback_query(call.id, "⚠️ Permission denied!", show_alert=True)
                    return
                
                script_key = f"{script_owner_id}_{file_name}"
                
                if script_key in bot_scripts:
                    kill_process_tree(bot_scripts[script_key])
                    del bot_scripts[script_key]
                    bot.answer_callback_query(call.id, "🛑 Stopped!")
                    
                    try:
                        bot.edit_message_text(
                            f"⚙️ <b>Control Panel</b>\n\n📄 File: <code>{file_name}</code>\nStatus: 🔴 Stopped\nUser: <code>{script_owner_id}</code>",
                            chat_id, call.message.message_id,
                            reply_markup=create_control_buttons(script_owner_id, file_name, False),
                            parse_mode='HTML'
                        )
                    except Exception:
                        pass
                else:
                    bot.answer_callback_query(call.id, "ℹ️ Already stopped.")
            except Exception as e:
                logger.error(f"Stop error: {e}")
            return
        
        elif data.startswith('restart_'):
            try:
                _, script_owner_id_str, file_name = data.split('_', 2)
                script_owner_id = int(script_owner_id_str)
                
                if user_id != script_owner_id and user_id not in admin_ids:
                    bot.answer_callback_query(call.id, "⚠️ Permission denied!", show_alert=True)
                    return
                
                script_key = f"{script_owner_id}_{file_name}"
                if script_key in bot_scripts:
                    kill_process_tree(bot_scripts[script_key])
                    del bot_scripts[script_key]
                
                bot.answer_callback_query(call.id, f"🔄 Restarting {file_name}...")
                
                user_folder = get_user_folder(script_owner_id)
                file_path = os.path.join(user_folder, file_name)
                file_type = None
                
                for fn, ft in user_files.get(script_owner_id, []):
                    if fn == file_name:
                        file_type = ft
                        break
                
                if file_type and os.path.exists(file_path):
                    if file_type == 'py':
                        threading.Thread(target=run_script, args=(file_path, script_owner_id, user_folder, file_name, call.message)).start()
                    else:
                        threading.Thread(target=run_js_script, args=(file_path, script_owner_id, user_folder, file_name, call.message)).start()
                    
                    time.sleep(1)
                    is_running = is_bot_running(script_owner_id, file_name)
                    status_text = '🟢 Running' if is_running else '🟡 Starting...'
                    
                    try:
                        bot.edit_message_text(
                            f"⚙️ <b>Control Panel</b>\n\n📄 File: <code>{file_name}</code>\nStatus: {status_text}\nUser: <code>{script_owner_id}</code>",
                            chat_id, call.message.message_id,
                            reply_markup=create_control_buttons(script_owner_id, file_name, is_running),
                            parse_mode='HTML'
                        )
                    except Exception:
                        pass
                else:
                    bot.answer_callback_query(call.id, "❌ File not found!", show_alert=True)
            except Exception as e:
                logger.error(f"Restart error: {e}")
            return
        
        elif data.startswith('delete_'):
            try:
                _, script_owner_id_str, file_name = data.split('_', 2)
                script_owner_id = int(script_owner_id_str)
                
                if user_id != script_owner_id and user_id not in admin_ids:
                    bot.answer_callback_query(call.id, "⚠️ Permission denied!", show_alert=True)
                    return
                
                script_key = f"{script_owner_id}_{file_name}"
                if script_key in bot_scripts:
                    kill_process_tree(bot_scripts[script_key])
                    del bot_scripts[script_key]
                
                user_folder = get_user_folder(script_owner_id)
                file_path = os.path.join(user_folder, file_name)
                log_path = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}.log")
                
                if os.path.exists(file_path):
                    os.remove(file_path)
                if os.path.exists(log_path):
                    os.remove(log_path)
                
                remove_user_file_db(script_owner_id, file_name)
                
                bot.answer_callback_query(call.id, "🗑️ Deleted!")
                bot.edit_message_text(
                    f"🗑️ Deleted: <code>{file_name}</code>",
                    chat_id, call.message.message_id,
                    reply_markup=None,
                    parse_mode='HTML'
                )
            except Exception as e:
                logger.error(f"Delete error: {e}")
            return
        
        elif data.startswith('logs_'):
            try:
                _, script_owner_id_str, file_name = data.split('_', 2)
                script_owner_id = int(script_owner_id_str)
                
                if user_id != script_owner_id and user_id not in admin_ids:
                    bot.answer_callback_query(call.id, "⚠️ Permission denied!", show_alert=True)
                    return
                
                user_folder = get_user_folder(script_owner_id)
                log_path = os.path.join(user_folder, f"{os.path.splitext(file_name)[0]}.log")
                
                if os.path.exists(log_path):
                    with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                        log_content = f.read()
                    
                    if len(log_content) > 4000:
                        log_content = log_content[-4000:]
                        log_content = "...\n" + log_content
                    
                    if not log_content.strip():
                        log_content = "(Empty log)"
                    
                    bot.send_message(chat_id, f"📜 <b>Logs for <code>{file_name}</code></b>\n\n<pre>{log_content}</pre>",
                                   parse_mode='HTML')
                    bot.answer_callback_query(call.id)
                else:
                    bot.answer_callback_query(call.id, "❌ No logs found!", show_alert=True)
            except Exception as e:
                logger.error(f"Logs error: {e}")
                bot.answer_callback_query(call.id, "❌ Error reading logs!", show_alert=True)
            return
        
        # --- Speed ---
        elif data == 'speed':
            _logic_bot_speed(call.message)
            bot.answer_callback_query(call.id)
            return
        
        # --- Stats ---
        elif data == 'stats':
            _logic_statistics(call.message)
            bot.answer_callback_query(call.id)
            return
        
        # --- Back to Main ---
        elif data == 'back_to_main':
            _logic_send_welcome(call.message)
            bot.answer_callback_query(call.id)
            return
        
        # --- Admin Subscriptions ---
        elif data == 'subscription':
            if user_id not in admin_ids:
                bot.answer_callback_query(call.id, "⚠️ Admin only!", show_alert=True)
                return
            _logic_subscriptions_panel(call.message)
            bot.answer_callback_query(call.id)
            return
        
        # --- Broadcast ---
        elif data == 'broadcast':
            if user_id not in admin_ids:
                bot.answer_callback_query(call.id, "⚠️ Admin only!", show_alert=True)
                return
            _logic_broadcast_init(call.message)
            bot.answer_callback_query(call.id)
            return
        
        # --- Admin Panel ---
        elif data == 'admin_panel':
            if user_id not in admin_ids:
                bot.answer_callback_query(call.id, "⚠️ Admin only!", show_alert=True)
                return
            _logic_admin_panel(call.message)
            bot.answer_callback_query(call.id)
            return
        
        # --- Run All Scripts ---
        elif data == 'run_all_scripts':
            if user_id not in admin_ids:
                bot.answer_callback_query(call.id, "⚠️ Admin only!", show_alert=True)
                return
            _logic_run_all_scripts(call)
            bot.answer_callback_query(call.id)
            return
        
        # --- Pending Files ---
        elif data == 'pending_files':
            if user_id not in admin_ids:
                bot.answer_callback_query(call.id, "⚠️ Admin only!", show_alert=True)
                return
            _logic_pending_files(call.message)
            bot.answer_callback_query(call.id)
            return

        # --- Pending Payments List (Admin) ---
        elif data == 'pending_payments_list':
            if user_id not in admin_ids:
                bot.answer_callback_query(call.id, "⚠️ Admin only!", show_alert=True)
                return
            _logic_pending_payments_list(call.message)
            bot.answer_callback_query(call.id)
            return
        
        # --- Admin Panel Actions ---
        elif data == 'add_admin':
            if user_id != OWNER_ID:
                bot.answer_callback_query(call.id, "⚠️ Owner only!", show_alert=True)
                return
            msg = bot.send_message(chat_id, "👑 Enter User ID to add as Admin:\nSend /cancel to cancel.")
            bot.register_next_step_handler(msg, process_add_admin)
            bot.answer_callback_query(call.id)
            return
        
        elif data == 'remove_admin':
            if user_id != OWNER_ID:
                bot.answer_callback_query(call.id, "⚠️ Owner only!", show_alert=True)
                return
            msg = bot.send_message(chat_id, "👑 Enter User ID to remove from Admin:\nSend /cancel to cancel.")
            bot.register_next_step_handler(msg, process_remove_admin)
            bot.answer_callback_query(call.id)
            return
        
        elif data == 'list_admins':
            if user_id not in admin_ids:
                bot.answer_callback_query(call.id, "⚠️ Admin only!", show_alert=True)
                return
            admin_list = "\n".join(f"- <code>{aid}</code> {'(Owner)' if aid == OWNER_ID else ''}" 
                                  for aid in sorted(list(admin_ids)))
            bot.send_message(chat_id, f"👑 <b>Admins</b>\n\n{admin_list}", parse_mode='HTML')
            bot.answer_callback_query(call.id)
            return
        
        elif data == 'payment_history':
            if user_id not in admin_ids:
                bot.answer_callback_query(call.id, "⚠️ Admin only!", show_alert=True)
                return
            
            conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
            c = conn.cursor()
            c.execute('''SELECT user_id, plan_id, amount, status, timestamp 
                         FROM payment_history ORDER BY id DESC LIMIT 20''')
            records = c.fetchall()
            conn.close()
            
            if not records:
                bot.send_message(chat_id, "📊 No payment records found.")
            else:
                msg = "📊 <b>Payment History</b> (Last 20)\n\n"
                for r in records:
                    status_icon = "✅" if r[3] == 'approved' else "⏳" if r[3] == 'pending' else "❌"
                    msg += f"{status_icon} User <code>{r[0]}</code> - {r[2]} - {r[3]}\n"
                    msg += f"   📅 {r[4][:16]}\n\n"
                bot.send_message(chat_id, msg, parse_mode='HTML')
            bot.answer_callback_query(call.id)
            return
        
        # --- Subscription Management ---
        elif data == 'add_subscription':
            if user_id not in admin_ids:
                bot.answer_callback_query(call.id, "⚠️ Admin only!", show_alert=True)
                return
            msg = bot.send_message(chat_id, """💳 <b>Add Subscription</b>

Format: <code>user_id plan_id</code>

Available plans:
• starter - ₹199 (10 files, 30 days)
• pro - ₹499 (100 files, 90 days)  
• ultimate - ₹999 (∞ files, 365 days)

Example: <code>123456789 ultimate</code>

Send /cancel to cancel.""", parse_mode='HTML')
            bot.register_next_step_handler(msg, process_add_subscription)
            bot.answer_callback_query(call.id)
            return
        
        elif data == 'remove_subscription':
            if user_id not in admin_ids:
                bot.answer_callback_query(call.id, "⚠️ Admin only!", show_alert=True)
                return
            msg = bot.send_message(chat_id, "💳 Enter User ID to remove subscription:\nSend /cancel to cancel.")
            bot.register_next_step_handler(msg, process_remove_subscription)
            bot.answer_callback_query(call.id)
            return
        
        elif data == 'check_subscription':
            if user_id not in admin_ids:
                bot.answer_callback_query(call.id, "⚠️ Admin only!", show_alert=True)
                return
            msg = bot.send_message(chat_id, "💳 Enter User ID to check subscription:\nSend /cancel to cancel.")
            bot.register_next_step_handler(msg, process_check_subscription)
            bot.answer_callback_query(call.id)
            return
        
        else:
            bot.answer_callback_query(call.id, "❌ Unknown action!")
            
    except Exception as e:
        logger.error(f"Callback error: {e}")
        try:
            bot.answer_callback_query(call.id, "❌ Error occurred!", show_alert=True)
        except Exception:
            pass

# --- Admin Step Handlers ---
def process_add_admin(message):
    if message.from_user.id != OWNER_ID:
        return
    if message.text and message.text.lower() == '/cancel':
        bot.reply_to(message, "❌ Cancelled.")
        return
    try:
        admin_id = int(message.text.strip())
        if admin_id <= 0:
            raise ValueError()
        if admin_id in admin_ids:
            bot.reply_to(message, f"⚠️ User <code>{admin_id}</code> is already admin.", parse_mode='HTML')
            return
        admin_ids.add(admin_id)
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (admin_id,))
        conn.commit()
        conn.close()
        bot.reply_to(message, f"✅ User <code>{admin_id}</code> added as admin!", parse_mode='HTML')
    except Exception:
        bot.reply_to(message, "❌ Invalid User ID! Please send a valid numeric ID.")

def process_remove_admin(message):
    if message.from_user.id != OWNER_ID:
        return
    if message.text and message.text.lower() == '/cancel':
        bot.reply_to(message, "❌ Cancelled.")
        return
    try:
        admin_id = int(message.text.strip())
        if admin_id == OWNER_ID:
            bot.reply_to(message, "⚠️ Cannot remove Owner!")
            return
        if admin_id not in admin_ids:
            bot.reply_to(message, f"⚠️ User <code>{admin_id}</code> is not admin.", parse_mode='HTML')
            return
        admin_ids.discard(admin_id)
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('DELETE FROM admins WHERE user_id = ?', (admin_id,))
        conn.commit()
        conn.close()
        bot.reply_to(message, f"✅ User <code>{admin_id}</code> removed from admin!", parse_mode='HTML')
    except Exception:
        bot.reply_to(message, "❌ Invalid User ID!")

def process_add_subscription(message):
    if message.from_user.id not in admin_ids:
        return
    if message.text and message.text.lower() == '/cancel':
        bot.reply_to(message, "❌ Cancelled.")
        return
    
    try:
        parts = message.text.strip().split()
        if len(parts) != 2:
            raise ValueError("Invalid format")
        
        user_id = int(parts[0])
        plan_id = parts[1].lower()
        
        if plan_id not in PLANS:
            raise ValueError(f"Unknown plan: {plan_id}")
        
        plan = PLANS[plan_id]
        expiry = datetime.now() + timedelta(days=plan['validity_days'])
        save_subscription(user_id, expiry, plan_id, plan['file_limit'])
        
        bot.reply_to(message, f"""
✅ <b>Subscription Added!</b>

👤 User: <code>{user_id}</code>
📋 Plan: {plan['name']}
📅 Valid till: {expiry.strftime('%Y-%m-%d')}
📁 File Limit: {plan['file_limit'] if plan['file_limit'] != float('inf') else '∞'}
📂 Types: {', '.join(plan['file_types']).upper()}
""", parse_mode='HTML')
        
        try:
            bot.send_message(user_id, f"""
🎉 <b>Subscription Activated!</b>

{plan['name']} added by admin!

📋 Details:
• Files: {plan['file_limit'] if plan['file_limit'] != float('inf') else '∞'}
• Valid till: {expiry.strftime('%Y-%m-%d')}

Enjoy hosting! 🚀
""", parse_mode='HTML')
        except Exception:
            pass
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}\n\nFormat: <code>user_id plan_id</code>\nPlans: starter, pro, ultimate", 
                    parse_mode='HTML')

def process_remove_subscription(message):
    if message.from_user.id not in admin_ids:
        return
    if message.text and message.text.lower() == '/cancel':
        bot.reply_to(message, "❌ Cancelled.")
        return
    try:
        user_id = int(message.text.strip())
        if user_id not in user_subscriptions:
            bot.reply_to(message, f"ℹ️ User <code>{user_id}</code> has no active subscription.", parse_mode='HTML')
            return
        remove_subscription_db(user_id)
        bot.reply_to(message, f"✅ Subscription removed for user <code>{user_id}</code>.", parse_mode='HTML')
        try:
            bot.send_message(user_id, "ℹ️ Your subscription has been removed by admin.")
        except Exception:
            pass
    except Exception:
        bot.reply_to(message, "❌ Invalid User ID!")

def process_check_subscription(message):
    if message.from_user.id not in admin_ids:
        return
    if message.text and message.text.lower() == '/cancel':
        bot.reply_to(message, "❌ Cancelled.")
        return
    try:
        user_id = int(message.text.strip())
        if user_id in user_subscriptions:
            sub = user_subscriptions[user_id]
            expiry = sub.get('expiry')
            if expiry and expiry > datetime.now():
                days_left = (expiry - datetime.now()).days
                plan_name = PLANS.get(sub.get('plan_id', ''), {}).get('name', 'Premium')
                bot.reply_to(message, f"""
✅ <b>Subscription Active</b>

👤 User: <code>{user_id}</code>
📋 Plan: {plan_name}
📅 Expires: {expiry.strftime('%Y-%m-%d')} ({days_left} days left)
📁 File Limit: {sub.get('file_limit', '∞')}
""", parse_mode='HTML')
            else:
                bot.reply_to(message, f"⚠️ Subscription for <code>{user_id}</code> has expired.", parse_mode='HTML')
                remove_subscription_db(user_id)
        else:
            bot.reply_to(message, f"ℹ️ User <code>{user_id}</code> has no active subscription.", parse_mode='HTML')
    except Exception:
        bot.reply_to(message, "❌ Invalid User ID!")

# --- Cleanup ---
def cleanup():
    logger.info("Cleaning up...")
    for key in list(bot_scripts.keys()):
        if key in bot_scripts:
            kill_process_tree(bot_scripts[key])
    logger.info("Cleanup complete.")

atexit.register(cleanup)

# --- Main ---
if __name__ == '__main__':
    logger.info("="*50)
    logger.info(f"🤖 {BOT_NAME} Starting...")
    logger.info(f"👑 Owner: {OWNER_ID}")
    logger.info(f"🔧 Admins: {admin_ids}")
    logger.info("="*50)
    
    keep_alive()
    
    while True:
        try:
            bot.infinity_polling(logger_level=logging.INFO, timeout=60, long_polling_timeout=30)
        except Exception as e:
            logger.error(f"Polling error: {e}")
            time.sleep(10)
