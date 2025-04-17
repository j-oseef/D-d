import telebot
import os
import subprocess
import uuid

# إعداد التوكن مباشرة هنا
BOT_TOKEN = "8007753220:AAEiMB7GLxLOIpSNRhDiGIPFZLkAtPiDizQ"
bot = telebot.TeleBot(BOT_TOKEN)

# بدء الأمر
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "أرسل رابط فيديو من Dailymotion لتحميله.")

# استقبال الرابط
@bot.message_handler(func=lambda message: message.text.startswith("http"))
def handle_video_link(message):
    url = message.text.strip()
    chat_id = message.chat.id

    bot.send_message(chat_id, "جاري استخراج الجودات المتاحة...")

    # استخدام streamlink لاستخراج الجودات
    result = subprocess.run(["streamlink", "--json", url], capture_output=True, text=True)

    if result.returncode != 0 or "No playable streams" in result.stdout:
        bot.send_message(chat_id, "لم يتم العثور على جودات قابلة للتحميل.")
        return

    try:
        import json
        streams = json.loads(result.stdout)["streams"]
        markup = telebot.types.InlineKeyboardMarkup()

        for quality in streams:
            markup.add(telebot.types.InlineKeyboardButton(
                text=f"{quality}", callback_data=f"{quality}|{url}"))

        bot.send_message(chat_id, "اختر الجودة التي تريد تحميلها:", reply_markup=markup)

    except Exception as e:
        bot.send_message(chat_id, f"حدث خطأ أثناء تحليل الرابط:\n{str(e)}")

# التعامل مع اختيار الجودة
@bot.callback_query_handler(func=lambda call: True)
def handle_quality_selection(call):
    chat_id = call.message.chat.id
    data = call.data.split("|")
    if len(data) != 2:
        bot.send_message(chat_id, "خطأ في البيانات المختارة.")
        return

    quality, url = data
    bot.send_message(chat_id, f"جاري تحميل الفيديو بالجودة: {quality}...")

    # اسم مؤقت للفيديو
    filename = f"{uuid.uuid4()}.mp4"
    cmd = ["streamlink", url, quality, "-o", filename]
    proc = subprocess.run(cmd, capture_output=True, text=True)

    if proc.returncode != 0:
        bot.send_message(chat_id, "فشل في تحميل الفيديو.")
        return

    bot.send_message(chat_id, "تم تحميل الفيديو، جاري الإرسال...")

    try:
        bot.send_chat_action(chat_id, "upload_video")
        with open(filename, "rb") as f:
            bot.send_video(chat_id, f)
    except Exception as e:
        bot.send_message(chat_id, f"حدث خطأ أثناء إرسال الفيديو:\n{str(e)}")
    finally:
        if os.path.exists(filename):
            os.remove(filename)

bot.polling()
