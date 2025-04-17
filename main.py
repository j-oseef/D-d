import os
import uuid
import threading
import logging
from flask import Flask
import telebot
from telebot import types
from yt_dlp import YoutubeDL

# ─── إعداد البوت ───────────────────────────────────────────────────────────────
TOKEN = "8007753220:AAEiMB7GLxLOIpSNRhDiGIPFZLkAtPiDizQ"
OWNER_ID = 2046117078
bot = telebot.TeleBot(TOKEN, parse_mode=None)

# ══ إعداد السجل
logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s",
    level=logging.INFO
)

# ─── Flask Web Server (Port Binding) ───────────────────────────────────────────
app = Flask(__name__)

@app.route("/")
def home():
    return "Loli Bot is running!"

def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

# ─── yt-dlp إعدادات التحميل ────────────────────────────────────────────────────
YDL_OPTS = {
    "format": "best[ext=mp4]/best",
    "outtmpl": "%(id)s.%(ext)s",
    "merge_output_format": "mp4",
    "quiet": True,
    "no_warnings": True,
}

# ─── Handlers ──────────────────────────────────────────────────────────────────

# /start
@bot.message_handler(commands=["start"])
def cmd_start(msg):
    if msg.from_user.id != OWNER_ID:
        bot.reply_to(msg, "عذرًا، هذا البوت خاص.")
        return
    bot.reply_to(msg, "مرحبًا! أرسل رابط فيديو من Dailymotion لاستخراج الجودات وتحميله.")

# استقبال رابط الفيديو
@bot.message_handler(func=lambda m: m.from_user.id == OWNER_ID and m.text.startswith("http"))
def handle_link(msg):
    url = msg.text.strip()
    chat_id = msg.chat.id
    info_msg = bot.send_message(chat_id, "⏳ جار استخراج الجودات المتوفرة...")
    try:
        with YoutubeDL({**YDL_OPTS, "skip_download": True}) as ydl:
            info = ydl.extract_info(url, download=False)

        formats = [
            f for f in info.get("formats", [])
            if f.get("vcodec") != "none" and f.get("acodec") != "none" and f.get("filesize")
        ]
        if not formats:
            bot.send_message(chat_id, "❌ لم أجد جودات قابلة للتحميل.")
            return

        # بناء الأزرار
        keyboard = types.InlineKeyboardMarkup(row_width=1)
        for f in formats:
            size_mb = round(f["filesize"] / 1024 / 1024, 1)
            note = f.get("format_note") or f.get("format_id")
            btn = types.InlineKeyboardButton(
                text=f"{note} — {size_mb} MB",
                callback_data=f"{url}|{f['format_id']}"
            )
            keyboard.add(btn)

        bot.send_message(chat_id, "✅ اختر الجودة:", reply_markup=keyboard)

    except Exception as e:
        bot.send_message(chat_id, f"❌ خطأ أثناء استخراج الجودات:\n{e}")
    finally:
        bot.delete_message(chat_id, info_msg.message_id)

# عند اختيار الجودة
@bot.callback_query_handler(func=lambda call: True)
def handle_quality(call):
    call.answer()
    data = call.data.split("|", 1)
    if len(data) != 2:
        bot.edit_message_text("❌ البيانات غير صالحة.", call.message.chat.id, call.message.message_id)
        return

    url, fmt = data
    chat_id = call.message.chat.id

    bot.edit_message_text(f"⏬ جاري تنزيل الفيديو ({fmt})...", chat_id, call.message.message_id)
    unique_id = uuid.uuid4().hex
    filename = f"{unique_id}.mp4"

    try:
        # تنزيل الفيديو
        with YoutubeDL({**YDL_OPTS, "format": fmt, "outtmpl": unique_id + ".%(ext)s"}) as ydl:
            info = ydl.extract_info(url, download=True)
            downloaded = ydl.prepare_filename(info)
            # تأكد أن الامتداد mp4
            if not downloaded.endswith(".mp4"):
                base = os.path.splitext(downloaded)[0]
                downloaded = base + ".mp4"

        size_mb = round(os.path.getsize(downloaded) / 1024 / 1024, 1)
        if size_mb > 50:
            bot.send_message(chat_id, f"⚠️ حجم الفيديو {size_mb} MB، يتجاوز الحد الآمن لإرسال البوت (50 MB).")
        else:
            bot.send_message(chat_id, f"📤 إرسال الفيديو ({size_mb} MB)...")
            with open(downloaded, "rb") as vid:
                bot.send_video(chat_id, vid, timeout=180)
            bot.send_message(chat_id, "✅ تم الإرسال بنجاح!")

    except Exception as e:
        bot.send_message(chat_id, f"❌ حدث خطأ أثناء التنزيل أو الإرسال:\n{e}")

    finally:
        # تنظيف الملف
        if os.path.exists(downloaded):
            os.remove(downloaded)

# ─── تشغيل التطبيق ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # شغّل Flask وPolling جنباً إلى جنب
    threading.Thread(target=run_flask).start()
    bot.infinity_polling()
