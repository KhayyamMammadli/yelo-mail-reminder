# Yelo Mail Reminder Bot

This repository sends a corporate mail reminder to the configured Telegram group on weekdays (Monday to Friday) at **09:30, 14:30, and 16:30** in the `Asia/Baku` time zone. The message includes a **“✅ Təsdiq edirəm”** button. Each click is acknowledged in the group.

After 15 minutes, the bot checks the confirmations. If everyone has confirmed, it sends no follow-up. If confirmations are incomplete, it posts the 15-minute warning and sends the original corporate reminder again with a working confirmation button. The workflow stays active for a further 15 minutes to accept confirmations to either reminder.

Telegram's Bot API provides the group count but not a complete member list; additional bots in the group can make the count-based all-confirmed check inaccurate.

## GitHub Actions setup

In the repository, open **Settings → Secrets and variables → Actions** and add:

- `TELEGRAM_BOT_TOKEN` — the newly rotated token from BotFather
- `TELEGRAM_CHAT_ID` — the numeric ID of the group

Do not commit either value to this repository.

## Confirmation and member tagging

Members can confirm with the button; the bot replies in the group with the confirmer's name. Telegram's Bot API does not provide a full group member list. If `TELEGRAM_GROUP_MEMBERS` is configured as a JSON list of `{"id": 123, "name": "Name"}` entries, the bot can tag those listed members in reminders and follow-ups. The list must be maintained when membership changes. Without it, the bot sends an untargeted follow-up only when confirmations are incomplete.

## Test

Use **Actions → Yelo mail reminders → Run workflow**. This sends real group messages and can keep the workflow active for up to 30 minutes. Coordinate the manual test with the group before running it.
