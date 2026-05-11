import logging
import os
import random
import sys
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
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

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


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
    if LOCK_FILE.exists():
        existing_pid_text = LOCK_FILE.read_text(encoding="utf-8").strip()
        if existing_pid_text.isdigit() and is_pid_running(int(existing_pid_text)):
            raise RuntimeError(
                "Another bot instance is already running. Stop it before starting a new one."
            )
        LOCK_FILE.unlink(missing_ok=True)
    LOCK_FILE.write_text(str(os.getpid()), encoding="utf-8")


def release_lock() -> None:
    LOCK_FILE.unlink(missing_ok=True)


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
        "Let's play Rock-Paper-Scissors!\nChoose one:",
        reply_markup=keyboard(),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Use /start to play Rock-Paper-Scissors.",
        reply_markup=keyboard(),
    )


async def fallback_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Send /start (or tap a choice below) to play.",
        reply_markup=keyboard(),
    )


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
            ("start", "Start Rock-Paper-Scissors"),
            ("help", "How to use the bot"),
        ]
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    error_text = str(context.error)
    if "terminated by other getUpdates request" in error_text:
        logger.error(
            "Conflict detected: another polling bot instance is active. Stop duplicates and restart."
        )
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
