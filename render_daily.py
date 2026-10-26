"""Run Yelo mail reminders and the daily report in one Render Cron invocation."""

import html
import json
import os
import sys
import time
from datetime import datetime, time as clock_time, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
MEMBERS_JSON = os.environ.get("TELEGRAM_GROUP_MEMBERS", "").strip()
BAKU = timezone(timedelta(hours=4), name="Asia/Baku")
ACK_SECONDS = 15 * 60
ACK_DATA = "mail_checked"
REMINDER_TIMES = (
    clock_time(9, 30),
    clock_time(14, 30),
    clock_time(16, 30),
)
REPORT_TIME = clock_time(18, 30)
EXEMPT_NAMES = {
    "emin khalilov",
    "marta rzayeva",
    "rahim",
    "behbudov",
    "javidan",
}


def normalized_name(value: str) -> str:
    return " ".join(value.casefold().split())


def callback_user_name(user: dict) -> str:
    return " ".join(
        part for part in (user.get("first_name"), user.get("last_name")) if part
    ) or user.get("username") or ""


def load_members() -> list[dict]:
    if not MEMBERS_JSON:
        raise RuntimeError(
            "TELEGRAM_GROUP_MEMBERS is required for confirmation and daily reports."
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


def api(method: str, payload: dict, timeout: int = 30) -> dict:
    request = Request(
        f"https://api.telegram.org/bot{BOT_TOKEN}/{method}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        # Never print the request URL because it contains the bot token.
        raise RuntimeError("Telegram API request failed.") from exc
    if not result.get("ok"):
        raise RuntimeError(f"Telegram API rejected {method}.")
    return result


def mention(member: dict) -> str:
    return (
        f'<a href="tg://user?id={member["id"]}">'
        f'{html.escape(member["name"])}</a>'
    )


def send_text(text: str) -> int:
    result = api(
        "sendMessage",
        {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"},
    )
    return int(result["result"]["message_id"])


def send_mentions(title: str, members: list[dict]) -> None:
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


def send_reminder(members: list[dict]) -> int:
    text = (
        "<b>Hörmətli həmkarlar,</b>\n\n"
        "Xahiş edirik, elektron poçt qutularınızı yoxlayasınız. "
        "Yoxladıqdan sonra aşağıdakı düymə vasitəsilə təsdiq etməyiniz xahiş olunur.\n\n"
        "<i>Təşəkkür edirik.</i>"
    )
    result = api(
        "sendMessage",
        {
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "reply_markup": {
                "inline_keyboard": [
                    [{"text": "✅ Təsdiq edirəm", "callback_data": ACK_DATA}]
                ]
            },
        },
    )
    message_id = int(result["result"]["message_id"])
    send_mentions("Təsdiq etməli əməkdaşlar:", members)
    return message_id


class DailyReminder:
    def __init__(self, members: list[dict]):
        self.members = members
        self.members_by_id = {member["id"]: member for member in members}
        self.confirmed: dict[int, str] = {}
        self.message_ids: set[int] = set()
        self.offset: int | None = None

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

        callback_name = callback_user_name(user)
        if normalized_name(callback_name) in EXEMPT_NAMES:
            api(
                "answerCallbackQuery",
                {
                    "callback_query_id": query["id"],
                    "text": "Sizin təsdiqiniz tələb olunmur.",
                },
            )
            return

        member = self.members_by_id.get(int(user_id))
        if not member:
            api(
                "answerCallbackQuery",
                {
                    "callback_query_id": query["id"],
                    "text": "Adınız təsdiq siyahısında tapılmadı.",
                },
            )
            return

        if int(user_id) in self.confirmed:
            api(
                "answerCallbackQuery",
                {
                    "callback_query_id": query["id"],
                    "text": "Təsdiqiniz artıq qeydə alınıb.",
                },
            )
            return

        self.confirmed[int(user_id)] = member["name"]
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
                "text": f"✅ {mention(member)} e-poçtunu yoxladığını təsdiqlədi. Təşəkkür edirik.",
                "parse_mode": "HTML",
                "reply_to_message_id": message_id,
            },
        )

    def poll_once(self, max_wait: int = 25) -> None:
        payload = {"timeout": max_wait, "allowed_updates": ["callback_query"]}
        if self.offset is not None:
            payload["offset"] = self.offset
        result = api("getUpdates", payload, timeout=max_wait + 10)
        for update in result.get("result", []):
            self.offset = int(update["update_id"]) + 1
            query = update.get("callback_query")
            if query:
                self.process_callback(query)

    def poll_for(self, seconds: int) -> None:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            remaining = int(deadline - time.monotonic())
            if remaining < 1:
                break
            self.poll_once(min(25, remaining))

    def wait_until(self, target: datetime) -> None:
        while True:
            remaining = (target - datetime.now(BAKU)).total_seconds()
            if remaining <= 0:
                return
            self.poll_once(max(1, min(25, int(remaining))))

    def run_reminder(self, slot_label: str) -> None:
        message_id = send_reminder(self.members)
        self.message_ids.add(message_id)
        print(f"Reminder sent for {slot_label}.")
        self.poll_for(ACK_SECONDS)

        pending = [
            member for member in self.members
            if member["id"] not in self.confirmed
        ]
        if not pending:
            print("All required members confirmed; no follow-up sent.")
            return

        warning = (
            "⏰ İlkin bildirişdən 15 dəqiqə keçib. E-poçtunu yoxlayıb təsdiq "
            "düyməsinə basmayan əməkdaşlardan xahiş olunur bunu indi etsinlər."
        )
        send_text(warning)
        send_mentions("Təsdiq etməyənlər:", pending)
        repeated_message_id = send_reminder(pending)
        self.message_ids.add(repeated_message_id)
        print(f"Follow-up sent for {slot_label}.")
        self.poll_for(ACK_SECONDS)

    def send_daily_report(self, today: str) -> None:
        confirmed = [
            member for member in self.members
            if member["id"] in self.confirmed
        ]
        unconfirmed = [
            member for member in self.members
            if member["id"] not in self.confirmed
        ]
        day_label = datetime.fromisoformat(today).strftime("%d.%m.%Y")
        send_text(
            f"<b>📊 Günlük e-poçt hesabatı — {day_label}</b>\n"
            "<i>İstisna olunan əməkdaşlar hesaba daxil edilməyib.</i>"
        )
        send_mentions(f"✅ Təsdiqləyib: {len(confirmed)} nəfər", confirmed)
        if not confirmed:
            send_text("✅ Təsdiqləyib: 0 nəfər\nHeç kim")
        send_mentions(f"❌ Təsdiqləməyib: {len(unconfirmed)} nəfər", unconfirmed)
        if not unconfirmed:
            send_text("❌ Təsdiqləməyib: 0 nəfər\nHeç kim")
        print(
            f"Daily report sent. Confirmed: {len(confirmed)}; "
            f"unconfirmed: {len(unconfirmed)}."
        )


def main() -> int:
    if not BOT_TOKEN or not CHAT_ID:
        print("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID.", file=sys.stderr)
        return 2
    try:
        members = load_members()
        today = datetime.now(BAKU).date()
        if today.weekday() >= 5:
            print("Weekend; no reminders sent.")
            return 0

        now = datetime.now(BAKU)
        if now.time() >= REPORT_TIME:
            raise RuntimeError("Cron job started after the 18:30 report time.")

        schedule = [
            (clock_time(9, 30), "09:30"),
            (clock_time(14, 30), "14:30"),
            (clock_time(16, 30), "16:30"),
        ]
        if now.time() < clock_time(14, 30):
            first_slot = 0
        elif now.time() < clock_time(16, 30):
            first_slot = 1
        else:
            first_slot = 2

        bot = DailyReminder(members)
        for slot_time, label in schedule[first_slot:]:
            target = datetime.combine(today, slot_time, tzinfo=BAKU)
            bot.wait_until(target)
            bot.run_reminder(label)

        report_target = datetime.combine(today, REPORT_TIME, tzinfo=BAKU)
        bot.wait_until(report_target)
        bot.send_daily_report(today.isoformat())
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
