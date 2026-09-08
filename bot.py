# bot.py
from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pyrogram import Client, idle

from config_parser import (
    API_ID,
    API_HASH,
    BOT_TOKEN,
    CHANNEL_ID,
    ADMIN_IDS,
    GH_ACCOUNTS,
    WEB_PORT,
    BACKUP_RANGE,
    IST,
    create_backup_trigger,
)
from helpers import get_backup_lock, get_last_run, scheduled_backup
from plugins import register_handlers
from web_server import start_web_server

try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-8s │ %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("gh-backup")
loop = asyncio.get_event_loop()

bot = Client(
    name="github_backup_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

register_handlers(bot)


async def main() -> None:
    web_runner = await start_web_server(WEB_PORT, get_backup_lock(), get_last_run())
    log.info(f"🌐 Web server → http://0.0.0.0:{WEB_PORT}  (health: /health)")

    scheduler = AsyncIOScheduler(timezone=IST)
    trigger = create_backup_trigger()

    scheduler.add_job(
        scheduled_backup,
        args=[bot],
        trigger=trigger,
        id="github_backup",
        name=f"GitHub {BACKUP_RANGE} backup",
        replace_existing=True,
        misfire_grace_time=3600,
        coalesce=True,
        max_instances=1,
    )

    scheduler.start()
    log.info("Scheduler online — %s backup at 00:00 IST", BACKUP_RANGE)

    await bot.start()
    log.info(
        f"Bot online ✓ │ admins={sorted(ADMIN_IDS)} │ "
        f"accounts={[u for _, u in GH_ACCOUNTS]}"
    )
    await bot.send_message(CHANNEL_ID, "Bot Started ✅")

    await idle()

    await bot.stop()
    scheduler.shutdown(wait=False)
    await web_runner.cleanup()
    log.info("Bot stopped — goodbye.")


if __name__ == "__main__":
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logging.info("----------------------- Service Stopped -----------------------")