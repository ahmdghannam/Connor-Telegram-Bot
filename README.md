# Connor Telegram Bot

A simple Telegram bot written in Python.

It currently includes:
- Cat image generator from TheCatAPI
- Cat breed list command
- Rock-Paper-Scissors mini game

## Features

- `/start` - Quick welcome and command hints
- `/help` - Full usage guide
- `/cat [count] [breed_id]` - Get random cat images
  - Examples:
    - `/cat`
    - `/cat 2`
    - `/cat 3 beng`
- `/breeds` - List common breed names with `breed_id`
- `/rps` - Play Rock-Paper-Scissors with inline buttons

## APIs Used

### 1) Telegram Bot API

- Used to receive user messages and send replies, photos, and command menus.
- Accessed through the Python library `python-telegram-bot`.
- Main actions used:
  - Polling updates
  - Sending messages
  - Sending photos/media groups
  - Setting bot command menu (`setMyCommands`)

### 2) TheCatAPI

- Used to fetch random cat images and breed metadata.
- Endpoints used:
  - `https://api.thecatapi.com/v1/images/search`
  - `https://api.thecatapi.com/v1/breeds`
- Authentication:
  - API key is read from `.env` as `CAT_API_KEY`
  - Sent using `x-api-key` header

## Project Structure

- `bot.py` - Main bot code
- `requirements.txt` - Python dependencies
- `.env` - Local environment variables (not committed)

## Setup

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Create `.env` with:

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
CAT_API_KEY=your_cat_api_key
```

3. Run the bot:

```bash
python bot.py
```

## Notes

- Run only one bot instance at a time.
- The bot uses a lock file (`.bot.lock`) to reduce duplicate-run conflicts.
- If commands do not respond, stop all running bot processes and start one clean instance.
