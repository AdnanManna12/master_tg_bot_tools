import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import os
import shutil
import json
import subprocess
import psutil
import time
import sys
import threading
import datetime


# ================= 1. AUTO INSTALLER =================
def install_requirements():
    packages = {'telebot': 'pyTelegramBotAPI', 'psutil': 'psutil', 'requests': 'requests'}
    for mod, pip_name in packages.items():
        try:
            __import__(mod)
        except ImportError:
            print(f"⚙️ Installing {pip_name}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name])


install_requirements()

# ================= 2. CONFIGURATION =================
MASTER_TOKEN = "8609413787:AAGURTJEqa8I102_56-DH_Ha1QBC6WV8Na4"
SUPER_ADMIN_ID = 8287522557
SUPPORT_USER = "@YourTelegramUsername"
CHANNEL_URL = "https://t.me/YourChannel"

bot = telebot.TeleBot(MASTER_TOKEN, num_threads=64)

DB_USERS = "db_users.json"
DB_PANELS = "db_panels.json"
DB_INSTANCES = "db_instances.json"
DB_ADMINS = "db_admins.json"

for folder in ["templates", "active_users"]: os.makedirs(folder, exist_ok=True)

# ================= 3. DATABASE ENGINE =================
db_lock = threading.Lock()


def load_db(file, default):
    if os.path.exists(file):
        try:
            with open(file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return default
    return default


def save_db(file, data):
    with db_lock:
        with open(file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)


users_db = load_db(DB_USERS, {})
panels = load_db(DB_PANELS, {})
running_instances = load_db(DB_INSTANCES, {})
admins_db = load_db(DB_ADMINS, [SUPER_ADMIN_ID])

if SUPER_ADMIN_ID not in admins_db:
    admins_db.append(SUPER_ADMIN_ID)
    save_db(DB_ADMINS, admins_db)

user_states = {}
active_processes = {}


def is_admin(uid):
    return int(uid) in admins_db


def has_access(uid):
    if is_admin(uid): return True
    uid = str(uid)
    user = users_db.get(uid, {})
    if user.get("status") == "approved":
        expire_time = user.get("expire", 0)
        if expire_time != -1 and time.time() > expire_time:
            users_db[uid]["status"] = "expired"
            save_db(DB_USERS, users_db)
            return False
        return True
    return False


# ================= 4. 👑 ADMIN CPANEL =================
def admin_main_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📁 File Manager", callback_data="adm_file_mgr"),
        InlineKeyboardButton("🛍️ Service Manager", callback_data="adm_svc_mgr"),
        InlineKeyboardButton("👥 User Manager", callback_data="adm_usr_mgr"),
        InlineKeyboardButton("📊 System Stats", callback_data="adm_stats")
    )
    return markup


@bot.message_handler(commands=['admin'])
def admin_command(message):
    bot.clear_step_handler_by_chat_id(message.chat.id)
    if not is_admin(message.from_user.id): return
    bot.reply_to(message, "👑 <b>Premium Master CPanel</b>", reply_markup=admin_main_menu(), parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data.startswith('adm_'))
def admin_callbacks(call):
    bot.answer_callback_query(call.id)
    bot.clear_step_handler_by_chat_id(call.message.chat.id)
    if not is_admin(call.from_user.id): return
    action = call.data

    if action == "adm_main":
        bot.edit_message_text("👑 <b>Premium Master CPanel</b>", call.message.chat.id, call.message.message_id,
                              reply_markup=admin_main_menu(), parse_mode="HTML")

    # --- Service Manager ---
    elif action == "adm_svc_mgr":
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("➕ Add Service", callback_data="adm_svc_add"),
            InlineKeyboardButton("📋 View Services", callback_data="adm_svc_list"),
            InlineKeyboardButton("🗑️ Remove Service", callback_data="adm_svc_del"),
            InlineKeyboardButton("🔙 Back", callback_data="adm_main")
        )
        bot.edit_message_text("🛍️ <b>Service Manager</b>", call.message.chat.id, call.message.message_id,
                              reply_markup=markup, parse_mode="HTML")

    elif action == "adm_svc_list":
        if not panels:
            bot.send_message(call.message.chat.id, "❌ No services added yet.")
            return
        text = "📋 <b>Active Services List:</b>\n━━━━━━━━━━━━━━━━━\n"
        for p_name, p_data in panels.items():
            text += f"🔴 <b>{p_name}</b> | 🏷️ {p_data.get('category', 'Client Panels')}\n"
            text += f"   ┣ 📁 Folder: <code>{p_data['folder']}</code>\n"
            text += f"   ┗ ⚙️ Limit: {p_data.get('limit', 1)} Bots\n\n"
        bot.send_message(call.message.chat.id, text, parse_mode="HTML")

    elif action == "adm_svc_add":
        msg = bot.send_message(call.message.chat.id, "📦 Enter <b>Service Name</b> (e.g. IMS, NUMBER):",
                               parse_mode="HTML")
        bot.register_next_step_handler(msg, process_add_svc_name)

    elif action == "adm_svc_del":
        msg = bot.send_message(call.message.chat.id, "🗑️ Type exactly the <b>Service Name</b> to remove:",
                               parse_mode="HTML")
        bot.register_next_step_handler(msg, lambda m: [panels.pop(m.text, None), save_db(DB_PANELS, panels),
                                                       bot.reply_to(m, "✅ Removed!")])

    # --- User Manager ---
    elif action == "adm_usr_mgr":
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("⏳ Pending", callback_data="adm_usr_pending"),
            InlineKeyboardButton("🔍 Inspect User", callback_data="adm_usr_inspect"),
            InlineKeyboardButton("⚙️ Change Limit", callback_data="adm_usr_limit"),
            InlineKeyboardButton("🚫 Ban", callback_data="adm_usr_ban"),
            InlineKeyboardButton("✅ Unban", callback_data="adm_usr_unban"),
            InlineKeyboardButton("🔙 Back", callback_data="adm_main")
        )
        bot.edit_message_text(f"👥 <b>User Manager</b>\nTotal Users: {len(users_db)}", call.message.chat.id,
                              call.message.message_id, reply_markup=markup, parse_mode="HTML")

    elif action == "adm_usr_pending":
        pending = [uid for uid, data in users_db.items() if data['status'] == 'pending']
        if not pending:
            bot.send_message(call.message.chat.id, "✅ No pending requests.")
            return
        for p_uid in pending:
            markup = InlineKeyboardMarkup(row_width=2)
            markup.add(
                InlineKeyboardButton("🎁 3 Days Trial", callback_data=f"sub_trial_{p_uid}"),
                InlineKeyboardButton("💎 30 Days Premium", callback_data=f"sub_premium_{p_uid}"),
                InlineKeyboardButton("🚫 Reject", callback_data=f"reject_{p_uid}")
            )
            bot.send_message(call.message.chat.id, f"📩 <b>Request from ID:</b> <code>{p_uid}</code>\nSelect Plan:",
                             reply_markup=markup, parse_mode="HTML")

    elif action == "adm_usr_limit":
        msg = bot.send_message(call.message.chat.id, "⚙️ Enter the <b>User ID</b> to change limit:", parse_mode="HTML")
        bot.register_next_step_handler(msg, process_change_user_limit)

    elif action == "adm_usr_inspect":
        msg = bot.send_message(call.message.chat.id, "🔍 Enter <b>User ID</b>:", parse_mode="HTML")
        bot.register_next_step_handler(msg, process_inspect_user)

    elif action == "adm_usr_ban":
        msg = bot.send_message(call.message.chat.id, "🚫 Enter ID to Ban:", parse_mode="HTML")
        bot.register_next_step_handler(msg, lambda m: [users_db.update({m.text.strip(): {"status": "banned"}}),
                                                       save_db(DB_USERS, users_db), bot.reply_to(m, "✅ Banned!")])

    elif action == "adm_usr_unban":
        msg = bot.send_message(call.message.chat.id, "✅ Enter ID to Unban:", parse_mode="HTML")
        bot.register_next_step_handler(msg,
                                       lambda m: [users_db.update({m.text.strip(): {"status": "approved", "limit": 3}}),
                                                  save_db(DB_USERS, users_db), bot.reply_to(m, "✅ Unbanned!")])

    # --- File Manager ---
    elif action == "adm_file_mgr":
        markup = InlineKeyboardMarkup(row_width=2).add(
            InlineKeyboardButton("➕ Create Folder", callback_data="adm_fm_create"),
            InlineKeyboardButton("📤 Upload Script", callback_data="adm_fm_upload"),
            InlineKeyboardButton("📂 View Files", callback_data="adm_fm_view"),
            InlineKeyboardButton("🔙 Back", callback_data="adm_main"))
        bot.edit_message_text("📁 <b>File Manager</b>", call.message.chat.id, call.message.message_id,
                              reply_markup=markup, parse_mode="HTML")
    elif action == "adm_fm_create":
        msg = bot.send_message(call.message.chat.id, "📝 Enter folder name:", parse_mode="HTML")
        bot.register_next_step_handler(msg,
                                       lambda m: [os.makedirs(os.path.join("templates", m.text.strip()), exist_ok=True),
                                                  bot.reply_to(m, "✅ Created!")])
    elif action == "adm_fm_upload":
        folders = [f for f in os.listdir("templates") if os.path.isdir(os.path.join("templates", f))]
        markup = InlineKeyboardMarkup()
        for f in folders: markup.add(InlineKeyboardButton(f"📂 {f}", callback_data=f"updir_{f}"))
        bot.edit_message_text("📤 Select folder to upload:", call.message.chat.id, call.message.message_id,
                              reply_markup=markup, parse_mode="HTML")
    elif action == "adm_fm_view":
        text = "📁 <b>Server Templates:</b>\n"
        for f in os.listdir("templates"): text += f"\n📂 <code>{f}</code>"
        bot.send_message(call.message.chat.id, text, parse_mode="HTML")

    elif action == "adm_stats":
        app_users = len([u for u, d in users_db.items() if d.get('status') == 'approved'])
        bot.send_message(call.message.chat.id,
                         f"📊 <b>Stats</b>\nCPU: {psutil.cpu_percent()}%\nRAM: {psutil.virtual_memory().percent}%\nActive Users: {app_users}\nBots Running: {len(running_instances)}",
                         parse_mode="HTML")


