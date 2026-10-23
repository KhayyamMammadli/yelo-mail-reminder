"""Collect group members who send /qeydiyyat and print their JSON roster."""

import getpass
import json
import sys
import time
from urllib.parse import urlencode
from urllib.request import urlopen

BOT_USERNAME = "YeloMailXatirlatmaBot"
COLLECTION_SECONDS = 300


def main() -> int:
    token = getpass.getpass("Bot token (hidden): ").strip()
    chat_id = input("Telegram group chat ID: ").strip()
    if not token or not chat_id:
        print("Bot token and group chat ID are required.", file=sys.stderr)
        return 2

    offset = None
    members = {}
    deadline = time.monotonic() + COLLECTION_SECONDS
    print(
        "Now ask each group member to send "
        f"/qeydiyyat@{BOT_USERNAME} in the group. Listening for 5 minutes..."
    )

    while time.monotonic() < deadline:
        timeout = max(1, min(20, int(deadline - time.monotonic())))
        params = {
            "timeout": timeout,
            "allowed_updates": json.dumps(["message"]),
        }
        if offset is not None:
            params["offset"] = offset
        url = f"https://api.telegram.org/bot{token}/getUpdates?{urlencode(params)}"
        try:
            with urlopen(url, timeout=timeout + 10) as response:
                result = json.loads(response.read().decode("utf-8"))
        except Exception:
            print("Could not read Telegram updates. Check the token and try again.", file=sys.stderr)
            return 1

        if not result.get("ok"):
            print("Telegram returned an error. Check the token and try again.", file=sys.stderr)
            return 1

        for update in result.get("result", []):
            offset = update["update_id"] + 1
            message = update.get("message") or {}
            chat = message.get("chat") or {}
            text = message.get("text") or ""
            command = text.split(maxsplit=1)[0].split("@")[0] if text else ""
            user = message.get("from") or {}
            user_id = user.get("id")
            if (
                str(chat.get("id")) != chat_id
                or command != "/qeydiyyat"
                or not user_id
                or user.get("is_bot")
            ):
                continue

            name = " ".join(
                part for part in (user.get("first_name"), user.get("last_name")) if part
            ) or user.get("username")
            members[str(user_id)] = {"id": user_id, "name": name}
            print(f"Registered: {name} ({user_id})")

    roster = list(members.values())
    if not roster:
        print("No members registered. Run this helper again and retry.", file=sys.stderr)
        return 1

    print("\nCopy this JSON into the GitHub TELEGRAM_GROUP_MEMBERS secret:")
    print(json.dumps(roster, ensure_ascii=False))
    print(f"\nCollected {len(roster)} member(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
