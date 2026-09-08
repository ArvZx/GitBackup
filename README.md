# 📦 GitHub Backup Bot

A **Pyrogram**-based Telegram bot that backs up every repository (and every branch) of one or more GitHub accounts, packs them into **AES-256 password-protected ZIPs**, and uploads the archives to a Telegram channel on a configurable schedule.

Includes a built-in **aiohttp web server** so the process stays alive on platforms that require an active HTTP port.

---

## ✨ Features

| Feature | Detail |
|---|---|
| **Multi-account GitHub** | Any number of `(token, username)` pairs — space-separated |
| **All repos + all branches** | Every branch downloaded as its own sub-folder |
| **AES-256 encryption** | ZIP is password-protected with `pyzipper` |
| **Flexible schedule** | `daily` · `weekly` · `monthly` — cron at 00:00 IST via APScheduler |
| **Admin-only commands** | Space-separated Telegram user IDs in `ADMINS` |
| **Auto-split** | Archives > `MAX_UPLOAD_MB` split into `.part000`, `.part001`… |
| **aiohttp keep-alive** | `/`, `/health`, `/healthz`, `/ping` endpoints |
| **Docker-ready** | `docker compose up -d` |

---

## 📁 Project Structure

```
GitBackup/
├── bot.py               # Entry point — wires bot, scheduler, web server
├── config.py            # Environment variable definitions & defaults
├── config_parser.py     # Validation & parsing of all config values
├── helpers.py           # Download, ZIP, split, upload logic
├── plugins.py           # Telegram command handlers (/start, /backup, /status, /accounts)
├── web_server.py        # aiohttp keep-alive server & health endpoints
├── requirements.txt     # Python dependencies
├── Dockerfile           # Container image
├── docker-compose.yml   # Local Docker Compose setup
├── Procfile             # Heroku / Railway process declaration
├── heroku.yml           # Heroku Docker build config
├── app.json             # Heroku one-click deploy manifest
├── render.yaml           # Render deployment blueprint
└── runtime.txt          # Python version pin (buildpack platforms)
```

---

## 📦 Archive Structure

```
github_backup_alice_bob_20240915_000012.zip   (AES-256 encrypted)
├── alice/
│   ├── my-api/
│   │   ├── main/            ← branch folder
│   │   └── develop/
│   └── website/
│       └── main/
└── bob/
    └── cli-tool/
        ├── main/
        └── feature_auth/    ← "/" replaced with "_"
```

---

## 🛠 Prerequisites

