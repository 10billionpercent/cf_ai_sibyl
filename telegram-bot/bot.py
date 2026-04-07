import os
import logging
import httpx
import asyncio
from dotenv import load_dotenv
import io

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.error import RetryAfter

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
        "/profile"
    )



# ----------------------
# BUTTON HANDLER
# ----------------------

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    if "|" in query.data:
        action, job_id = query.data.split("|", 1)
    else:
        action, job_id = query.data, None

    logger.info(f"Feedback: {action} | Job: {job_id}")

    if action in ("good", "more", "less", "bad") and job_id:
        job_cache = context.user_data.get("last_jobs", {})
        job = job_cache.get(job_id)
        if job:
            try:
                async with httpx.AsyncClient(timeout=60) as client:
                    if action in ("good", "more"):
                        await client.post(
                            "http://127.0.0.1:8000/save-job",
                            json=job
                        )

                    await client.post(
                        "http://127.0.0.1:8000/job-feedback",
                        json={
                            "job": job,
                            "feedback": "good" if action in ("good", "more") else "bad"
                        }
                    )
            except Exception as e:
                logger.error(f"Save job failed: {e}")

    if action == "more":
        text = "👍 Got it — I'll show more like this"
    else:
        text = "👎 Got it — I'll show less like this"

    await query.edit_message_text(text=text)

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

        async with httpx.AsyncClient(timeout=180) as client:

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

def format_resume(data, header="🧠 Resume Parsed"):

    message = f"{header}\n\n"

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

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get("http://127.0.0.1:8000/latest-resume")
        if response.status_code != 200:
            await update.message.reply_text("⚠️ Could not load your latest resume.")
            return
        data = response.json()
        if data.get("error"):
            await update.message.reply_text("⚠️ No resume found yet.")
            return
        message = format_resume(data, header="🧠 Your Profile")
        await update.message.reply_text(message)
    except Exception as e:
        logger.error(f"Profile fetch failed: {e}")
        await update.message.reply_text("⚠️ Could not load your latest resume.")

def feedback_keyboard(job_id):

    keyboard = [
        [
            InlineKeyboardButton(
                "👍 Show more like this",
                callback_data=f"more|{job_id}"
            )
        ],
        [
            InlineKeyboardButton(
                "👎 Show less like this",
                callback_data=f"less|{job_id}"
            )
        ]
    ]

    return InlineKeyboardMarkup(keyboard)

async def jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):

    msg = await update.message.reply_text(
        "🔎 Searching internships..."
    )

    await msg.edit_text(
    "🔎 Searching internships...\n\nThis may take ~30 seconds..."
    )

    try:
        await msg.edit_text("🔎 Fetching internships...")

        async with httpx.AsyncClient(timeout=20000) as client:
            response = await client.post(
                "http://127.0.0.1:8000/fetch-jobs-stream"
            )

        if response.status_code != 200:
            await msg.edit_text("❌ Failed to fetch internships")
            return

        data = response.json()
        run_id = data.get("run_id")
        if not run_id:
            await msg.edit_text("❌ Backend error")
            return

        await msg.edit_text("🧠 Matching jobs... sending results as they are ready.")

        context.user_data["last_jobs"] = {}

        seen = set()
        cursor = 0
        total = None

        while True:
            async with httpx.AsyncClient(timeout=20000) as client:
                result = await client.get(
                    "http://127.0.0.1:8000/fetch-results",
                    params={"run_id": run_id, "since": cursor}
                )

            if result.status_code != 200:
                await msg.edit_text("❌ Failed to fetch internships")
                return

            payload = result.json()
            status = payload.get("status")
            total = payload.get("total") if total is None else total

            new_jobs = payload.get("results", [])
            cursor = payload.get("next", cursor)

            for idx, job in enumerate(new_jobs, start=1):
                match = job.get("match") or {}
                score = match.get("match_score", "?")

                message = (
                    f"🔥 {score}/10 MATCH — {job.get('title')}\n\n"
                    f"🏢 {match.get('company', 'Unknown')}\n"
                    f"🌐 {job.get('source')}\n\n"
                )

                # Why
                if match.get("why"):
                    message += "🧠 Why:\n"
                    for item in match["why"]:
                        message += f"• {item}\n"
                    message += "\n"

                # Missing
                if match.get("missing"):
                    message += "⚠️ Missing:\n"
                    for item in match["missing"]:
                        message += f"• {item}\n"
                    message += "\n"

                # Uncertainty
                if match.get("uncertainty"):
                    message += "🤔 Uncertainty:\n"
                    for item in match["uncertainty"]:
                        message += f"• {item}\n"
                    message += "\n"

                message += f"🔗 Apply: {job.get('apply_url') or job.get('job_url') or job.get('url')}"

                job_id = str(job.get("job_id") or job.get("id") or job.get("url"))
                context.user_data["last_jobs"][job_id] = job

                if job_id in seen:
                    continue
                seen.add(job_id)

                try:
                    await update.message.reply_text(
                        message,
                        reply_markup=feedback_keyboard(job_id)
                    )
                except RetryAfter as e:
                    await asyncio.sleep(e.retry_after)
                    await update.message.reply_text(
                        message,
                        reply_markup=feedback_keyboard(job_id)
                    )
                except Exception as e:
                    logger.error(f"Send failed: {e}")
                    continue

                await asyncio.sleep(0.5)

            if status == "done":
                break
            if status == "error":
                await msg.edit_text("⚠️ Something went wrong while matching")
                break

            await asyncio.sleep(5)
        

    except Exception as e:

        logger.exception("Jobs command crashed")

        await msg.edit_text(
            "⚠️ Something went wrong while sending results"
        )

# ----------------------
# MAIN
# ----------------------

def main():

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("resume", resume))
    app.add_handler(CommandHandler("profile", profile))
    app.add_handler(CommandHandler("jobs", jobs))

    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    app.add_handler(CallbackQueryHandler(button_handler))

    print("Sibyl is running...")

    app.run_polling()


if __name__ == "__main__":
    main()
