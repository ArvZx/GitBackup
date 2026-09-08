# helpers.py
from __future__ import annotations

import asyncio
import io
import logging
import re
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiohttp
import pyzipper
from github import Github, GithubException
from pyrogram.types import Message

from config_parser import (
    GH_ACCOUNTS,
    CHANNEL_ID,
    ZIP_PASSWORD,
    MAX_UPLOAD_BYTES,
    BACKUP_RANGE,
    IST,
)

log = logging.getLogger("gh-backup")

WORKSPACE = Path("workspace")
OUTPUT_DIR = Path("output")

_backup_lock = asyncio.Lock()
_last_run: dict[str, str] = {}


def get_backup_lock() -> asyncio.Lock:
    return _backup_lock


def get_last_run() -> dict[str, str]:
    return _last_run


def _safe_name(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(".")


async def _download_branch(
    session: aiohttp.ClientSession,
    token: str,
    repo_full_name: str,
    branch: str,
    dest: Path,
    retries: int = 3,
) -> bool:
    url = f"https://api.github.com/repos/{repo_full_name}/zipball/{branch}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    timeout = aiohttp.ClientTimeout(total=300)

    for attempt in range(1, retries + 1):
        try:
            async with session.get(url, headers=headers, allow_redirects=True, timeout=timeout) as resp:
                if resp.status == 404:
                    log.warning(f"      404 — {repo_full_name}@{branch} (inaccessible or missing)")
                    return False
                if resp.status != 200:
                    log.error(f"      HTTP {resp.status} for {repo_full_name}@{branch} (attempt {attempt}/{retries})")
                    if attempt < retries:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    return False
                raw = await resp.read()
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            log.error(f"      Network error {repo_full_name}@{branch} attempt {attempt}: {exc}")
            if attempt < retries:
                await asyncio.sleep(2 ** attempt)
                continue
            return False

        try:
            dest.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                for member in zf.infolist():
                    parts = Path(member.filename).parts
                    if len(parts) <= 1:
                        continue
                    rel = Path(*parts[1:])
                    target = dest / rel
                    if member.is_dir():
                        target.mkdir(parents=True, exist_ok=True)
                    else:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(zf.read(member.filename))
            return True
        except (zipfile.BadZipFile, OSError) as exc:
            log.error(f"      Extract error {repo_full_name}@{branch}: {exc}")
            return False

    return False


async def _backup_one_account(
    session: aiohttp.ClientSession,
    token: str,
    username: str,
    account_dir: Path,
    status_msg: Optional[Message],
    acct_idx: int,
    total_accts: int,
) -> tuple[int, int]:
    prefix = f"[acct {acct_idx}/{total_accts} @{username}]"

    try:
        gh = Github(token, per_page=100)
        user = gh.get_user()
        repos = list(user.get_repos(type="all"))
    except GithubException as exc:
        log.error(f"{prefix} GitHub API error: {exc}")
        return 0, 0

    log.info(f"{prefix} {len(repos)} repos found")

    if status_msg:
        try:
            await status_msg.edit_text(
                f"📡 **Account {acct_idx}/{total_accts}**: `{username}`\n"
                f"Found **{len(repos)} repositories** — downloading…"
            )
        except Exception:
            pass

    ok_count = fail_count = 0
    for idx, repo in enumerate(repos, 1):
        repo_dir = account_dir / _safe_name(repo.full_name)
        repo_dir.mkdir(parents=True, exist_ok=True)

        try:
            branches = list(repo.get_branches())
        except GithubException:
            branches = []

        log.info(f"  {prefix} [{idx:>3}/{len(repos)}] {repo.full_name} — {len(branches)} branch(es)")

        if status_msg and (idx % 10 == 0 or idx == len(repos)):
            try:
                await status_msg.edit_text(
                    f"📥 **@{username}** [{idx}/{len(repos)} repos]\n"
                    f"📦 `{repo.full_name}` — {len(branches)} branch(es)"
                )
            except Exception:
                pass

        for branch in branches:
            dest = repo_dir / _safe_name(branch.name)
            log.info(f"        ↳ {branch.name}")
            success = await _download_branch(
                session, token, repo.full_name, branch.name, dest
            )
            if success:
                ok_count += 1
            else:
                fail_count += 1

    return ok_count, fail_count


async def download_all_accounts(
    status_msg: Optional[Message] = None,
) -> list[tuple[str, Path]]:
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    results: list[tuple[str, Path]] = []
    total_accts = len(GH_ACCOUNTS)
    timestamp = datetime.now(IST).strftime("%Y%m%d_%H%M%S")

    async with aiohttp.ClientSession() as session:
        for acct_idx, (token, username) in enumerate(GH_ACCOUNTS, 1):
            safe_user = _safe_name(username)
            account_dir = WORKSPACE / safe_user
            account_dir.mkdir(parents=True, exist_ok=True)

            ok, fail = await _backup_one_account(
                session, token, username, account_dir,
                status_msg, acct_idx, total_accts,
            )

            files_to_zip = [f for f in account_dir.rglob("*") if f.is_file()]
            if not files_to_zip:
                log.warning(
                    f"@{username}: account_dir is empty "
                    f"(all {fail} branch(es) failed?) — skipping ZIP"
                )
                shutil.rmtree(account_dir, ignore_errors=True)
                continue

            zip_path = OUTPUT_DIR / f"{safe_user}_{timestamp}.zip"
            log.info(f"Building ZIP for @{username} → {zip_path.name}  ({len(files_to_zip)} files)")

            if status_msg:
                try:
                    await status_msg.edit_text(
                        f"🗜️ **[{acct_idx}/{total_accts}]** Packing `{username}` "
                        f"({ok} branches, {len(files_to_zip)} files) → `{zip_path.name}`…"
                    )
                except Exception:
                    pass

            def _build_zip(
                _zip_path: Path,
                _account_dir: Path,
                _files: list[Path],
                _password: str,
            ) -> None:
                with pyzipper.AESZipFile(
                    _zip_path,
                    mode="w",
                    compression=pyzipper.ZIP_DEFLATED,
                    encryption=pyzipper.WZ_AES,
                ) as zf:
                    zf.setpassword(_password.encode())
                    for fpath in sorted(_files):
                        zf.write(fpath, fpath.relative_to(_account_dir))

            try:
                await asyncio.get_event_loop().run_in_executor(
                    None, _build_zip, zip_path, account_dir, files_to_zip, ZIP_PASSWORD
                )
            except Exception as zip_exc:
                log.error(f"@{username}: ZIP creation FAILED — {zip_exc}", exc_info=True)
                zip_path.unlink(missing_ok=True)
                shutil.rmtree(account_dir, ignore_errors=True)
                continue

            if not zip_path.exists() or zip_path.stat().st_size < 100:
                log.error(
                    f"@{username}: ZIP missing or suspiciously small "
                    f"({zip_path.stat().st_size if zip_path.exists() else 0} bytes)"
                )
                zip_path.unlink(missing_ok=True)
                shutil.rmtree(account_dir, ignore_errors=True)
                continue

            size_mb = zip_path.stat().st_size / 1_048_576
            log.info(
                f"@{username} ZIP ready — {size_mb:.1f} MB "
                f"({ok} branches ok, {fail} failed)"
            )
            results.append((username, zip_path))
            shutil.rmtree(account_dir, ignore_errors=True)

    return results


def _split_file(path: Path, chunk_size: int) -> list[Path]:
    parts: list[Path] = []
    buffer_size = 32 * 1024 * 1024

    with path.open("rb") as src:
        idx = 0
        while True:
            part = path.with_suffix(f".part{idx:03d}")
            remaining = chunk_size
            written = 0

            with part.open("wb") as dst:
                while remaining > 0:
                    data = src.read(min(buffer_size, remaining))
                    if not data:
                        break
                    dst.write(data)
                    written += len(data)
                    remaining -= len(data)

            if written == 0:
                part.unlink(missing_ok=True)
                break

            parts.append(part)
            idx += 1

    return parts


async def upload_backup(
    bot_client,
    username: str,
    zip_path: Path,
    acct_idx: int,
    total_accts: int,
    status_msg: Optional[Message] = None,
) -> None:
    file_size = zip_path.stat().st_size

    if file_size > MAX_UPLOAD_BYTES:
        log.info(f"@{username} archive {file_size / 1_048_576:.0f} MB > limit — splitting")
        if status_msg:
            try:
                await status_msg.edit_text(
                    f"✂️ `{username}` archive is too large — splitting into parts…"
                )
            except Exception:
                pass
        parts = _split_file(zip_path, MAX_UPLOAD_BYTES)
    else:
        parts = [zip_path]

    total_parts = len(parts)
    now_str = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")

    for i, part in enumerate(parts, 1):
        size_mb = part.stat().st_size / 1_048_576

        lines = [
            f"📦 **GitHub Backup — `{username}`**",
            "",
            f"👤 Account:   `{username}`",
            f"📅 Generated: `{now_str} IST`",
            f"💾 Size:      `{size_mb:.1f} MB`",
            "🔐 Password-protected (AES-256) — see `ZIP_PASSWORD` env",
        ]
        if total_parts > 1:
            lines.append(f"📂 Part:      `{i} / {total_parts}`")
        if total_accts > 1:
            lines.append(f"🗂 Archive:   `{acct_idx} / {total_accts}`")
        lines += ["", f"__Automated {BACKUP_RANGE} backup · 12:00 AM IST__"]
        caption = "\n".join(lines)

        if status_msg:
            try:
                await status_msg.edit_text(
                    f"📤 **`{username}`** [{acct_idx}/{total_accts}] "
                    f"— uploading part {i}/{total_parts} ({size_mb:.1f} MB)…"
                )
            except Exception:
                pass

        last_pct = [-1]

        async def _prog(current: int, total: int, _i: int = i) -> None:
            pct = int(current * 100 / total)
            if pct // 10 > last_pct[0] // 10:
                last_pct[0] = pct
                log.info(
                    f"  ↑ @{username} [{_i}/{total_parts}] {pct}% "
                    f"({current // 1_048_576}/{total // 1_048_576} MB)"
                )

        await bot_client.send_document(
            chat_id=CHANNEL_ID,
            document=str(part),
            caption=caption,
            progress=_prog,
        )

        if total_parts > 1:
            part.unlink(missing_ok=True)

    log.info(f"@{username} upload complete ✓  ({total_parts} part(s))")


async def run_backup(bot_client, status_msg: Optional[Message] = None) -> None:
    if _backup_lock.locked():
        log.warning("Backup already running — duplicate trigger ignored")
        if status_msg:
            try:
                await status_msg.edit_text("⚠️ A backup is already running. Please wait.")
            except Exception:
                pass
        return

    async with _backup_lock:
        start = datetime.now(IST)
        zip_list: list[tuple[str, Path]] = []
        log.info("═══ Backup pipeline START ═══")

        try:
            if WORKSPACE.exists():
                shutil.rmtree(WORKSPACE)

            zip_list = await download_all_accounts(status_msg)

            if not zip_list:
                if status_msg:
                    try:
                        await status_msg.edit_text(
                            "❌ Backup **failed** — no ZIPs produced. Check bot logs."
                        )
                    except Exception:
                        pass
                return

            total_accts = len(zip_list)
            for acct_idx, (username, zip_path) in enumerate(zip_list, 1):
                if not zip_path.exists():
                    log.error(f"ZIP missing for @{username}: {zip_path}")
                    continue
                await upload_backup(bot_client, username, zip_path, acct_idx, total_accts, status_msg)
                zip_path.unlink(missing_ok=True)

            elapsed = (datetime.now(IST) - start).total_seconds()
            _last_run.update({
                "timestamp": datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST"),
                "duration_sec": str(int(elapsed)),
                "accounts": ", ".join(u for u, _ in zip_list),
                "zips_sent": str(len(zip_list)),
            })
            log.info(f"═══ Backup pipeline END — {elapsed:.0f}s, {len(zip_list)} ZIP(s) sent ═══")

            if status_msg:
                acct_lines = "\n".join(f"   ✅ `{u}`" for u, _ in zip_list)
                try:
                    await status_msg.edit_text(
                        f"✅ **Backup complete!**\n\n"
                        f"{acct_lines}\n\n"
                        f"⏱ Duration: `{int(elapsed // 60)}m {int(elapsed % 60)}s`\n"
                        f"📢 Channel:  `{CHANNEL_ID}`"
                    )
                except Exception:
                    pass

        except Exception as exc:
            log.exception(f"Unhandled error in backup pipeline: {exc}")
            if status_msg:
                try:
                    await status_msg.edit_text(f"❌ Backup **failed**:\n`{exc}`")
                except Exception:
                    pass

        finally:
            if WORKSPACE.exists():
                shutil.rmtree(WORKSPACE, ignore_errors=True)
            for _, zip_path in zip_list:
                zip_path.unlink(missing_ok=True)


async def scheduled_backup(bot_client) -> None:
    log.info("Scheduled %s backup triggered at 00:00 IST", BACKUP_RANGE)
    await run_backup(bot_client)
