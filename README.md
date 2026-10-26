# Yelo Mail Reminder Bot

The GitHub Actions workflow sends the corporate email reminder to the configured Telegram group on weekdays at **09:30, 14:30, and 16:30 Baku time**. At **18:30**, it posts a daily report with confirmation counts and the names of confirmed and unconfirmed required members. The report excludes the following Telegram display names: Emin Khalilov, Marta Rzayeva, Rahim, Behbudov, and Javidan.

The report combines confirmation records from the day's reminder runs. Each reminder run listens for confirmations for up to 30 minutes and saves only HMAC-protected user identifiers in a short-lived GitHub Actions artifact; employee names and Telegram IDs are not put in the artifact or workflow logs.

## GitHub Actions secrets

Open **Settings → Secrets and variables → Actions → New repository secret** and configure:

- `TELEGRAM_BOT_TOKEN` — the current token from BotFather
- `TELEGRAM_CHAT_ID` — the numeric ID of the target group
- `TELEGRAM_GROUP_MEMBERS` — a JSON list containing every required group member's Telegram numeric ID and display name, for example:
  ```json
  [{"id": 123456789, "name": "Employee Name"}]
  ```

Telegram's Bot API does not provide a complete group member list. The roster is needed to name the people who did not confirm; without it, the daily report cannot be generated. Keep the roster current when group membership changes. The five exempt names are filtered out automatically.

Do not put tokens, the group roster, or other private data in repository files or chat messages.

## Schedule

The schedule uses UTC cron times to match Baku time (UTC+4):

- 09:30 Baku — 05:30 UTC
- 14:30 Baku — 10:30 UTC
- 16:30 Baku — 12:30 UTC
- 18:30 Baku — 14:30 UTC (daily report)

GitHub Actions scheduled events can be delayed or dropped during periods of high load. Check the workflow run history if a message does not arrive.

## Manual test

Use **Actions → Yelo mail reminders → Run workflow**. A manual run sends a real reminder to the configured group and can take up to 30 minutes to finish. It also saves that run's confirmation record for the day's report.
