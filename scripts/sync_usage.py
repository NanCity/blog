"""Collect a public-only usage snapshot locally through the official Codex RPC.

Credentials stay in the local Codex login. This does not run a model or read chats.
Use --publish in a dedicated, clean checkout to push only gpt-usage.json.
"""

import argparse
from contextlib import contextmanager
from datetime import date, datetime, timezone
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import threading
import time


ROOT = Path(__file__).resolve().parents[1]
SUMMARY_FIELDS = (
    "lifetimeTokens", "peakDailyTokens", "longestRunningTurnSec",
    "currentStreakDays", "longestStreakDays",
)
SAFE_INTEGER = 2**53 - 1


def statistic(value):
    if value is None:
        return None
    if type(value) is not int or not 0 <= value <= SAFE_INTEGER:
        raise ValueError("The usage service returned an invalid numeric field")
    return value


def find_codex(explicit=None):
    if explicit:
        return str(Path(explicit).resolve(strict=True))
    installed = shutil.which("codex")
    if installed:
        return installed
    candidates = list((Path.home() / ".vscode/extensions").glob(
        "openai.chatgpt-*/bin/windows-x86_64/codex.exe"
    ))
    if candidates:
        return str(max(candidates, key=lambda path: path.stat().st_mtime))
    raise RuntimeError("Official Codex CLI not found; install Codex or pass --codex")


def collect(codex):
    process = subprocess.Popen(
        [codex, "app-server"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    inbox = queue.Queue()

    def read_messages():
        for line in process.stdout:
            try:
                inbox.put(json.loads(line))
            except ValueError:
                continue
        inbox.put(None)

    threading.Thread(target=read_messages, daemon=True).start()

    def send(message):
        process.stdin.write(json.dumps(message) + "\n")
        process.stdin.flush()

    def request(method, params, request_id):
        send({"method": method, "params": params, "id": request_id})
        deadline = time.monotonic() + 45
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError("Timed out reading usage from Codex")
            try:
                message = inbox.get(timeout=remaining)
            except queue.Empty as error:
                raise RuntimeError("Timed out reading usage from Codex") from error
            if message is None:
                raise RuntimeError("Codex exited before returning usage")
            if message.get("id") == request_id:
                if "error" in message:
                    # Do not put raw RPC payloads or authentication details in logs.
                    raise RuntimeError(f"Codex rejected {method}; check your local ChatGPT login")
                return message.get("result")

    try:
        request("initialize", {
            "clientInfo": {"name": "nancy_blog_usage", "title": "NanCy Blog Usage Sync", "version": "1.0.0"},
            "capabilities": {"experimentalApi": True},
        }, 0)
        send({"method": "initialized", "params": {}})
        account = request("account/read", {"refreshToken": False}, 1)
        if (account.get("account") or {}).get("type") != "chatgpt":
            raise RuntimeError("Sign in to the official Codex CLI with your ChatGPT account first")
        result = request("account/usage/read", {}, 2)
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        process.stdin.close()
        process.stdout.close()

    summary = result.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("The usage service did not return a summary")
    safe_summary = {key: statistic(summary.get(key)) for key in SUMMARY_FIELDS}
    buckets = result.get("dailyUsageBuckets")
    days = None
    if buckets is not None:
        if not isinstance(buckets, list):
            raise ValueError("Invalid daily activity")
        merged = {}
        for bucket in buckets:
            day = date.fromisoformat(bucket["startDate"]).isoformat()
            tokens = statistic(bucket.get("tokens"))
            if tokens is None:
                raise ValueError("Daily activity is missing token counts")
            merged[day] = statistic(merged.get(day, 0) + tokens)
        days = [{"startDate": day, "tokens": merged[day]} for day in sorted(merged)]
    return {
        "schemaVersion": 1,
        "updatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "OpenAI Codex account/usage/read",
        "summary": safe_summary,
        "dailyUsageBuckets": days,
    }


def git(*arguments, allow_changes=False):
    environment = os.environ.copy()
    environment.update(GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="Never")
    result = subprocess.run(
        ["git", *arguments], cwd=ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace", env=environment, timeout=90,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode and not allow_changes:
        raise RuntimeError(f"Git {arguments[0]} failed (exit {result.returncode}); no credentials logged")
    return result


@contextmanager
def sync_lock():
    path = Path(git("rev-parse", "--git-path", "nancy-usage-sync.lock").stdout.strip())
    if not path.is_absolute():
        path = ROOT / path
    with path.open("a+b") as handle:
        if not handle.tell():
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def publish(codex):
    with sync_lock():
        if git("status", "--porcelain").stdout.strip():
            raise RuntimeError("Sync checkout has local changes; refusing to overwrite or publish them")
        if git("branch", "--show-current").stdout.strip() != "main":
            raise RuntimeError("Sync checkout must be on main")
        git("pull", "--ff-only", "origin", "main")
        snapshot = collect(codex)
        previous = json.loads((ROOT / "gpt-usage.json").read_text(encoding="utf-8"))
        unchanged = all(snapshot[key] == previous.get(key) for key in ("summary", "dailyUsageBuckets"))
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(previous["updatedAt"])).total_seconds()
        if unchanged and age < 3600:
            logging.info("No new activity; recent public snapshot retained")
            # A previous interrupted push may have left a clean local commit ahead.
            git("-c", "http.postBuffer=5242880", "-c", "http.version=HTTP/1.1", "push", "origin", "main")
            return
        write_snapshot(snapshot)
        git("add", "--", "gpt-usage.json")
        git("commit", "-m", "Update GPT usage snapshot", "--", "gpt-usage.json")
        git("-c", "http.postBuffer=5242880", "-c", "http.version=HTTP/1.1", "push", "origin", "main")
        logging.info("Published a public usage snapshot")


def write_snapshot(snapshot):
    target = ROOT / "gpt-usage.json"
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--codex")
    args = parser.parse_args()
    log_path = Path(git("rev-parse", "--git-path", "gpt-usage-sync.log").stdout.strip())
    if not log_path.is_absolute():
        log_path = ROOT / log_path
    logging.basicConfig(handlers=[RotatingFileHandler(log_path, maxBytes=500000, backupCount=1, encoding="utf-8")], level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        codex = find_codex(args.codex)
        if args.publish:
            publish(codex)
        else:
            write_snapshot(collect(codex))
            logging.info("Collected public usage snapshot locally")
    except Exception as error:
        logging.error("Sync failed: %s", error)
        if sys.stderr is not None:
            print(f"Usage sync failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
