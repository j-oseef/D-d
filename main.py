import os
import uuid
import threading
import logging
import time
from http.client import RemoteDisconnected

from flask import Flask
import telebot
from telebot import types
from yt_dlp import YoutubeDL

# ─── إعداد البوت ───────────────────────────────────────────────────────────────
TOKEN = "7605106279:AAF-axOVnW-RYrCr8UzhAwj-5yjEpNxXlWI"
OWNER_ID = 2046117078
bot = telebot.TeleBot(TOKEN)

logging.basicConfig(level=logging.INFO)

# ─── Flask Web Server (Port Binding) ───────────────────────────────────────────
app = Flask(__name__)

@app.route("/")
def home():
    return "Loli Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# ─── إعداد yt-dlp ─────────────────────────────────────────────────────────────
YDL_OPTS = {
    "outtmpl": "%(id)s.%(ext)s",
    "merge_output_format": "mp4",
    "quiet": True,
    "no_warnings": True,
}

# ─── /start ───────────────────────────────────────────────────────────────────
@bot.message_handler(commands=["start"])
def cmd_start(msg):
    if msg.from_user.id != OWNER_ID:
        bot.reply_to(msg, "عذرًا، هذا البوت خاص.")
        return
    bot.reply_to(msg, "مرحبًا! أرسل رابط فيديو من Dailymotion لاستخراج الجودات.")

# ─── استقبال رابط الفيديو ─────────────────────────────────────────────────────
@bot.message_handler(func=lambda m: m.from_user.id == OWNER_ID and m.text.startswith("http"))
def handle_link(msg):
    url, chat_id = msg.text.strip(), msg.chat.id
    info_msg = bot.send_message(chat_id, "⏳ استخراج الجودات...")
    try:
        with YoutubeDL({**YDL_OPTS, "skip_download": True}) as ydl:
            info = ydl.extract_info(url, download=False)
        fmts = info.get("formats", [])
        # نختار كل الصيغ التي تحتوي فيديو
        valid = [f for f in fmts if f.get("vcodec") != "none"]
        if not valid:
            bot.send_message(chat_id, "❌ لم أجد جودات فيديو.")
            return

        kb = types.InlineKeyboardMarkup(row_width=1)
        for f in valid:
            fid = f["format_id"]
            res = f.get("height") or f.get("format_note") or fid
            size = f.get("filesize") or 0
            size_mb = f"{round(size/1024/1024,1)} MB" if size else "؟ MB"
            kb.add(types.InlineKeyboardButton(
                text=f"{res} — {size_mb}",
                callback_data=f"{url}|{fid}"
            ))
        bot.send_message(chat_id, "✅ اختر الجودة:", reply_markup=kb)

    except Exception as e:
        bot.send_message(chat_id, f"❌ خطأ في استخراج الجودات:\n{e}")
    finally:
        bot.delete_message(chat_id, info_msg.message_id)

# ─── عند اختيار الجودة ────────────────────────────────────────────────────────
@bot.callback_query_handler(func=lambda call: True)
def handle_quality(call):
    # نزيل أي Webhook قائم لتفادي Conflict
    bot.delete_webhook()
    # نرد على التفاعل
    bot.answer_callback_query(call.id)

    chat_id = call.message.chat.id
    url, fmt = call.data.split("|", 1)
    bot.edit_message_text("⏬ جاري التنزيل...", chat_id, call.message.message_id)

    fn = None
    try:
        # إذا الصيغة بدون صوت، ندمج مع أفضل صوت
        with YoutubeDL({**YDL_OPTS, "skip_download": True}) as ydl:
            info = ydl.extract_info(url, download=False)
            f = next(x for x in info["formats"] if x["format_id"] == fmt)
            if f.get("acodec") == "none":
                fmt += "+bestaudio"

        unique = uuid.uuid4().hex
        with YoutubeDL({**YDL_OPTS, "format": fmt, "outtmpl": unique + ".%(ext)s"}) as ydl:
            info = ydl.extract_info(url, download=True)
            fn = ydl.prepare_filename(info)
            if not fn.endswith(".mp4"):
                fn = os.path.splitext(fn)[0] + ".mp4"

        size_mb = round(os.path.getsize(fn) / 1024 / 1024, 1)
        if size_mb > 50:
            bot.send_message(chat_id, f"⚠️ حجم الفيديو {size_mb} MB يتجاوز الحد. اختر جودة أقل.")
            return

        bot.send_message(chat_id, "📤 جاري الإرسال…")
        # محاولة الإرسال مع retry
        sent = False
        for _ in range(3):
            try:
                with open(fn, "rb") as vid:
                    bot.send_video(chat_id, vid, timeout=300)
                sent = True
                break
            except RemoteDisconnected:
                time.sleep(2)
        if not sent:
            # إذا استمر الفشل، نرسل كملف عام
            with open(fn, "rb") as doc:
                bot.send_document(chat_id, doc, caption="تم الإرسال كملف بسبب مشاكل الشبكة.")

        bot.send_message(chat_id, "✅ تم الإرسال بنجاح!")

    except Exception as e:
        bot.send_message(chat_id, f"❌ خطأ أثناء التنزيل/الإرسال:\n{e}")

    finally:
        if fn and os.path.exists(fn):
            os.remove(fn)

# ─── تشغيل Flask + Bot ────────────────────────────────────────────────────────
if __name__ == "__main__":
    # حذف أي Webhook عالق
    bot.delete_webhook()
    # تشغيل خادم الويب على Thread منفصل
    threading.Thread(target=run_flask).start()
    # بدء polling للبوت
    bot.infinity_polling()
