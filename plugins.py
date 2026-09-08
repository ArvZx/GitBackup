# plugins.py
from __future__ import annotations

import logging
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message

from config_parser import ADMIN_IDS, GH_ACCOUNTS, CHANNEL_ID, BACKUP_RANGE, IST
from helpers import get_backup_lock, get_last_run, run_backup

log = logging.getLogger("gh-backup")


def _admin_check(_, __, msg: Message) -> bool:
    return bool(msg.from_user and msg.from_user.id in ADMIN_IDS)


admin_filter = filters.create(_admin_check, name="AdminFilter")


def register_handlers(bot: Client) -> None:
    @bot.on_message(filters.command("start") & admin_filter)
    async def cmd_start(_: Client, msg: Message) -> None:
        accts = "\n".join(f"   • `{u}`" for _, u in GH_ACCOUNTS)
        await msg.reply_text(
            "🤖 **GitHub Backup Bot**\n\n"
            f"Backs up all repos for:\n{accts}\n\n"
            "Uploads a password-protected ZIP to the channel "
            f"{BACKUP_RANGE}at **12:00 AM IST**.\n\n"
            "**Commands (admin only):**\n"
            "• /start  — This message\n"
            "• /backup — Run a backup right now\n"
            "• /status — Show bot status\n"
            "• /accounts — List configured GitHub accounts"
        )

    @bot.on_message(filters.command("backup") & admin_filter)
    async def cmd_backup(client: Client, msg: Message) -> None:
        status = await msg.reply("🔄 Starting backup… this may take a while.")
        await run_backup(client, status)

    @bot.on_message(filters.command("status") & admin_filter)
    async def cmd_status(_: Client, msg: Message) -> None:
        now = datetime.now(IST)
        busy = get_backup_lock().locked()
        state = "🔒 Backup in progress" if busy else "✅ Idle"
        last_run = get_last_run()
        last = last_run.get("timestamp", "Never")
        dur = last_run.get("duration_sec")
        dur_txt = f" ({int(dur)//60}m {int(dur)%60}s)" if dur else ""

        await msg.reply(
            "**Bot Status**\n\n"
            f"🕐 IST now:      `{now.strftime('%Y-%m-%d %H:%M:%S')}`\n"
            f"⏰ Next backup:  `00:00 IST {BACKUP_RANGE}`\n"
            f"⚙️  State:        {state}\n"
            f"📅 Last run:     `{last}{dur_txt}`\n"
            f"📢 Channel:      `{CHANNEL_ID}`\n"
            f"👤 Accounts:     {len(GH_ACCOUNTS)}\n"
            f"🔑 Admins:       {len(ADMIN_IDS)}"
        )

    @bot.on_message(filters.command("accounts") & admin_filter)
    async def cmd_accounts(_: Client, msg: Message) -> None:
        lines = ["**Configured GitHub Accounts**\n"]
        for i, (_, username) in enumerate(GH_ACCOUNTS, 1):
            lines.append(f"{i}. `{username}`")
        await msg.reply("\n".join(lines))