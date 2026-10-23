"""Send the Yelo mail reminder to the configured Telegram group."""

import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
MESSAGE = "Mail-lərinizi yoxlayın."


def main() -> int:
    if not BOT_TOKEN:
        print("Missing TELEGRAM_BOT_TOKEN.", file=sys.stderr)
        return 2
    if not CHAT_ID:
        print("Missing TELEGRAM_CHAT_ID.", file=sys.stderr)
        return 2

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = json.dumps({"chat_id": CHAT_ID, "text": MESSAGE}).encode("utf-8")
    request = Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=20) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
        # Never print the request URL because it contains the bot token.
        print("Telegram did not accept the reminder. Check the bot and chat settings.", file=sys.stderr)
        return 1

    if not result.get("ok"):
        print("Telegram returned an error while sending the reminder.", file=sys.stderr)
        return 1

    print("Reminder sent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
