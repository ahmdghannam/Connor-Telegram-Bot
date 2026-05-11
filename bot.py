import logging
import os
import random
import sys
import urllib.parse
import urllib.request
from json import loads
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

CHOICES = ["rock", "paper", "scissors"]
EMOJI = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}
LOCK_FILE = Path(".bot.lock")
CAT_API_BASE = "https://api.thecatapi.com/v1/images/search"
CAT_BREEDS_API = "https://api.thecatapi.com/v1/breeds"
CAT_API_USER_AGENT = "ConnorTelegramBot/1.0"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)
SCRIPT_DIR = Path(__file__).resolve().parent


def load_local_env() -> None:
    env_path = Path(".env")
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def is_pid_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def acquire_lock() -> None:
    lock_path = SCRIPT_DIR / LOCK_FILE
    if lock_path.exists():
        existing_pid_text = lock_path.read_text(encoding="utf-8").strip()
        if existing_pid_text.isdigit() and is_pid_running(int(existing_pid_text)):
            raise RuntimeError(
                "Another bot instance is already running. Stop it before starting a new one."
            )
        lock_path.unlink(missing_ok=True)
    lock_path.write_text(str(os.getpid()), encoding="utf-8")


def release_lock() -> None:
    (SCRIPT_DIR / LOCK_FILE).unlink(missing_ok=True)


def get_result(user_choice: str, bot_choice: str) -> str:
    if user_choice == bot_choice:
        return "It's a draw!"
    wins = {
        ("rock", "scissors"),
        ("paper", "rock"),
        ("scissors", "paper"),
    }
    return "You win! 🎉" if (user_choice, bot_choice) in wins else "You lose! 😅"


def keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton("🪨 Rock", callback_data="rock"),
            InlineKeyboardButton("📄 Paper", callback_data="paper"),
            InlineKeyboardButton("✂️ Scissors", callback_data="scissors"),
        ]
    ]
    return InlineKeyboardMarkup(buttons)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Welcome! 🐱\n\n"
        "Quick actions:\n"
        "/cat - random cat image\n"
        "/rps - play Rock-Paper-Scissors\n\n"
        "Need full instructions? Use /help",
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Full command guide:\n"
        "/start - quick menu\n"
        "/help - detailed usage\n"
        "/cat [count] [breed_id] - cat image generator\n"
        "/breeds - list available breed IDs\n"
        "/rps - play Rock-Paper-Scissors\n\n"
        "Cat generator examples:\n"
        "/cat\n"
        "/cat 3\n"
        "/cat 5 beng\n\n"
        "Find breed IDs with:\n"
        "/breeds\n\n"
        "Notes:\n"
        "- count range is 1 to 10\n"
        "- breed_id is optional (example: beng)\n"
        "- add CAT_API_KEY in .env for advanced filtering/reliability\n\n"
        "Use /rps to play Rock-Paper-Scissors.",
    )


async def fallback_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Try /cat for random cat images, /rps to play, or /start for all commands.",
    )


async def rps_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Let's play Rock-Paper-Scissors!\nChoose one:",
        reply_markup=keyboard(),
    )


def fetch_cat_images(limit: int, breed_id: str | None, api_key: str | None) -> list[dict]:
    params = {"limit": str(limit)}
    if breed_id:
        params["breed_ids"] = breed_id
    if api_key:
        params["api_key"] = api_key

    url = f"{CAT_API_BASE}?{urllib.parse.urlencode(params)}"
    headers = {
        "Accept": "application/json",
        "User-Agent": CAT_API_USER_AGENT,
    }
    if api_key:
        headers["x-api-key"] = api_key
    req = urllib.request.Request(url, headers=headers)

    with urllib.request.urlopen(req, timeout=15) as response:
        body = response.read().decode("utf-8")
    data = loads(body)
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict) and item.get("url")]


def fetch_breeds(api_key: str | None) -> list[dict]:
    headers = {
        "Accept": "application/json",
        "User-Agent": CAT_API_USER_AGENT,
    }
    if api_key:
        headers["x-api-key"] = api_key
    req = urllib.request.Request(CAT_BREEDS_API, headers=headers)

    with urllib.request.urlopen(req, timeout=15) as response:
        body = response.read().decode("utf-8")
    data = loads(body)
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict) and item.get("id") and item.get("name")]


async def cat_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    count = 1
    breed_id: str | None = None

    if args:
        first = args[0].strip()
        if first.isdigit():
            count = int(first)
            if len(args) > 1:
                breed_id = args[1].strip()
        else:
            breed_id = first

    count = max(1, min(count, 10))
    api_key = os.getenv("CAT_API_KEY")

    try:
        images = fetch_cat_images(limit=count, breed_id=breed_id, api_key=api_key)
    except Exception as exc:
        logger.exception("Cat API request failed", exc_info=exc)
        await update.message.reply_text(
            "Could not reach TheCatAPI right now. Try again in a moment."
        )
        return

    if not images:
        await update.message.reply_text(
            "No cat images found for that request. Try another breed or no breed."
        )
        return

    if len(images) == 1:
        image = images[0]
        caption = "Here is your cat! 🐱"
        if breed_id:
            caption += f" (breed: {breed_id})"
        await update.message.reply_photo(photo=image["url"], caption=caption)
        return

    media = [InputMediaPhoto(media=image["url"]) for image in images]
    await update.message.reply_media_group(media=media)


async def breeds_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    api_key = os.getenv("CAT_API_KEY")
    try:
        breeds = fetch_breeds(api_key=api_key)
    except Exception:
        await update.message.reply_text(
            "Could not fetch breeds right now. Try again in a moment."
        )
        return

    if not breeds:
        await update.message.reply_text("No breeds returned from TheCatAPI.")
        return

    lines = [f"{breed['name']} -> `{breed['id']}`" for breed in breeds[:30]]
    message = "Common breed IDs:\n" + "\n".join(lines)
    message += "\n\nUse like: /cat 3 beng"
    await update.message.reply_text(message, parse_mode="Markdown")


async def play(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    user_choice = query.data
    bot_choice = random.choice(CHOICES)
    result = get_result(user_choice, bot_choice)

    message = (
        f"You chose: {EMOJI[user_choice]} {user_choice.title()}\n"
        f"I chose: {EMOJI[bot_choice]} {bot_choice.title()}\n\n"
        f"{result}\n\n"
        "Play again:"
    )
    await query.edit_message_text(message, reply_markup=keyboard())


async def post_init(application: Application) -> None:
    await application.bot.set_my_commands(
        [
            ("start", "Show command menu"),
            ("help", "How to use the bot"),
            ("cat", "Get random cat image(s)"),
            ("breeds", "List cat breed IDs"),
            ("rps", "Play Rock-Paper-Scissors"),
        ]
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    error_text = str(context.error)
    if "terminated by other getUpdates request" in error_text:
        logger.error(
            "Conflict detected: another polling bot instance is active. Stop duplicates and restart."
        )
        await context.application.stop()
        return
    logger.exception("Unhandled bot error", exc_info=context.error)


def main() -> None:
    load_local_env()
    acquire_lock()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("Please set TELEGRAM_BOT_TOKEN in your environment or .env.")

    app = Application.builder().token(token).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("cat", cat_command))
    app.add_handler(CommandHandler("breeds", breeds_command))
    app.add_handler(CommandHandler("rps", rps_command))
    app.add_handler(CallbackQueryHandler(play))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, fallback_text))
    app.add_error_handler(error_handler)

    try:
        print("Bot is running... Press Ctrl+C to stop.")
        app.run_polling()
    finally:
        release_lock()


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        print(exc)
        sys.exit(1)