- Python **3.10+**
- Telegram **API ID / Hash** → [my.telegram.org](https://my.telegram.org)
- Telegram **Bot Token** → [@BotFather](https://t.me/BotFather)
- GitHub **Personal Access Token(s)** with `repo` + `read:user` scopes
  → [github.com/settings/tokens](https://github.com/settings/tokens)
- Bot must be an **admin** of the target channel with *Post Messages* permission

---

## ⚙️ Environment Variables

### Required

| Variable | Description | Example |
|---|---|---|
| `API_ID` | Telegram app API ID | `12345678` |
| `API_HASH` | Telegram app API hash | `abcdef1234567890abcdef` |
| `BOT_TOKEN` | Token from @BotFather | `123456:ABC-DEF...` |
| `CHANNEL_ID` | `@username` or `-1001…` numeric ID | `@my_backups` |
| `ADMINS` | Space-separated Telegram user IDs | `123456789 987654321` |
| `GITHUB_TOKENS` | Space-separated GitHub PATs | `ghp_tokenA ghp_tokenB` |
| `GITHUB_USERNAMES` | Space-separated usernames (same order as tokens) | `alice bob` |
| `ZIP_PASSWORD` | AES-256 archive password | `s3cr3tP@ss` |

### Optional

| Variable | Default | Description |
|---|---|---|
| `BACKUP_RANGE` | `daily` | Schedule: `daily` · `weekly` · `monthly` |
| `PORT` | `8080` | Web server port (auto-set by Render / Koyeb / Heroku) |
| `MAX_UPLOAD_MB` | `1950` | Max Telegram part size in MB |

### Single-account shorthand (backward-compatible)

```env
GITHUB_TOKEN=ghp_xxx          # alias for GITHUB_TOKENS
GITHUB_USERNAME=alice         # alias for GITHUB_USERNAMES
```

### Multiple accounts

```env
GITHUB_TOKENS=ghp_tokenAlice  ghp_tokenBob  ghp_tokenCarol
GITHUB_USERNAMES=alice         bob            carol
```

---

## 🚀 Deployment

### Option A — Local / VPS

```bash
git clone https://github.com/ArvZx/GitBackup && cd GitBackup

python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

Set environment variables (choose one):

**Shell export (current session)**
```bash
export API_ID=12345678
export API_HASH=your_api_hash
export BOT_TOKEN=your_bot_token
export CHANNEL_ID=@your_channel
export ADMINS="123456789"
export GITHUB_TOKENS=ghp_yourtoken
export GITHUB_USERNAMES=yourusername
export ZIP_PASSWORD=yourpassword
export BACKUP_RANGE=daily
```

**`.env` file (recommended)**
```env
API_ID=12345678
API_HASH=your_api_hash
BOT_TOKEN=your_bot_token
CHANNEL_ID=@your_channel
ADMINS=123456789
GITHUB_TOKENS=ghp_yourtoken
GITHUB_USERNAMES=yourusername
ZIP_PASSWORD=yourpassword
BACKUP_RANGE=daily
MAX_UPLOAD_MB=1950
```

**Run**
```bash
python bot.py
```

**Run as a systemd service (VPS — keep alive on reboot)**

Create `/etc/systemd/system/GitBackup.service`:
```ini
[Unit]
Description=GitHub Backup Bot
After=network.target

[Service]
User=your_user
WorkingDirectory=/path/to/GitBackup
EnvironmentFile=/path/to/GitBackup/.env
ExecStart=/path/to/GitBackup/venv/bin/python bot.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now GitBackup
sudo journalctl -u GitBackup -f
```

---

### Option B — Docker

```bash
git clone https://github.com/ArvZx/GitBackup && cd GitBackup
```

Create a `.env` file (see variables above), then:

```bash
docker compose up -d
docker compose logs -f
```

`docker-compose.yml` uses the local `Dockerfile` — no pre-built image required.

---

### Option C — Koyeb

1. Push the repo to GitHub: `https://github.com/ArvZx/GitBackup`
2. In Koyeb dashboard: **Create service → GitHub → select your repo**
3. Set **Build method** → `Dockerfile`
4. Under **Environment**, add each variable:

   | Key | Value |
   |---|---|
   | `API_ID` | your Telegram API ID |
   | `API_HASH` | your Telegram API hash |
   | `BOT_TOKEN` | your bot token |
   | `CHANNEL_ID` | `@your_channel` or numeric ID |
   | `ADMINS` | `123456789` (space-separated if multiple) |
   | `GITHUB_TOKENS` | `ghp_yourtoken` (space-separated if multiple) |
   | `GITHUB_USERNAMES` | `yourusername` (space-separated if multiple) |
   | `ZIP_PASSWORD` | your zip password |
   | `BACKUP_RANGE` | `daily` |
   | `MAX_UPLOAD_MB` | `1950` |

5. Set **Port** → `8080`
6. Set **Health check path** → `/healthz`
7. Click **Deploy**

> `PORT` is auto-injected by Koyeb at runtime — do not override it.

---

### Option D — Render

Render reads **`render.yaml`** automatically when you connect the repo.

1. Go to [render.com](https://render.com) → **New → Blueprint**
2. Connect repo: `https://github.com/ArvZx/GitBackup`
3. Render will detect `render.yaml` and pre-configure the service
4. Under **Environment**, fill in the secret values (marked `sync: false`):

   | Key | Value |
   |---|---|
   | `API_ID` | your Telegram API ID |
   | `API_HASH` | your Telegram API hash |
   | `BOT_TOKEN` | your bot token |
   | `CHANNEL_ID` | `@your_channel` or numeric ID |
   | `ADMINS` | `123456789` (space-separated if multiple) |
   | `GITHUB_TOKENS` | `ghp_yourtoken` (space-separated if multiple) |
   | `GITHUB_USERNAMES` | `yourusername` (space-separated if multiple) |
   | `ZIP_PASSWORD` | your zip password |

   `BACKUP_RANGE` and `MAX_UPLOAD_MB` are pre-filled in `render.yaml` with defaults.

5. Click **Apply** — Render builds from the Dockerfile automatically
6. Health check path is pre-set to `/healthz` in `render.yaml`

> `PORT` is auto-injected by Render — do not add it as an env var.

---

### Option E — Heroku

Heroku reads **`heroku.yml`** and **`app.json`** (container stack, Docker build).

**One-click deploy (if repo is public)**

Click the **Deploy to Heroku** button at the top of this README — fill in the env vars in the form and deploy.
<!-- Make sure app.json has the correct repository URL: https://github.com/ArvZx/GitBackup -->

**Manual deploy via CLI**

```bash
# Install Heroku CLI: https://devcenter.heroku.com/articles/heroku-cli
heroku login
heroku create your-app-name
# ↑ Choose a unique Heroku app name

# Set the container stack (required for heroku.yml / Docker builds)
heroku stack:set container -a your-app-name

# Set all environment variables
heroku config:set API_ID=12345678 -a your-app-name
heroku config:set API_HASH=your_api_hash -a your-app-name
heroku config:set BOT_TOKEN=your_bot_token -a your-app-name
heroku config:set CHANNEL_ID=@your_channel -a your-app-name
heroku config:set ADMINS="123456789" -a your-app-name
heroku config:set GITHUB_TOKENS=ghp_yourtoken -a your-app-name
heroku config:set GITHUB_USERNAMES=yourusername -a your-app-name
heroku config:set ZIP_PASSWORD=yourpassword -a your-app-name
heroku config:set BACKUP_RANGE=daily -a your-app-name
heroku config:set MAX_UPLOAD_MB=1950 -a your-app-name

# Push and deploy
git push heroku main

# Check logs
heroku logs --tail -a your-app-name
```

> `PORT` is auto-injected by Heroku — do not set it manually. The `Procfile` and `heroku.yml` handle process startup automatically.

---

## 🤖 Bot Commands (admin-only)

| Command | Description |
|---|---|
| `/start` | Help message + list of configured accounts |
| `/backup` | Trigger an immediate backup |
| `/status` | Current time, last run timestamp, bot state |
| `/accounts` | List all configured GitHub accounts |

Non-admin messages are silently ignored — strangers receive no feedback.

---

## 🌐 Web Server Endpoints

| Path | Response | Used by |
|---|---|---|
| `/` | HTML status page | Browser |
| `/health` | JSON status | Koyeb health probe |
| `/healthz` | JSON status | Render / K8s style |
| `/ping` | JSON status | Railway / Fly.io |

**JSON payload example:**
```json
{
  "status": "ok",
  "service": "GitBackup",
  "github_accounts": ["alice", "bob"],
  "admins": 2,
  "channel": "@my_backups",
  "schedule": "00:00 IST daily",
  "backup_running": false,
  "last_run": {
    "timestamp": "2024-09-15 00:03:47 IST",
    "duration_sec": "227",
    "accounts": "alice, bob"
  },
  "timestamp_ist": "2024-09-15T12:00:00+05:30"
}
```

---

## 🔐 Security Notes

- `ZIP_PASSWORD` is never logged or included in Telegram messages.
- Non-admin commands are silently ignored — strangers get no feedback.
- Use **fine-grained PATs** scoped to read-only repository access.
- Tokens live only in memory; your `.env` file should be in `.gitignore`.

---

## 🐛 Troubleshooting

| Symptom | Fix |
|---|---|
| `EnvironmentError: 'ADMINS' is not set` | Add your Telegram user ID to `ADMINS` — get it from @userinfobot |
| `Token/username count mismatch` warning | Ensure `GITHUB_TOKENS` and `GITHUB_USERNAMES` have the same number of space-separated entries |
| Bot ignores your commands | Your user ID is not in `ADMINS` |
| 404 on private repos | PAT is missing `repo` scope |
| Platform kills the service | Confirm health check path is `/healthz` and port matches `PORT` |
| `SessionPasswordNeeded` on restart | Delete `github_backup_bot.session` and restart |
| Heroku deploy fails | Ensure `heroku stack:set container` was run before pushing |
| Render build fails | Confirm `render.yaml` is at the repo root and runtime is set to web |


---

## One Click Deploy Options

[![Deploy to Heroku](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy?template=https://github.com/ArvZx/GitBackup)

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/ArvZx/GitBackup)

[![Deploy to Koyeb](https://www.koyeb.com/static/images/deploy/button.svg)](https://app.koyeb.com/deploy?name=git-backup&type=git&repository=ArvZx%2FGitBackup&branch=main&instance_type=free&regions=fra&instances_min=0&autoscaling_sleep_idle_delay=3900&env%5BAPI_ID%5D=&env%5BAPI_HASH%5D=&env%5BBOT_TOKEN%5D=&env%5BCHANNEL_ID%5D=&env%5BADMINS%5D=&env%5BGITHUB_USERNAMES%5D=&env%5BGITHUB_TOKENS%5D=&env%5BBACKUP_RANGE%5D=&env%5BZIP_PASSWORD%5D=&env%5BMAX_UPLOAD_MB%5D=)
