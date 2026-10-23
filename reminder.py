"""Send a corporate mail reminder and collect acknowledgements for 15 minutes."""

import html
import json
import os
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
MEMBERS_JSON = os.environ.get("TELEGRAM_GROUP_MEMBERS", "").strip()
ACK_SECONDS = 15 * 60
ACK_DATA = "mail_checked"
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


def api(method: str, payload: dict, timeout: int = 25) -> dict:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    request = Request(
        url,
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
    return members


def mention(user: dict) -> str:
    safe_name = html.escape(user["name"])
    return f'<a href="tg://user?id={user["id"]}">{safe_name}</a>'


def send_reminder(members: list[dict]) -> int:
    tags = ", ".join(mention(member) for member in members)
    text = (
        "<b>Hörmətli həmkarlar,</b>\n\n"
        "Xahiş edirik, elektron poçt qutularınızı yoxlayasınız. "
        "Yoxladıqdan sonra aşağıdakı düymə vasitəsilə təsdiq etməyiniz xahiş olunur."
    )
    if tags:
        text += f"\n\n{tags}"
    text += "\n\n<i>Təşəkkür edirik.</i>"

    result = api(
        "sendMessage",
        {
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "reply_markup": {
                "inline_keyboard": [[{"text": "✅ Təsdiq edirəm", "callback_data": ACK_DATA}]]
            },
        },
    )
    return result["result"]["message_id"]


def acknowledge(query: dict, message_ids: set[int], confirmed: set[int]) -> None:
    user = query.get("from") or {}
    user_id = user.get("id")
    message = query.get("message") or {}
    if (
        not user_id
        or str((message.get("chat") or {}).get("id")) != CHAT_ID
        or message.get("message_id") not in message_ids
        or query.get("data") != ACK_DATA
    ):
        api("answerCallbackQuery", {"callback_query_id": query["id"]})
        return

    name = callback_user_name(user)
    if normalized_name(name) in EXEMPT_NAMES:
        api(
            "answerCallbackQuery",
            {
                "callback_query_id": query["id"],
                "text": "Sizin təsdiqiniz tələb olunmur.",
            },
        )
        return

    if user_id in confirmed:
        api(
            "answerCallbackQuery",
            {
                "callback_query_id": query["id"],
                "text": "Təsdiqiniz artıq qeydə alınıb.",
            },
        )
        return

    confirmed.add(user_id)
    api(
        "answerCallbackQuery",
        {
            "callback_query_id": query["id"],
            "text": "Təsdiqiniz qeydə alındı. Təşəkkür edirik.",
        },
    )
    name = name or f"İstifadəçi {user_id}"
    api(
        "sendMessage",
        {
            "chat_id": CHAT_ID,
            "text": f"✅ {mention({'id': user_id, 'name': name})} e-poçtunu yoxladığını təsdiqlədi. Təşəkkür edirik.",
            "parse_mode": "HTML",
            "reply_to_message_id": message.get("message_id"),
        },
    )

def collect_confirmations(
    message_ids: set[int], confirmed: set[int] | None = None
) -> set[int]:
    if confirmed is None:
        confirmed = set()
    offset = None
    deadline = time.monotonic() + ACK_SECONDS
    print("Waiting 15 minutes for group confirmations.")
    while time.monotonic() < deadline:
        wait_seconds = max(1, min(15, int(deadline - time.monotonic())))
        payload = {"timeout": wait_seconds, "allowed_updates": ["callback_query"]}
        if offset is not None:
            payload["offset"] = offset
        result = api("getUpdates", payload, timeout=wait_seconds + 10)
        for update in result.get("result", []):
            offset = update["update_id"] + 1
            query = update.get("callback_query")
            if query:
                acknowledge(query, message_ids, confirmed)
    return confirmed

def remind_unconfirmed(members: list[dict], confirmed: set[int]) -> bool:
    # Telegram returns a total group count, but not a full member list.
    # The count includes this bot, so exclude it before checking confirmations.
    member_count = int(api("getChatMemberCount", {"chat_id": CHAT_ID})["result"])
    expected_confirmations = max(0, member_count - 1 - len(EXEMPT_NAMES))
    if len(confirmed) >= expected_confirmations:
        print("All required group members confirmed; no 15-minute follow-up sent.")
        return False

    warning = (
        "⏰ İlkin bildirişdən 15 dəqiqə keçib. E-poçtunu yoxlayıb təsdiq "
        "düyməsinə basmayan əməkdaşlardan xahiş olunur bunu indi etsinlər."
    )
    pending = [member for member in members if member["id"] not in confirmed]
    if pending:
        warning += "\n\nTəsdiq etməyənlər: " + ", ".join(
            mention(member) for member in pending
        )

    api(
        "sendMessage",
        {"chat_id": CHAT_ID, "text": warning, "parse_mode": "HTML"},
    )
    return True

def main() -> int:
    if not BOT_TOKEN or not CHAT_ID:
        print("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID.", file=sys.stderr)
        return 2

    try:
        members = load_members()
        message_id = send_reminder(members)
        print("Corporate reminder sent.")
        confirmed = collect_confirmations({message_id})
        if remind_unconfirmed(members, confirmed):
            repeated_message_id = send_reminder(members)
            print("Repeated corporate reminder sent with its confirmation button.")
            confirmed = collect_confirmations(
                {message_id, repeated_message_id}, confirmed
            )
        print(f"Confirmation windows closed. Confirmed: {len(confirmed)}.")
        if not members:
            print("No member roster configured; group-count check was used.")
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
