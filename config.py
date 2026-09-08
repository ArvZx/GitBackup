import os

API_ID = int(os.environ.get("API_ID", "")) # Telegram API_ID
API_HASH = os.environ.get("API_HASH", "") # Telegram API_HASH
BOT_TOKEN = os.environ.get("BOT_TOKEN", "") # Telegram BOT_TOKEN get it from @BotFather.

CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "")) # Backup Channel Id. (bot must have msg permissions).
ADMINS = os.environ.get("ADMINS", "") # Multiple admin ids separate by space.

GITHUB_USERNAMES = os.environ.get("GITHUB_USERNAMES", "") # Multiple usernames separate by space.
GITHUB_TOKENS = os.environ.get("GITHUB_TOKENS", "") # Multiple tokens separate by spac.

BACKUP_RANGE = os.environ.get("BACKUP_RANGE", "daily") # Supports daily, weekly, monthly.
# daily: 00:00 IST (daily).
# weekly: 00:00 IST (every monday).
# monthly: 00:00 IST (1st day of every month).

ZIP_PASSWORD = os.environ.get("ZIP_PASSWORD", "git@pass") # Password For the zip file.

PORT = os.environ.get("PORT", "8080") # Leave as it is.
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "1950")) # Default telegram upload size.