# --- Admin Process Handlers ---
def process_change_user_limit(message):
    uid = message.text.strip()
    if uid not in users_db:
        bot.reply_to(message, "❌ User not found.")
        return
    user_states[message.from_user.id] = {'target_uid': uid}
    msg = bot.reply_to(message, f"⚙️ Enter new Global Bot Limit for {uid}:")
    bot.register_next_step_handler(msg, finalize_user_limit)


def finalize_user_limit(message):
    try:
        limit = int(message.text)
        uid = user_states[message.from_user.id]['target_uid']
        users_db[uid]['limit'] = limit
        save_db(DB_USERS, users_db)
        bot.reply_to(message, f"✅ Limit for {uid} updated to {limit} bots.")
    except:
        bot.reply_to(message, "❌ Invalid number.")


def process_inspect_user(message):
    uid = message.text.strip()
    user_bots = {k: v for k, v in running_instances.items() if str(v["user"]) == uid}
    if not user_bots:
        bot.reply_to(message, f"❌ No bots running for {uid}")
        return
    text = f"🕵️‍♂️ <b>Details for {uid}:</b>\n━━━━━━━━━━━━━\n"
    for i_id, data in user_bots.items():
        text += f"🔹 <b>{data['type']}</b> | 🆔 <code>{i_id}</code>\n"
    bot.reply_to(message, text, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data.startswith('updir_'))
