# Yelo Mail Reminder Bot

## Render schedule

The Render Cron Blueprint in `render.yaml` starts one weekday run at **09:30 Baku time** (05:30 UTC). That process stays active through the workday, sends reminders at **09:30, 14:30, and 16:30**, collects confirmations, then posts the **18:30** report and exits.

The report includes counts and names for confirmed and unconfirmed required members. It excludes these Telegram display names: Emin Khalilov, Marta Rzayeva, Rahim, Behbudov, and Javidan. The job keeps confirmation state in memory for that single workday; it does not need a database or a persistent disk. Render stops cron runs after 12 hours; this process normally runs about 9 hours.

Render cron schedules use UTC. The lowest cron plan is `0.5c-512mb` in Frankfurt. Render bills cron jobs by active time, with a $1/month minimum per cron service.

## Required Render environment variables

When creating the Blueprint, Render prompts for these values:

- `TELEGRAM_BOT_TOKEN` — the current token from BotFather
- `TELEGRAM_CHAT_ID` — the numeric ID of the target group
- `TELEGRAM_GROUP_MEMBERS` — a JSON list of every required group member's Telegram numeric ID and display name, for example:
  ```json
  [{"id": 123456789, "name": "Employee Name"}]
  ```

Telegram's Bot API cannot provide the complete group-member list. The roster is needed to identify people who did not confirm. The five exempt names are filtered out automatically. Keep the roster in Render's environment settings; do not commit it or put it in this repository.

## Deploy

Open the Render Blueprint page for this repository and apply `render.yaml`:

https://dashboard.render.com/blueprint/new?repo=https://github.com/KhayyamMammadli/yelo-mail-reminder

After the Render Cron service has been deployed and its first run verified, disable the GitHub Actions schedule to prevent duplicate messages.
