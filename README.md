# Yelo Mail Reminder Bot

## GitHub Actions schedule

The active scheduler is GitHub Actions. On weekdays, it is configured for Baku time (UTC+4):

- 12:00 — email reminder
- 13:00 — email reminder
- 14:00 — email reminder
- 14:30 — end-of-day confirmation report

The first three runs collect button confirmations for 15 minutes. If required confirmations are still missing, the bot posts a follow-up and repeats the reminder. Saturdays and Sundays are excluded.

GitHub-hosted schedules are best-effort and can start late during platform load. The workflow retries transient Telegram API failures and keeps partial confirmation records so the 14:30 report can still be sent with an incomplete-data warning.

## GitHub Actions secrets

Configure these at **Repository → Settings → Secrets and variables → Actions**:

- `TELEGRAM_BOT_TOKEN` — current token from BotFather
- `TELEGRAM_CHAT_ID` — numeric ID of the target group
- `TELEGRAM_GROUP_MEMBERS` — optional JSON roster of required members, for example:
  ```json
  [{"id": 123456789, "name": "Employee Name"}]
  ```

Without `TELEGRAM_GROUP_MEMBERS`, the bot still posts the scheduled reminders and the 14:30 report includes counts only. The names of non-confirmers and individual mentions require the full roster. Keep the roster in GitHub Secrets; do not commit it to the repository.

The following display names are treated as exempt from confirmation: Emin Khalilov, Marta Rzayeva, Rahim, Behbudov, and Javidan.

## Run manually

Open **Actions → Yelo mail reminders → Run workflow** to send a test reminder immediately. A manual run is separate from the weekday schedule.
