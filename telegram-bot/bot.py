import os
import logging
import httpx
from dotenv import load_dotenv
import io

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

logger = logging.getLogger(__name__)


# ----------------------
# START COMMAND
# ----------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = (
        "👋 Hi, I'm Sibyl\n\n"
        "I autonomously find internships tailored for you.\n\n"
        "Commands:\n"
        "/resume — Upload resume\n"
        "/profile — View profile\n"
        "/test — Send test job\n"
        "/help — Help"
    )

    await update.message.reply_text(message)


# ----------------------
# HELP COMMAND
# ----------------------

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Commands:\n"
        "/start\n"
        "/resume\n"
        "/profile\n"
        "/test"
    )


# ----------------------
# TEST JOB ALERT
# ----------------------

async def send_test_job(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = [
        [
            InlineKeyboardButton("👍 Good", callback_data="good"),
            InlineKeyboardButton("👎 Bad", callback_data="bad")
        ],
        [
            InlineKeyboardButton("🤏 Close", callback_data="close"),
            InlineKeyboardButton("🚫 Ignore", callback_data="ignore")
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    message = (
        "🔥 8.9 MATCH — Frontend Intern @ Meow\n\n"
        "🧠 Why:\n"
        "• React + UI alignment\n"
        "• Matches your profile\n\n"
        "⚠️ Missing:\n"
        "• Next.js\n\n"
        "🤔 Uncertainty:\n"
        "• JD unclear about frontend depth\n\n"
        "🌍 Remote: Yes\n"
        "🔗 Apply: example.com"
    )

    await update.message.reply_text(
        message,
        reply_markup=reply_markup
    )


# ----------------------
# BUTTON HANDLER
# ----------------------

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    feedback = query.data

    logger.info(f"Feedback received: {feedback}")

    await query.edit_message_text(
        text=f"Feedback received: {feedback}"
    )


# ----------------------
# RESUME HANDLER
# ----------------------

async def resume(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "📄 Upload your resume (PDF)"
    )


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):

    file = update.message.document

    await update.message.reply_text(
        f"✅ Resume received: {file.file_name}"
    )

    thinking_msg = await update.message.reply_text(
        "🧠 Analyzing resume...\nThis may take a few seconds..."
    )

    try:
        file_obj = await file.get_file()
        file_bytes = await file_obj.download_as_bytearray()

        file_stream = io.BytesIO(file_bytes)

        async with httpx.AsyncClient(timeout=60) as client:

            response = await client.post(
                "http://127.0.0.1:8000/parse-resume",
                files={
                    "file": ("resume.pdf", file_stream, "application/pdf")
                }
            )

        data = response.json()

        message = format_resume(data)

        await thinking_msg.edit_text(message)

    except Exception as e:
        logger.error(f"Resume parsing failed: {e}")

        await thinking_msg.edit_text(
            "❌ Failed to parse resume.\nPlease try again."
        )

def format_resume(data):

    message = "🧠 Resume Parsed\n\n"

    if data.get("role"):
        message += f"🎯 Role:\n{data['role']}\n\n"

    if data.get("skills"):
        message += "🛠 Skills:\n"
        for skill in data["skills"][:10]:
            message += f"• {skill}\n"
        message += "\n"

    if data.get("technologies"):
        message += "⚙️ Technologies:\n"
        for tech in data["technologies"][:10]:
            message += f"• {tech}\n"
        message += "\n"

    return message
# ----------------------
# PROFILE
# ----------------------

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "🧠 Your Profile\n\n"
        "Role: Frontend-focused\n"
        "Skills:\n"
        "• React\n"
        "• Python\n"
        "• UI"
    )


# ----------------------
# MAIN
# ----------------------

def main():

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("test", send_test_job))
    app.add_handler(CommandHandler("resume", resume))
    app.add_handler(CommandHandler("profile", profile))

    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    app.add_handler(CallbackQueryHandler(button_handler))

    print("Sibyl is running...")

    app.run_polling()


if __name__ == "__main__":
    main()