# Yelo Mail Reminder Bot

This repository sends a corporate mail reminder to the configured Telegram group every day at **14:30, 16:30, and 17:00** in the `Asia/Baku` time zone. The message includes a **“✅ Təsdiq edirəm”** button. Each click is acknowledged in the group. After 15 minutes, the bot posts a follow-up reminder.

## GitHub Actions setup

In the repository, open **Settings → Secrets and variables → Actions** and add:

- `TELEGRAM_BOT_TOKEN` — the rotated token from BotFather
- `TELEGRAM_CHAT_ID` — the numeric ID of the group

Do not commit either value to this repository.

## Confirmation and member tagging

Members can confirm with the button; the bot replies in the group with the confirmer's name. Telegram's Bot API does not provide a full group member list. Without a member roster, the bot cannot identify or individually tag people who did not confirm, so the 15-minute follow-up goes to the whole group. If `TELEGRAM_GROUP_MEMBERS` is optionally configured as a JSON list of `{"id": 123, "name": "Name"}` entries, the bot can tag those listed members in the reminder and follow-up. The list must be maintained when membership changes.

## Test

Use **Actions → Yelo mail reminders → Run workflow**. This sends a real group message and keeps the workflow active for 15 minutes to collect confirmations, then posts the follow-up.
