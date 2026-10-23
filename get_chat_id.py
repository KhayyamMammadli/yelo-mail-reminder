"""Read a /chatid command and print the Telegram group chat ID."""

import getpass
import json
import os
from urllib.parse import urlencode
from urllib.request import urlopen


def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        token = getpass.getpass("Paste the new bot token (input is hidden): ").strip()
    if not token:
        raise SystemExit("A bot token is required.")

    query = urlencode({"timeout": 30, "allowed_updates": json.dumps(["message"])})
    url = f"https://api.telegram.org/bot{token}/getUpdates?{query}"
    print("Now send /chatid@YeloMailXatirlatmaBot in the target group.")
    print("Waiting up to 30 seconds for that command...")

    try:
        with urlopen(url, timeout=35) as response:
            result = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise SystemExit("Could not read Telegram updates. Check the token and try again.") from exc

    if not result.get("ok"):
        raise SystemExit("Telegram returned an error. Check the token and try again.")

    matches = []
    for update in result.get("result", []):
        message = update.get("message") or update.get("channel_post") or {}
        text = (message.get("text") or "").split()[0].split("@")[0]
        chat = message.get("chat") or {}
        if text == "/chatid" and chat.get("type") in {"group", "supergroup"}:
            matches.append((chat.get("id"), chat.get("title", "Telegram group")))

    if not matches:
        raise SystemExit("No /chatid command was found. Send it in the group and run this helper again.")

    chat_id, title = matches[-1]
    print(f"Group: {title}")
    print(f"TELEGRAM_CHAT_ID: {chat_id}")


if __name__ == "__main__":
    main()