def handle_upload_dir(call):
    bot.answer_callback_query(call.id)
    user_states[call.from_user.id] = {'upload_dir': call.data.replace('updir_', '')}
    msg = bot.send_message(call.from_user.id, "📎 Upload `.py` file:", parse_mode="HTML")
    bot.register_next_step_handler(msg, process_file_upload)


def process_file_upload(message):
    if message.document:
        folder = user_states[message.from_user.id].get('upload_dir')
        file_info = bot.get_file(message.document.file_id)
        with open(os.path.join("templates", folder, message.document.file_name), 'wb') as f:
            f.write(bot.download_file(file_info.file_path))
        bot.reply_to(message, "✅ <b>Uploaded Successfully!</b>", parse_mode="HTML")


def process_add_svc_name(message):
    user_states[message.from_user.id] = {'temp_name': message.text.upper()}
    msg = bot.reply_to(message, "📁 Enter <b>Folder Name</b> from templates:")
    bot.register_next_step_handler(msg, process_add_svc_folder)


def process_add_svc_folder(message):
    user_states[message.from_user.id]['temp_folder'] = message.text
    msg = bot.reply_to(message, "💰 Enter <b>Price</b> (e.g., $10):")
    bot.register_next_step_handler(msg, process_add_svc_price)


def process_add_svc_price(message):
    user_states[message.from_user.id]['temp_price'] = message.text
    msg = bot.reply_to(message, "⚙️ Enter <b>Bot Limit</b> for this panel (e.g., 2):")
    bot.register_next_step_handler(msg, process_add_svc_limit)


