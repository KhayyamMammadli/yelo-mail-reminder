"""Run the Yelo group reminders on a single Render Cron process (Baku time)."""

import html
import json
import math
import os
import sys
import time
from datetime import datetime, time as clock_time, timedelta
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
MEMBERS_JSON = os.environ.get("TELEGRAM_GROUP_MEMBERS", "").strip()
BAKU = ZoneInfo("Asia/Baku")
ACK_SECONDS = 15 * 60
POLL_SECONDS = 20
SLOT_GRACE = timedelta(minutes=5)
ACK_DATA = "mail_checked"
REMINDER_SLOTS = (
    (clock_time(17, 0), "17:00"),
    (clock_time(17, 30), "17:30"),
    (clock_time(18, 0), "18:00"),
)
EXEMPT_NAMES = {
    "emin khalilov",
    "marta rzayeva",
    "rahim",
    "behbudov",
    "javidan",
}
FOLLOWUP_TEXT = (
    "⏰ İlkin bildirişdən 15 dəqiqə keçib. E-poçtunu yoxlayıb təsdiq "
    "düyməsinə basmayan əməkdaşlardan xahiş olunur bunu indi etsinlər."
)
REMINDER_TEXT = (
    "<b>Hörmətli həmkarlar,</b>\n\n"
    "Xahiş edirik, elektron poçt qutularınızı yoxlayasınız. "
    "Yoxladıqdan sonra aşağıdakı düymə vasitəsilə təsdiq etməyiniz xahiş olunur.\n\n"
    "<i>Təşəkkür edirik.</i>"
)


def normalized_name(value: str) -> str:
    return " ".join(value.casefold().split())


def is_exempt(value: str) -> bool:
    name = normalized_name(value)
    single_name_exemptions = {"rahim", "behbudov", "javidan"}
    return name in EXEMPT_NAMES or bool(set(name.split()) & single_name_exemptions)


def callback_user_name(user: dict) -> str:
    return " ".join(
        part for part in (user.get("first_name"), user.get("last_name")) if part
    ) or user.get("username") or ""


def load_members() -> list[dict]:
    if not MEMBERS_JSON:
        return []
    try:
        raw_members = json.loads(MEMBERS_JSON)
        members = []
        seen = set()
        for item in raw_members:
            user_id = int(item["id"])
            name = str(item["name"]).strip()
            if user_id not in seen and name and not is_exempt(name):
                members.append({"id": user_id, "name": name})
                seen.add(user_id)
    except (json.JSONDecodeError, TypeError, KeyError, ValueError) as exc:
        raise RuntimeError(
            "TELEGRAM_GROUP_MEMBERS must be a JSON list of {id, name} objects."
        ) from exc
    return members


def api(method: str, payload: dict, timeout: int = 30) -> dict:
    request = Request(
        f"https://api.telegram.org/bot{BOT_TOKEN}/{method}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    for attempt in range(3):
        try:
            with urlopen(request, timeout=timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            retryable = exc.code == 429 or exc.code >= 500
            if retryable and attempt < 2:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"Telegram API returned HTTP {exc.code} during {method}.") from exc
        except (URLError, TimeoutError) as exc:
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"Telegram network request failed during {method}.") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Telegram returned invalid JSON during {method}.") from exc

        if not result.get("ok"):
            code = result.get("error_code")
            if code in {429, 500, 502, 503, 504} and attempt < 2:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"Telegram API rejected {method} (code {code}).")
        return result

    raise RuntimeError(f"Telegram API request failed during {method}.")


def mention(member: dict) -> str:
    safe_name = html.escape(member["name"])
    return f'<a href="tg://user?id={member["id"]}">{safe_name}</a>'


