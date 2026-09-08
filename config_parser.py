# config_parser.py
from __future__ import annotations

import re
import os
import logging
import config
import pytz
from apscheduler.triggers.cron import CronTrigger

log = logging.getLogger("gh-backup")
IST = pytz.timezone("Asia/Kolkata")


def _cfg(attr: str, default=None):
    """
    Read *attr* from config.py.
    Raises ValueError for required fields that are missing or blank.
    """
    v = getattr(config, attr, default)
    if v is None or (isinstance(v, str) and not str(v).strip()):
        raise ValueError(
            f"config.{attr} is not set. Open config.py and fill in the value."
        )
    return v


def _parse_admin_ids() -> frozenset[int]:
    """
    Parse config.ADMINS = "123456789 987654321" → frozenset[int].
    """
    raw = str(getattr(config, "ADMINS", "")).strip()
    ids: set[int] = set()
    for token in raw.split():
        if token.lstrip("-").isdigit():
            ids.add(int(token))
        else:
            log.warning(f"config.ADMINS: ignoring non-numeric entry '{token}'")
    if not ids:
        raise ValueError(
            "config.ADMINS is required — set at least one Telegram user ID. "
            "Use a space to separate multiple IDs."
        )
    return frozenset(ids)


def _parse_github_accounts() -> list[tuple[str, str]]:
    """
    Parse config.GITHUB_TOKENS and config.GITHUB_USERNAMES into a list of (token, username) pairs.
    """
    tokens_raw = str(
        getattr(config, "GITHUB_TOKENS", getattr(config, "GITHUB_TOKEN", ""))
    ).strip()
    usernames_raw = str(
        getattr(config, "GITHUB_USERNAMES", getattr(config, "GITHUB_USERNAME", ""))
    ).strip()

    tokens = tokens_raw.split()
    usernames = usernames_raw.split()

    if not tokens:
        raise ValueError(
            "config.GITHUB_TOKENS is not set. "
            "Use space-separated values for multiple accounts."
        )
    if not usernames:
        raise ValueError(
            "config.GITHUB_USERNAMES is not set. "
            "Must match the order of config.GITHUB_TOKENS."
        )
    if len(tokens) != len(usernames):
        n = min(len(tokens), len(usernames))
        log.warning(
            f"config.GITHUB_TOKENS has {len(tokens)} entries but "
            f"config.GITHUB_USERNAMES has {len(usernames)} — "
            f"using only the first {n} pair(s)."
        )
        tokens, usernames = tokens[:n], usernames[:n]

    pairs = list(zip(tokens, usernames))
    log.info(f"GitHub accounts loaded: {[u for _, u in pairs]}")
    return pairs


API_ID       = int(_cfg("API_ID"))
API_HASH     = str(_cfg("API_HASH")).strip()
BOT_TOKEN    = str(_cfg("BOT_TOKEN")).strip()
ZIP_PASSWORD = str(_cfg("ZIP_PASSWORD")).strip()

_RAW_CH    = str(_cfg("CHANNEL_ID")).strip()
CHANNEL_ID: int | str = (
    int(_RAW_CH) if re.fullmatch(r"-?\d+", _RAW_CH) else _RAW_CH
)

ADMIN_IDS: frozenset[int] = _parse_admin_ids()
GH_ACCOUNTS: list[tuple[str, str]] = _parse_github_accounts()

WEB_PORT = int(
    os.environ.get(
        "PORT",
        getattr(config, "PORT", 8080),
    )
)

MAX_UPLOAD_BYTES = int(getattr(config, "MAX_UPLOAD_MB", 1950)) * 1_048_576

BACKUP_RANGE = str(_cfg("BACKUP_RANGE")).strip().lower()

if BACKUP_RANGE not in {"daily", "weekly", "monthly"}:
    raise ValueError(
        "config.BACKUP_RANGE must be one of: daily, weekly, monthly"
    )

log.info(
    f"Config loaded │ admins={len(ADMIN_IDS)} │ gh_accounts={len(GH_ACCOUNTS)} "
    f"│ channel={CHANNEL_ID} │ web_port={WEB_PORT}"
)


def create_backup_trigger():
    common = {
        "hour": 0,
        "minute": 0,
        "timezone": IST,
    }

    if BACKUP_RANGE == "daily":
        return CronTrigger(**common)

    if BACKUP_RANGE == "weekly":
        return CronTrigger(
            day_of_week="mon",
            **common,
        )

    if BACKUP_RANGE == "monthly":
        return CronTrigger(
            day=1,
            **common,
        )

    raise ValueError(f"Unsupported BACKUP_RANGE: {BACKUP_RANGE}")