def process_add_svc_limit(message):
    try:
        user_states[message.from_user.id]['temp_limit'] = int(message.text)
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(InlineKeyboardButton("🏆 AGENT PANELS", callback_data="setcat_Agent Panels"),
                   InlineKeyboardButton("👤 CLIENT PANELS", callback_data="setcat_Client Panels"))
        bot.reply_to(message, "📁 <b>Select Category:</b>", reply_markup=markup, parse_mode="HTML")
    except:
        bot.reply_to(message, "❌ Invalid limit.")


@bot.callback_query_handler(func=lambda call: call.data.startswith('setcat_'))
def finalize_service_add(call):
    bot.answer_callback_query(call.id)
    category = call.data.split('_')[1]
    uid = call.from_user.id
    name = user_states[uid]['temp_name']

    panels[name] = {"folder": user_states[uid]['temp_folder'], "price": user_states[uid]['temp_price'],
                    "limit": user_states[uid]['temp_limit'], "category": category}
    save_db(DB_PANELS, panels)
    bot.edit_message_text(
        f"✅ <b>Service Added!</b>\nName: {name}\nLimit: {user_states[uid]['temp_limit']}\nCategory: {category}",
        call.message.chat.id, call.message.message_id, parse_mode="HTML")


# ================= 5. 💎 EXACT SCREENSHOT UI (USER DASHBOARD) =================

def user_bottom_menu():
    # 💡 Bottom keyboard menu
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(KeyboardButton("🏠 Dashboard"), KeyboardButton("🚀 Active Bots"))
    markup.add(KeyboardButton("📊 Profile & Plan"), KeyboardButton("📞 Support"))
    return markup


def get_user_dashboard_markup(uid):
    # 💡 EXACT UI Match: Vertical Stack (row_width=1)
    markup = InlineKeyboardMarkup(row_width=1)
    if has_access(uid):
        markup.add(
            InlineKeyboardButton("📁 PANEL LIST", callback_data="usr_panel_list"),
            InlineKeyboardButton("💻 YOUR PANELS", callback_data="usr_my_panels"),
            InlineKeyboardButton("🎥 HOW TO USE", url=CHANNEL_URL),
            InlineKeyboardButton("👤 YOUR SUBSCRIPTION", callback_data="usr_subscription"),
            InlineKeyboardButton("💎 BUY SUBSCRIPTION", callback_data="req_subscription")
        )
    else:
        markup.add(
            InlineKeyboardButton("💎 BUY SUBSCRIPTION / REQUEST ACCESS", callback_data="req_subscription"),
            InlineKeyboardButton("📞 Support", url=f"https://t.me/{SUPPORT_USER.replace('@', '')}")
        )
    return markup


def generate_user_dashboard_text(user):
    # 💡 EXACT UI Match: Text Format
    uid = str(user.id)
    uname = f"@{user.username}" if user.username else user.first_name

    u_data = users_db.get(uid, {})
    if is_admin(uid):
        status_icon = "👑 Admin"
    elif has_access(uid):
        status_icon = f"💎 Premium"
    else:
        status_icon = "🆓 Pending/Expired"

    active_count = len([k for k, v in running_instances.items() if str(v["user"]) == uid])

    text = "📝 <b>USER DASHBOARD</b>\n\n"
    text += f"🆔 <b>ID:</b> <code>{uid}</code>\n"
    text += f"👤 <b>User:</b> {uname}\n"
    text += f"📊 <b>Status:</b> {status_icon}\n"
    text += f"🚀 <b>Running Panels:</b> {active_count}"
    return text


