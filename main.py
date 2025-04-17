import os, uuid, threading, logging
from flask import Flask
import telebot
from telebot import types
from yt_dlp import YoutubeDL

# ─── إعداد البوت ───────────────────────────────────────────────────────────────
TOKEN = "8007753220:AAEiMB7GLxLOIpSNRhDiGIPFZLkAtPiDizQ"
OWNER_ID = 2046117078
bot = telebot.TeleBot(TOKEN)

logging.basicConfig(level=logging.INFO)

# ─── Flask Web Server ─────────────────────────────────────────────────────────
app = Flask(__name__)
@app.route("/")
def home():
    return "Loli Bot is running!"
def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

# ─── yt-dlp إعدادات التحميل ───────────────────────────────────────────────────
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
    bot.reply_to(msg, "أرسل رابط فيديو من Dailymotion لاستخراج الجودات.")

# ─── استقبال رابط الفيديو ─────────────────────────────────────────────────────
@bot.message_handler(func=lambda m: m.from_user.id==OWNER_ID and m.text.startswith("http"))
def handle_link(msg):
    url, chat_id = msg.text.strip(), msg.chat.id
    info_msg = bot.send_message(chat_id, "⏳ استخراج الجودات...")
    try:
        with YoutubeDL({**YDL_OPTS, "skip_download": True, "format": "best"}) as ydl:
            info = ydl.extract_info(url, download=False)
        fmts = info.get("formats", [])
        valid = [f for f in fmts if f.get("vcodec")!="none"]
        if not valid:
            bot.send_message(chat_id, "❌ لم أجد جودات فيديو.")
            return

        kb = types.InlineKeyboardMarkup(row_width=1)
        for f in valid:
            fid = f["format_id"]
            res = f.get("height") or f.get("format_note") or fid
            size = f.get("filesize") or 0
            size_mb = f"{round(size/1024/1024,1)}MB" if size else "؟MB"
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
    # الإجابة عن الكولباك
    bot.answer_callback_query(call.id)

    chat_id = call.message.chat.id
    url, fmt = call.data.split("|",1)
    bot.edit_message_text("⏬ جاري التنزيل...", chat_id, call.message.message_id)

    fn = None
    try:
        # دمج الصوت إذا لزم الأمر
        with YoutubeDL({**YDL_OPTS, "skip_download": True}) as ydl:
            info = ydl.extract_info(url, download=False)
            f = next(x for x in info["formats"] if x["format_id"]==fmt)
            if f.get("acodec")=="none":
                fmt += "+bestaudio"

        unique = uuid.uuid4().hex
        with YoutubeDL({**YDL_OPTS, "format": fmt, "outtmpl": unique + ".%(ext)s"}) as ydl:
            info = ydl.extract_info(url, download=True)
            fn = ydl.prepare_filename(info)
            if not fn.endswith(".mp4"):
                fn = os.path.splitext(fn)[0] + ".mp4"

        size_mb = round(os.path.getsize(fn)/1024/1024, 1)
        if size_mb > 50:
            bot.send_message(chat_id, f"⚠️ حجم {size_mb} MB يتجاوز الحد. اختر جودة أصغر.")
        else:
            bot.send_message(chat_id, "📤 جاري الإرسال...")
            with open(fn, "rb") as video:
                bot.send_video(chat_id, video, timeout=180)
            bot.send_message(chat_id, "✅ تم الإرسال!")

    except Exception as e:
        bot.send_message(chat_id, f"❌ خطأ أثناء التنزيل/الإرسال:\n{e}")
    finally:
        if fn and os.path.exists(fn):
            os.remove(fn)

# ─── تشغيل Flask + Bot ────────────────────────────────────────────────────────
if __name__=="__main__":
    threading.Thread(target=run_flask).start()
    bot.infinity_polling()
