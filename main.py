import asyncio
import datetime
import json
import os
import random
import string
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ====== CONFIG ======
TOKEN = "7318584635:AAE7HIFZiBeytAH-14M_ixyhtjOPrc0P06s"
ADMIN_ID = 7598401539
GROUP_CHAT_ID = -1002860765460
API_URL = "https://apibomaylanhat.onrender.com/predict"

KEY_FILE = "keys.json"
STATE_FILE = "states.json"

# ====== DATA STORAGE ======
def load_data(file, default):
    if os.path.exists(file):
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

def save_data(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

key_store = load_data(KEY_FILE, {})
user_states = load_data(STATE_FILE, {})

last_session = None

# ====== SUPPORT FUNCTIONS ======
def generate_key(length=12):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def check_key_valid(user_id):
    if str(user_id) in key_store:
        info = key_store[str(user_id)]
        expire = datetime.datetime.strptime(info["expire"], "%Y-%m-%d %H:%M:%S")
        return expire > datetime.datetime.now()
    return False

# ====== BOT COMMANDS ======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🤖 **BOT DỰ ĐOÁN SUNWIN**\n\n"
        "📋 Danh sách lệnh:\n"
        "`/key <key>` - Nhập key để kích hoạt\n"
        "`/checkkey` - Kiểm tra key còn hạn không\n"
        "`/chaybot` - Bắt đầu nhận dự đoán\n"
        "`/tatbot` - Dừng nhận dự đoán\n"
        "`/stop` - Ngừng bot\n"
        "`/taokey <time> <devices>` - Tạo key (admin)\n"
        "`/help` - Hướng dẫn sử dụng"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 **HƯỚNG DẪN**\n"
        "1️⃣ Nhập key: `/key <key>`\n"
        "2️⃣ Bật bot: `/chaybot`\n"
        "3️⃣ Tắt bot: `/tatbot`\n"
        "4️⃣ Admin tạo key: `/taokey 3d 1` (3 ngày, 1 thiết bị)",
        parse_mode="Markdown"
    )

async def key_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("❌ Sai cú pháp!\nVí dụ: `/key ABC123`", parse_mode="Markdown")
        return
    user_id = str(update.effective_user.id)
    key = context.args[0]
    if key in key_store:
        expire = key_store[key]["expire"]
        devices = key_store[key]["devices"]
        key_store[user_id] = {"expire": expire, "devices": devices}
        save_data(KEY_FILE, key_store)
        await update.message.reply_text(f"✅ Key kích hoạt thành công! Hạn dùng đến {expire}")
        return
    await update.message.reply_text("❌ Key không hợp lệ!")

async def checkkey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id in key_store:
        expire = key_store[user_id]["expire"]
        await update.message.reply_text(f"🔑 Key của bạn hết hạn vào: {expire}")
    else:
        await update.message.reply_text("⛔ Bạn chưa nhập key!")

async def chaybot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if not check_key_valid(user_id):
        await update.message.reply_text("⛔ Key hết hạn hoặc chưa có!")
        return
    user_states[user_id] = True
    save_data(STATE_FILE, user_states)
    await update.message.reply_text("✅ Đã bật nhận dự đoán.")

async def tatbot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    user_states[user_id] = False
    save_data(STATE_FILE, user_states)
    await update.message.reply_text("⛔ Đã tắt nhận dự đoán.")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Tạm biệt!")
    user_id = str(update.effective_user.id)
    if user_id in user_states:
        del user_states[user_id]
        save_data(STATE_FILE, user_states)

async def taokey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Bạn không có quyền!")
        return
    if len(context.args) != 2:
        await update.message.reply_text("❌ Sai cú pháp!\nVD: `/taokey 3d 1`", parse_mode="Markdown")
        return
    time_str = context.args[0]
    devices = int(context.args[1])
    if not time_str.endswith("d"):
        await update.message.reply_text("❌ Thời gian phải có 'd'!")
        return
    days = int(time_str[:-1])
    expire_date = (datetime.datetime.now() + datetime.timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    new_key = generate_key()
    key_store[new_key] = {"expire": expire_date, "devices": devices}
    save_data(KEY_FILE, key_store)
    await update.message.reply_text(
        f"🔑 **TẠO KEY THÀNH CÔNG**\n🆔 Key: `{new_key}`\n📅 Hạn: {expire_date}\n📱 Thiết bị: {devices}",
        parse_mode="Markdown"
    )

# ====== API LOOP ======
import asyncio

async def notify_users(app):
    global last_session
    lock = asyncio.Lock()  # khóa để tránh gửi trùng khi task restart

    while True:
        try:
            async with lock:  # chỉ cho phép 1 vòng lặp xử lý tại 1 thời điểm
                res = requests.get(API_URL, timeout=5).json()

                if "phien" in res:
                    session = res["phien"]

                    # Chỉ gửi nếu là phiên mới
                    if session != last_session:
                        last_session = session
                        msg = (
                            f"🎲 **PHIÊN:** `{res['phien']}`\n"
                            f"🎲 **XÚC XẮC:** {res['xuc_xac']}\n"
                            f"📊 **KẾT QUẢ:** {res['ket_qua']}\n"
                            f"🔮 **DỰ ĐOÁN:** {res['du_doan']}"
                        )

                        # Gửi cho tất cả user đã bật bot
                        for uid, state in user_states.items():
                            if state and check_key_valid(uid):
                                try:
                                    await app.bot.send_message(
                                        chat_id=int(uid),
                                        text=msg,
                                        parse_mode="Markdown"
                                    )
                                except Exception as e:
                                    print(f"Lỗi gửi cho {uid}: {e}")

            await asyncio.sleep(1)  # kiểm tra API mỗi 1 giây

        except Exception as e:
            print("Lỗi vòng lặp:", e)
            await asyncio.sleep(2)  # nghỉ 2 giây nếu lỗi

# ====== MAIN ======
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("key", key_cmd))
    app.add_handler(CommandHandler("checkkey", checkkey))
    app.add_handler(CommandHandler("chaybot", chaybot))
    app.add_handler(CommandHandler("tatbot", tatbot))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("taokey", taokey))

    loop = asyncio.get_event_loop()
    loop.create_task(notify_users(app))

    print("✅ Bot đang chạy...")
    app.run_polling()
