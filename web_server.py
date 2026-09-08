# web_server.py
from __future__ import annotations

import asyncio
import json
from datetime import datetime
import aiohttp
from aiohttp import web as aio_web

from config_parser import GH_ACCOUNTS, ADMIN_IDS, CHANNEL_ID, IST


def register_web_routes(
    app: aio_web.Application,
    backup_lock: asyncio.Lock,
    last_run_dict: dict,
) -> None:
    async def _handle_root(request: aio_web.Request) -> aio_web.Response:
        html = """<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>GitHub Backup Bot</title>
<style>
  body{{font-family:system-ui,sans-serif;max-width:600px;margin:60px auto;padding:0 20px;color:#1a1a1a}}
  h1{{font-size:1.6rem}}
  span.ok{{color:#16a34a}}
  span.busy{{color:#d97706}}
  table{{width:100%;border-collapse:collapse;margin-top:1rem}}
  td,th{{text-align:left;padding:6px 10px;border-bottom:1px solid #e5e5e5}}
  th{{background:#f5f5f5}}
  code{{background:#f0f0f0;padding:2px 6px;border-radius:4px}}
</style></head>
<body>
<h1>🤖 GitHub Backup Bot</h1>
<p>Status: <span class="{status_cls}"><strong>{status_txt}</strong></span></p>
<table>
  <tr><th>Key</th><th>Value</th></tr>
  <tr><td>GitHub accounts</td><td><code>{accounts}</code></td></tr>
  <tr><td>Telegram channel</td><td><code>{channel}</code></td></tr>
  <tr><td>Admins</td><td><code>{admins}</code></td></tr>
  <tr><td>Schedule</td><td>00:00 IST daily</td></tr>
  <tr><td>Last run</td><td>{last_run}</td></tr>
  <tr><td>Server time (IST)</td><td><code>{now}</code></td></tr>
</table>
<p style="margin-top:2rem;font-size:.85rem;color:#666">
  Commands: <code>/start</code> &nbsp; <code>/backup</code> &nbsp; <code>/status</code>
</p>
</body></html>"""

        busy = backup_lock.locked()
        body = html.format(
            status_cls="busy" if busy else "ok",
            status_txt="Backup in progress…" if busy else "Idle — healthy",
            accounts=", ".join(u for _, u in GH_ACCOUNTS),
            channel=str(CHANNEL_ID),
            admins=len(ADMIN_IDS),
            last_run=last_run_dict.get("timestamp", "—"),
            now=datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S"),
        )
        return aio_web.Response(text=body, content_type="text/html")

    async def _handle_health(request: aio_web.Request) -> aio_web.Response:
        payload = {
            "status": "busy" if backup_lock.locked() else "ok",
            "service": "github-backup-bot",
            "github_accounts": [u for _, u in GH_ACCOUNTS],
            "admins": len(ADMIN_IDS),
            "channel": str(CHANNEL_ID),
            "schedule": "00:00 IST daily",
            "backup_running": backup_lock.locked(),
            "last_run": last_run_dict or None,
            "timestamp_ist": datetime.now(IST).isoformat(),
        }
        return aio_web.Response(
            text=json.dumps(payload, indent=2),
            content_type="application/json",
        )

    app.router.add_get("/", _handle_root)
    app.router.add_get("/health", _handle_health)
    app.router.add_get("/healthz", _handle_health)
    app.router.add_get("/ping", _handle_health)


async def start_web_server(
    port: int,
    backup_lock: asyncio.Lock,
    last_run_dict: dict,
) -> aio_web.AppRunner:
    app = aio_web.Application()
    register_web_routes(app, backup_lock, last_run_dict)
    runner = aio_web.AppRunner(app)
    await runner.setup()
    site = aio_web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    return runner