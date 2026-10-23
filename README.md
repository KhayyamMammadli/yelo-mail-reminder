# Yelo Mail Reminder Bot

This repository sends **“Mail-lərinizi yoxlayın.”** to the configured Telegram group every day at **14:30, 16:30, and 17:00** in the `Asia/Baku` time zone.

## GitHub Actions setup

In the repository, open **Settings → Secrets and variables → Actions** and add:

- `TELEGRAM_BOT_TOKEN` — the newly rotated token from BotFather
- `TELEGRAM_CHAT_ID` — the numeric ID of the group

Do not commit either value to this repository.

To get the group ID, send `/chatid@YeloMailXatirlatmaBot` in the group, then run `python3 get_chat_id.py` in a terminal. The helper prompts for the bot token without displaying it and prints the group ID. Add that ID as the `TELEGRAM_CHAT_ID` repository secret.

After adding both secrets, use **Actions → Yelo mail reminders → Run workflow** to test a message. Scheduled runs are enabled by the workflow file on the default branch.