@bot.message_handler(commands=['start', 'dashboard'])
@bot.message_handler(func=lambda message: message.text == "🏠 Dashboard")
def start_user_dashboard(message):
    bot.clear_step_handler_by_chat_id(message.chat.id)
    # 💡 1. Send Bottom Menu silently
    bot.send_message(message.chat.id, "🔄 <i>Loading your dashboard...</i>", reply_markup=user_bottom_menu(),
                     parse_mode="HTML")
    # 💡 2. Send Inline Dashboard exactly like screenshot
    text = generate_user_dashboard_text(message.from_user)
    markup = get_user_dashboard_markup(str(message.from_user.id))
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data == "usr_back_dash")
def back_to_dashboard(call):
    bot.answer_callback_query(call.id)
    bot.clear_step_handler_by_chat_id(call.message.chat.id)
    text = generate_user_dashboard_text(call.from_user)
    markup = get_user_dashboard_markup(str(call.from_user.id))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")


# --- 📁 PANEL CATEGORIES & GRID MATCHING SCREENSHOT ---
@bot.callback_query_handler(func=lambda call: call.data == "usr_panel_list")
def show_categories(call):
    bot.answer_callback_query(call.id)
    text = "📁 <b>PANEL CATEGORIES</b>\nSelect a category to view available panels:"
    markup = InlineKeyboardMarkup(row_width=1)  # Vertical Stack
    markup.add(
        InlineKeyboardButton("🏆 AGENT PANELS", callback_data="cat_Agent Panels"),
        InlineKeyboardButton("👤 CLIENT PANELS", callback_data="cat_Client Panels"),
        InlineKeyboardButton("🔙 Back to Dashboard", callback_data="usr_back_dash")
    )
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data.startswith('cat_'))
def show_panels_grid(call):
    bot.answer_callback_query(call.id)
    category = call.data.replace('cat_', '')

    markup = InlineKeyboardMarkup(row_width=2)  # 💡 EXACT UI: 2 Columns Grid!
    buttons = []
    for p_name, p_data in panels.items():
        if p_data.get('category', 'Client Panels') == category:
            buttons.append(InlineKeyboardButton(f"🔴 {p_name}", callback_data=f"deploy_{p_name}"))

    if not buttons:
        bot.answer_callback_query(call.id, "❌ No panels in this category yet.", show_alert=True)
        return

    markup.add(*buttons)  # Adds buttons in pairs
    markup.row(InlineKeyboardButton("🔙 Back to Categories", callback_data="usr_panel_list"))  # Full width back button

    text = f"📁 <b>{category.upper()}</b>\nSelect a panel to configure:"
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")


# ================= 6. 💳 SUBSCRIPTION SYSTEM =================
@bot.callback_query_handler(func=lambda call: call.data == "req_subscription")
def select_plan_to_buy(call):
    bot.answer_callback_query(call.id)
    bot.clear_step_handler_by_chat_id(call.message.chat.id)

    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("🎁 3 Days Trial", callback_data="buyplan_Trial"),
        InlineKeyboardButton("💎 30 Days Premium", callback_data="buyplan_Premium"),
        InlineKeyboardButton("🔙 Back to Dashboard", callback_data="usr_back_dash")
    )
    bot.edit_message_text("💎 <b>SELECT A PLAN</b>\nChoose the subscription plan:", call.message.chat.id,
                          call.message.message_id, reply_markup=markup, parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data.startswith('buyplan_'))
def ask_for_screenshot(call):
    bot.answer_callback_query(call.id)
    plan = call.data.split('_')[1]
    user_states[call.from_user.id] = {'req_plan': plan}

    msg = bot.send_message(call.message.chat.id,
                           f"📝 You selected: <b>{plan.upper()}</b>\n\n📎 Please send your <b>Payment Screenshot</b> or <b>Transaction ID</b> below:",
                           parse_mode="HTML")
    bot.register_next_step_handler(msg, process_subscription_payment)


