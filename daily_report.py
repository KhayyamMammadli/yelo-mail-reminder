"""Post the daily mail-confirmation report to the Telegram group."""

import hashlib
import html
import hmac
import io
import json
import os
import sys
import urllib.error
import urllib.request
import zipfile
from datetime import datetime
from zoneinfo import ZoneInfo

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
MEMBERS_JSON = os.environ.get("TELEGRAM_GROUP_MEMBERS", "").strip()
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
GITHUB_REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "").strip()
WORKFLOW_PATH = ".github/workflows/reminders.yml"
TIMEZONE = ZoneInfo("Asia/Baku")
EXEMPT_NAMES = {
    "emin khalilov",
    "marta rzayeva",
    "rahim",
    "behbudov",
    "javidan",
}


def normalized_name(value: str) -> str:
    return " ".join(value.casefold().split())


def load_members() -> list[dict]:
    if not MEMBERS_JSON:
        raise RuntimeError(
            "Set TELEGRAM_GROUP_MEMBERS to a JSON roster of group member IDs and names."
        )
    try:
        raw_members = json.loads(MEMBERS_JSON)
        members = []
        seen = set()
        for item in raw_members:
            user_id = int(item["id"])
            name = str(item["name"]).strip()
            if (
                user_id not in seen
                and name
                and normalized_name(name) not in EXEMPT_NAMES
            ):
                members.append({"id": user_id, "name": name})
                seen.add(user_id)
    except (json.JSONDecodeError, TypeError, KeyError, ValueError) as exc:
        raise RuntimeError(
            "TELEGRAM_GROUP_MEMBERS must be a JSON list of {id, name} objects."
        ) from exc
    if not members:
        raise RuntimeError("The required member roster is empty after exclusions.")
    return members


def github_request(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            return response.read()
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        # Do not print request headers or URLs that may carry authorization data.
        raise RuntimeError("Could not read today's private confirmation records.") from exc


def github_json(path: str) -> dict:
    url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}{path}"
    try:
        return json.loads(github_request(url).decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError("GitHub returned invalid JSON for confirmation records.") from exc


def local_date_for_run(run: dict) -> str | None:
    try:
        created = datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))
    except (KeyError, ValueError):
        return None
    return created.astimezone(TIMEZONE).date().isoformat()


def today_confirmation_hashes(today: str) -> tuple[set[str], int]:
    if not GITHUB_TOKEN or not GITHUB_REPOSITORY or "/" not in GITHUB_REPOSITORY:
        raise RuntimeError("GitHub Actions read access is not configured.")
    data = github_json("/actions/runs?per_page=100")
    runs = data.get("workflow_runs", [])
    current_run_id = os.environ.get("GITHUB_RUN_ID", "")
    today_runs = [
        run
        for run in runs
        if run.get("path") == WORKFLOW_PATH
        and run.get("head_branch") == "main"
        and run.get("event") in {"schedule", "workflow_dispatch"}
        and str(run.get("id")) != current_run_id
        and local_date_for_run(run) == today
    ]
    hashes: set[str] = set()
    records_found = 0
    missing_records = []
    for run in today_runs:
        if run.get("status") != "completed" or run.get("conclusion") != "success":
            missing_records.append(str(run.get("run_number", run.get("id"))))
            continue
        artifacts = github_json(f"/actions/runs/{run['id']}/artifacts").get(
            "artifacts", []
        )
        record_artifact = next(
            (
                item
                for item in artifacts
                if item.get("name") == f"confirmation-record-{run['id']}"
                and not item.get("expired")
            ),
            None,
        )
        if not record_artifact:
            missing_records.append(str(run.get("run_number", run.get("id"))))
            continue
        archive = github_request(
            f"https://api.github.com/repos/{GITHUB_REPOSITORY}"
            f"/actions/artifacts/{record_artifact['id']}/zip"
        )
        try:
            with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
                raw = zipped.read("confirmation-record.json")
                record = json.loads(raw.decode("utf-8"))
        except (zipfile.BadZipFile, KeyError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise RuntimeError("A confirmation record could not be read.") from exc
        if record.get("date") != today:
            continue
        hashes.update(str(item) for item in record.get("confirmed_hashes", []))
        records_found += 1
    if missing_records:
        raise RuntimeError(
            "Daily report cancelled because reminder run(s) lack a complete record: "
            + ", ".join(missing_records)
        )
    return hashes, records_found


def user_hash(user_id: int) -> str:
    return hmac.new(
        BOT_TOKEN.encode("utf-8"),
        str(user_id).encode("ascii"),
        hashlib.sha256,
    ).hexdigest()


def mention(member: dict) -> str:
    safe_name = html.escape(member["name"])
    return f'<a href="tg://user?id={member["id"]}">{safe_name}</a>'


def telegram_api(method: str, payload: dict) -> dict:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError("Telegram API request failed while sending the report.") from exc
    if not result.get("ok"):
        raise RuntimeError(f"Telegram API rejected {method}.")
    return result


def send_report(confirmed: list[dict], unconfirmed: list[dict], today: str) -> None:
    day_label = datetime.fromisoformat(today).strftime("%d.%m.%Y")
    telegram_api(
        "sendMessage",
        {
            "chat_id": CHAT_ID,
            "text": f"<b>📊 Günlük e-poçt hesabatı — {day_label}</b>\n"
            "<i>İstisna olunan əməkdaşlar hesabata daxil edilməyib.</i>",
            "parse_mode": "HTML",
        },
    )
    for label, emoji, members in (
        ("Təsdiqləyib", "✅", confirmed),
        ("Təsdiqləməyib", "❌", unconfirmed),
    ):
        heading = f"{emoji} <b>{label}: {len(members)} nəfər</b>\n"
        names = [mention(member) for member in members]
        if not names:
            telegram_api(
                "sendMessage",
                {
                    "chat_id": CHAT_ID,
                    "text": heading + "Heç kim",
                    "parse_mode": "HTML",
                },
            )
            continue
        # Keep every Telegram message under the 4096-character limit and
        # never split an HTML mention across messages.
        chunk = heading
        for name in names:
            separator = ", " if chunk != heading else ""
            if len(chunk) + len(separator) + len(name) > 3500:
                telegram_api(
                    "sendMessage",
                    {
                        "chat_id": CHAT_ID,
                        "text": chunk,
                        "parse_mode": "HTML",
                    },
                )
                chunk = f"{heading}(davamı)\n"
                separator = ""
            chunk += separator + name
        if chunk:
            telegram_api(
                "sendMessage",
                {"chat_id": CHAT_ID, "text": chunk, "parse_mode": "HTML"},
            )


def main() -> int:
    if not BOT_TOKEN or not CHAT_ID:
        print("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID.", file=sys.stderr)
        return 2
    try:
        members = load_members()
        today = datetime.now(TIMEZONE).date().isoformat()
        hashes, records_found = today_confirmation_hashes(today)
        if not records_found:
            raise RuntimeError(
                "No completed reminder confirmation records were found for today."
            )
        confirmed = [member for member in members if user_hash(member["id"]) in hashes]
        unconfirmed = [member for member in members if user_hash(member["id"]) not in hashes]
        send_report(confirmed, unconfirmed, today)
        print(
            f"Daily report sent. Confirmed: {len(confirmed)}; "
            f"unconfirmed: {len(unconfirmed)}; records: {records_found}."
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