def send_text(text: str) -> int:
    result = api(
        "sendMessage",
        {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"},
    )
    return int(result["result"]["message_id"])


class DailyReminder:
    def __init__(self, members: list[dict]):
        self.members = members
        self.members_by_id = {member["id"]: member for member in members}
        self.confirmed: dict[int, str] = {}
        self.message_ids: set[int] = set()
        self.offset: int | None = None
        if members:
            self.expected_confirmations = len(members)
        else:
            member_count = int(
                api("getChatMemberCount", {"chat_id": CHAT_ID})["result"]
            )
            human_count = max(0, member_count - 1)
            # Without a roster, Telegram does not expose which exempt users are
            # actually in the group. Keep at least one human as a required recipient.
            exempt_count = min(len(EXEMPT_NAMES), max(0, human_count - 1))
            self.expected_confirmations = human_count - exempt_count
        print(
            f"Confirmation target: {self.expected_confirmations}; "
            f"roster configured: {bool(members)}."
        )

    def send_mentions(self, title: str, members: list[dict]) -> None:
        if not members:
            return
        heading = html.escape(title) + "\n"
        chunk = heading
        for member in members:
            tag = mention(member)
            separator = ", " if chunk != heading else ""
            if len(chunk) + len(separator) + len(tag) > 3500:
                send_text(chunk)
                chunk = heading + "(davamı)\n"
                separator = ""
            chunk += separator + tag
        if chunk != heading:
            send_text(chunk)

    def send_reminder(self, tagged_members: list[dict]) -> int:
        result = api(
            "sendMessage",
            {
                "chat_id": CHAT_ID,
                "text": REMINDER_TEXT,
                "parse_mode": "HTML",
                "reply_markup": {
                    "inline_keyboard": [
                        [{"text": "✅ Təsdiq edirəm", "callback_data": ACK_DATA}]
                    ]
                },
            },
        )
        message_id = int(result["result"]["message_id"])
        self.send_mentions("Təsdiq etməli əməkdaşlar:", tagged_members)
        return message_id

    def all_required_confirmed(self) -> bool:
        return len(self.confirmed) >= self.expected_confirmations

    def send_followup(self, slot_label: str) -> None:
        if self.all_required_confirmed():
            print(f"All required members confirmed for {slot_label}; follow-up skipped.")
            return
        pending = [
            member for member in self.members
            if member["id"] not in self.confirmed
        ]
        warning = FOLLOWUP_TEXT
        if pending:
            warning += "\n\nTəsdiq etməyənlər: " + ", ".join(
                mention(member) for member in pending
            )
        send_text(warning)
        message_id = self.send_reminder(pending)
        self.message_ids.add(message_id)
        print(f"15-minute follow-up sent for {slot_label}.")

    def process_callback(self, query: dict) -> None:
        user = query.get("from") or {}
        user_id = user.get("id")
        message = query.get("message") or {}
        message_id = message.get("message_id")
        chat_id = str((message.get("chat") or {}).get("id"))
        valid = (
            user_id
            and chat_id == CHAT_ID
            and message_id in self.message_ids
            and query.get("data") == ACK_DATA
        )
        if not valid:
            api("answerCallbackQuery", {"callback_query_id": query["id"]})
            return

        user_id = int(user_id)
        name = callback_user_name(user)
        member = self.members_by_id.get(user_id)
        if self.members and not member:
            api(
                "answerCallbackQuery",
                {
                    "callback_query_id": query["id"],
                    "text": "Adınız təsdiq siyahısında tapılmadı.",
                },
            )
            return
        if member:
            name = member["name"]
        if is_exempt(name):
            api(
                "answerCallbackQuery",
                {
                    "callback_query_id": query["id"],
                    "text": "Sizin təsdiqiniz tələb olunmur.",
                },
            )
            return
        if user_id in self.confirmed:
            api(
                "answerCallbackQuery",
                {
                    "callback_query_id": query["id"],
                    "text": "Təsdiqiniz artıq qeydə alınıb.",
                },
            )
            return

        self.confirmed[user_id] = name or f"İstifadəçi {user_id}"
        api(
            "answerCallbackQuery",
            {
                "callback_query_id": query["id"],
                "text": "Təsdiqiniz qeydə alındı. Təşəkkür edirik.",
            },
        )
        api(
            "sendMessage",
            {
                "chat_id": CHAT_ID,
                "text": f"✅ {mention({'id': user_id, 'name': self.confirmed[user_id]})} "
                "e-poçtunu yoxladığını təsdiqlədi. Təşəkkür edirik.",
                "parse_mode": "HTML",
                "reply_to_message_id": message_id,
            },
        )

    def poll_once(self, max_wait: int = POLL_SECONDS) -> None:
        max_wait = max(1, min(POLL_SECONDS, int(max_wait)))
        payload = {"timeout": max_wait, "allowed_updates": ["callback_query"]}
        if self.offset is not None:
            payload["offset"] = self.offset
        result = api("getUpdates", payload, timeout=max_wait + 10)
        for update in result.get("result", []):
            self.offset = int(update["update_id"]) + 1
            query = update.get("callback_query")
            if query:
                self.process_callback(query)


def run_schedule(members: list[dict]) -> int:
    today = datetime.now(BAKU).date()
    if today.weekday() >= 5:
        print("Weekend; no reminders sent.")
        return 0

    bot = DailyReminder(members)
    slots = [
        (datetime.combine(today, slot, tzinfo=BAKU), label)
        for slot, label in REMINDER_SLOTS
    ]
    stop_at = datetime.combine(today, clock_time(18, 30), tzinfo=BAKU)
    sent_slots: set[str] = set()
    handled_followups: set[str] = set()
    followups: dict[str, datetime] = {}

    print("Render reminder schedule started.")
    while datetime.now(BAKU) < stop_at:
        now = datetime.now(BAKU)

        for slot_id, (target, label) in enumerate(slots):
            if slot_id in sent_slots or now < target:
                continue
            sent_slots.add(slot_id)
            if now - target > SLOT_GRACE:
                print(f"Skipped stale {label} slot; no late reminder sent.")
                continue
            message_id = bot.send_reminder(bot.members)
            bot.message_ids.add(message_id)
            followups[slot_id] = datetime.now(BAKU) + timedelta(seconds=ACK_SECONDS)
            print(f"Reminder sent for Baku {label}.")

        now = datetime.now(BAKU)
        for slot_id, due in list(followups.items()):
            if slot_id in handled_followups or now < due:
                continue
            handled_followups.add(slot_id)
            bot.send_followup(slots[slot_id][1])

        if now >= stop_at:
            break

        future_events = [
            target for slot_id, (target, _) in enumerate(slots)
            if slot_id not in sent_slots and target > now
        ]
        future_events.extend(
            due for slot_id, due in followups.items()
            if slot_id not in handled_followups and due > now
        )
        next_event = min(future_events, default=stop_at)
        wait = max(1, min(POLL_SECONDS, math.ceil((next_event - now).total_seconds())))
        bot.poll_once(wait)

    print(
        f"Reminder schedule finished. Confirmed: {len(bot.confirmed)}; "
        f"messages sent: {len(bot.message_ids)}. No daily report is sent."
    )
    return 0


def main() -> int:
    if not BOT_TOKEN or not CHAT_ID:
        print("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID.", file=sys.stderr)
        return 2
    try:
        members = load_members()
        return run_schedule(members)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