def process_subscription_payment(message):
    uid = str(message.from_user.id)
    uname = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name
    plan = user_states.get(message.from_user.id, {}).get('req_plan', 'Premium')

    bot.forward_message(SUPER_ADMIN_ID, message.chat.id, message.message_id)
    markup = InlineKeyboardMarkup(row_width=2).add(
        InlineKeyboardButton("✅ Approve", callback_data=f"subapprove_{uid}_{plan}"),
        InlineKeyboardButton("🚫 Reject", callback_data=f"subreject_{uid}"))
    bot.send_message(SUPER_ADMIN_ID, f"🔔 <b>New Payment!</b>\nUser: {uname} (<code>{uid}</code>)\nPlan: <b>{plan}</b>",
                     reply_markup=markup, parse_mode="HTML")
    bot.reply_to(message, f"✅ <b>Request for {plan} Submitted!</b>\nAdmin is reviewing your payment.",
                 parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data.startswith('subapprove_'))
def admin_approve_plan(call):
    bot.answer_callback_query(call.id)
    if not is_admin(call.from_user.id): return
    uid, plan = call.data.split('_')[1], call.data.split('_')[2]

    expire = time.time() + ((3 if plan == "Trial" else 30) * 86400)
    limit = 1 if plan == "Trial" else 3
    users_db[uid] = {"status": "approved", "limit": limit, "plan": plan, "expire": expire}
    save_db(DB_USERS, users_db)

    bot.edit_message_text(f"✅ {uid} approved for {plan}.", call.message.chat.id, call.message.message_id)
    try:
        bot.send_message(uid, f"🎉 <b>Approved!</b> Your <b>{plan}</b> plan is active.\nSend /start", parse_mode="HTML")
    except:
        pass


@bot.callback_query_handler(func=lambda call: call.data.startswith('subreject_'))
def admin_reject_plan(call):
    bot.answer_callback_query(call.id)
    uid = call.data.split('_')[1]
    bot.edit_message_text(f"❌ Rejected {uid}.", call.message.chat.id, call.message.message_id)
    try:
        bot.send_message(uid, "❌ <b>Subscription Rejected.</b> Contact support.", parse_mode="HTML")
    except:
        pass


@bot.callback_query_handler(func=lambda call: call.data == "usr_subscription")
@bot.message_handler(func=lambda message: message.text == "📊 Profile & Plan")
def show_profile(call_or_msg):
    is_call = hasattr(call_or_msg, 'message')
    uid = str(call_or_msg.from_user.id)
    user = users_db.get(uid, {})

    plan, expire = user.get('plan', 'N/A'), user.get('expire', 0)
    exp_date = "Lifetime" if is_admin(uid) or expire == -1 else (
        datetime.datetime.fromtimestamp(expire).strftime('%d %b %Y') if expire > 0 else "Expired")

    active_count = len([k for k, v in running_instances.items() if str(v["user"]) == uid])

    text = f"👤 <b>PROFILE DETAILS</b>\n━━━━━━━━━━━━━━━━━\n🆔 <b>ID:</b> <code>{uid}</code>\n💎 <b>Plan:</b> {plan}\n⏳ <b>Expires:</b> {exp_date}\n\n🔋 <b>LIMIT:</b> {active_count} / {user.get('limit', 0)} Bots Used"

    if is_call:
        bot.answer_callback_query(call_or_msg.id)
        bot.edit_message_text(text, call_or_msg.message.chat.id, call_or_msg.message.message_id,
                              reply_markup=InlineKeyboardMarkup().add(
                                  InlineKeyboardButton("🔙 Back", callback_data="usr_back_dash")), parse_mode="HTML")
    else:
        bot.reply_to(call_or_msg, text, parse_mode="HTML")


