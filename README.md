# Yelo Mail Reminder Bot

This repository sends a corporate mail reminder to the configured Telegram group on weekdays (Monday to Friday) at **09:30, 14:30, and 16:30** in the `Asia/Baku` time zone. The message includes a **“✅ Təsdiq edirəm”** button. Each click is acknowledged in the group.

After 15 minutes, the bot sends a follow-up only if confirmations are fewer than the group member count, excluding this bot. If everyone has confirmed, no follow-up message is sent. Telegram's Bot API provides the group count but not a complete member list; additional bots in the group can make this count-based check inaccurate.

## GitHub Actions setup

In the repository, open **Settings → Secrets and variables → Actions** and add:

- `TELEGRAM_BOT_TOKEN` — the newly rotated token from BotFather
- `TELEGRAM_CHAT_ID` — the numeric ID of the group

Do not commit either value to this repository.

## Confirmation and member tagging

Members can confirm with the button; the bot replies in the group with the confirmer's name. Telegram's Bot API does not provide a full group member list. If `TELEGRAM_GROUP_MEMBERS` is configured as a JSON list of `{"id": 123, "name": "Name"}` entries, the bot can tag those listed members in the reminder and follow-up. The list must be maintained when membership changes. Without it, the bot sends an untargeted follow-up only when confirmations are incomplete.

## Test

Use **Actions → Yelo mail reminders → Run workflow**. This sends a real group message and keeps the workflow active for up to 15 minutes to collect confirmations. Coordinate the manual test with the group before running it.