# ================= 7. 🚀 DEPLOY WIZARD =================
@bot.callback_query_handler(func=lambda call: call.data.startswith('deploy_'))
def deploy_wizard(call):
    bot.answer_callback_query(call.id)
    bot.clear_step_handler_by_chat_id(call.message.chat.id)
    uid = str(call.from_user.id)

    if not has_access(uid):
        bot.answer_callback_query(call.id, "❌ Access Denied! Please subscribe.", show_alert=True)
        return

    p_name = call.data.replace('deploy_', '')
    total_active = len([k for k, v in running_instances.items() if str(v["user"]) == uid])
    if total_active >= users_db.get(uid, {}).get("limit", 1) and not is_admin(uid):
        bot.send_message(uid, "❌ <b>Global Limit Reached!</b>", parse_mode="HTML")
        return

    user_states[uid] = {'selected_panel': p_name}
    msg = bot.send_message(uid, f"✅ Selected: <b>{p_name}</b>\n\n🌐 Enter <b>Panel URL</b>:", parse_mode="HTML")
    bot.register_next_step_handler(msg, ask_for_username)


def ask_for_username(message):
    uid = str(message.from_user.id)
    user_states[uid]['panel_url'] = message.text
    msg = bot.reply_to(message, "👤 Enter <b>Panel Username</b>:", parse_mode="HTML")
    bot.register_next_step_handler(msg, ask_for_password)


def ask_for_password(message):
    uid = str(message.from_user.id)
    user_states[uid]['username'] = message.text
    msg = bot.reply_to(message, "🔑 Enter <b>Panel Password</b>:", parse_mode="HTML")
    bot.register_next_step_handler(msg, ask_for_bot_token)


def ask_for_bot_token(message):
    uid = str(message.from_user.id)
    user_states[uid]['password'] = message.text
    msg = bot.reply_to(message, "🤖 Enter <b>Telegram Bot Token</b>:", parse_mode="HTML")
    bot.register_next_step_handler(msg, ask_for_chatid)


def ask_for_chatid(message):
    uid = str(message.from_user.id)
    user_states[uid]['bot_token'] = message.text
    msg = bot.reply_to(message, "💬 Enter <b>Target Chat ID</b>:", parse_mode="HTML")
    bot.register_next_step_handler(msg, finalize_deployment)


def finalize_deployment(message):
    uid = str(message.from_user.id)
    p_name = user_states.get(uid, {}).get('selected_panel')
    if not p_name: return

    target_dir = f"active_users/bot_{uid}_{int(time.time())}"
    bot.reply_to(message, "⏳ <b>Deploying Server...</b>", parse_mode="HTML")

    try:
        shutil.copytree(f"templates/{panels[p_name]['folder']}", target_dir)
        config_data = {"panel_url": user_states[uid]['panel_url'], "username": user_states[uid]['username'],
                       "password": user_states[uid]['password'], "bot_token": user_states[uid]['bot_token'],
                       "chat_id": message.text}
        with open(f"{target_dir}/config.json", "w") as f:
            json.dump(config_data, f)

        py_files = [f for f in os.listdir(target_dir) if f.endswith('.py')]
        new_script = f"user_{uid}.py"
        os.rename(os.path.join(target_dir, py_files[0]), os.path.join(target_dir, new_script))

        running_instances[target_dir.split('/')[-1]] = {"user": uid, "type": p_name, "folder": target_dir,
                                                        "status": "stopped", "script": new_script}
        save_db(DB_INSTANCES, running_instances)

        start_instance_bg(target_dir.split('/')[-1])
        bot.reply_to(message, f"🚀 <b>DEPLOYMENT SUCCESSFUL!</b>\n✅ Engine Started! Click '🚀 Active Bots' to manage.",
                     parse_mode="HTML")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")


# ================= 8. ⚙️ MANAGE BOTS & TERMINAL =================
@bot.callback_query_handler(func=lambda call: call.data == "usr_my_panels")
@bot.message_handler(func=lambda message: message.text == "🚀 Active Bots")
def menu_my_bots(call_or_msg):
    is_call = hasattr(call_or_msg, 'message')
    uid = str(call_or_msg.from_user.id)
    chat_id = call_or_msg.message.chat.id if is_call else call_or_msg.chat.id
    if is_call: bot.answer_callback_query(call_or_msg.id)

    bot.clear_step_handler_by_chat_id(chat_id)
    user_bots = {k: v for k, v in running_instances.items() if str(v["user"]) == uid}

    if not user_bots:
        bot.send_message(chat_id, "❌ You have no active servers.")
        return

    for i_id, data in user_bots.items():
        markup = InlineKeyboardMarkup(row_width=2)
        if data.get('status') == 'running':
            markup.add(InlineKeyboardButton("⏸️ Stop", callback_data=f"bot_stop_{i_id}"),
                       InlineKeyboardButton("🖥️ View Log", callback_data=f"bot_log_{i_id}"))
            markup.add(InlineKeyboardButton("⌨️ Send Terminal Input", callback_data=f"bot_input_{i_id}"))
        else:
            markup.add(InlineKeyboardButton("▶️ Start", callback_data=f"bot_start_{i_id}"))
        markup.add(InlineKeyboardButton("🗑️ Delete Server", callback_data=f"bot_delete_{i_id}"))

        bot.send_message(chat_id, f"💻 <b>{data['type']}</b>\n🆔 <code>{i_id}</code>", reply_markup=markup,
                         parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data.startswith('bot_'))
def bot_controls(call):
    bot.answer_callback_query(call.id)
    bot.clear_step_handler_by_chat_id(call.message.chat.id)
    action, i_id = call.data.split('_')[1], call.data.replace(f"bot_{call.data.split('_')[1]}_", "")

    if i_id not in running_instances: return

    if action == "start":
        start_instance_bg(i_id)
        bot.edit_message_text("✅ Server Started!", call.message.chat.id, call.message.message_id)
    elif action == "stop":
        stop_instance_bg(i_id)
        bot.edit_message_text("🛑 Server Stopped!", call.message.chat.id, call.message.message_id)
    elif action == "delete":
        stop_instance_bg(i_id)
        shutil.rmtree(running_instances[i_id]['folder'], ignore_errors=True)
        del running_instances[i_id]
        save_db(DB_INSTANCES, running_instances)
        bot.edit_message_text("🗑️ Server Deleted!", call.message.chat.id, call.message.message_id)
    elif action == "log":
        try:
            bot.send_message(call.message.chat.id,
                             f"🖥️ <b>Terminal Log:</b>\n<pre>{''.join(open(os.path.join(running_instances[i_id]['folder'], 'terminal.log')).readlines()[-15:])}</pre>",
                             parse_mode="HTML")
        except:
            bot.send_message(call.message.chat.id, "❌ No log generated yet.")
    elif action == "input":
        msg = bot.send_message(call.message.chat.id,
                               "⌨️ <b>Send Input:</b>\nType the value (e.g. 1/2/3) to send to terminal:",
                               parse_mode="HTML")
        bot.register_next_step_handler(msg, lambda m: [active_processes[i_id].stdin.write(m.text + "\n"),
                                                       active_processes[i_id].stdin.flush(), bot.reply_to(m,
                                                                                                          "✅ Input Sent Successfully!")] if i_id in active_processes else bot.reply_to(
            m, "❌ Bot is not running."))


def start_instance_bg(i_id):
    data = running_instances[i_id]
    log_file = open(os.path.join(data['folder'], "terminal.log"), "a", encoding='utf-8')
    proc = subprocess.Popen([sys.executable, "-u", data.get('script', 'main.py')], cwd=data['folder'],
                            stdin=subprocess.PIPE, stdout=log_file, stderr=subprocess.STDOUT, text=True, bufsize=1)
    active_processes[i_id] = proc
    running_instances[i_id].update({'status': 'running', 'pid': proc.pid})
    save_db(DB_INSTANCES, running_instances)


def stop_instance_bg(i_id):
    if i_id in active_processes:
        try:
            active_processes[i_id].terminate(); active_processes.pop(i_id)
        except:
            pass
    if i_id in running_instances:
        try:
            psutil.Process(running_instances[i_id]['pid']).terminate()
        except:
            pass
        running_instances[i_id]['status'] = 'stopped'
        save_db(DB_INSTANCES, running_instances)


@bot.message_handler(func=lambda message: message.text == "📞 Support")
def menu_support(message): bot.reply_to(message, f"📞 <b>Contact Support:</b> {SUPPORT_USER}", parse_mode="HTML")


print("========================================")
print(" 🚀 PREMIUM MASTER CPANEL STARTED ")
print("========================================")
try:
    bot.infinity_polling()
except KeyboardInterrupt:
    print("\n🛑 Server Stopped Safely.")