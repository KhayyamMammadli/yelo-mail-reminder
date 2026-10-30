# Yelo Mail Reminder Bot

## Automatic weekday reminders

Render Cron is configured to start one process at 11:30 Baku time (07:30 UTC), Monday to Friday. It sends reminders at:

- 11:30
- 12:00
- 12:00

The two 12:00 slots each send a separate reminder. The process finishes at 12:30 Baku time.

If a reminder has unconfirmed required employees after 15 minutes, the bot sends a follow-up and repeats the confirmation message. There is no daily report.

The single daily process handles all three slots, so delayed schedule events cannot pile up as separate runs. Slots more than five minutes late are skipped instead of sent in a burst.

## Render environment variables

Add these in the Render service's **Environment** settings:

- `TELEGRAM_BOT_TOKEN` — current token from BotFather
- `TELEGRAM_CHAT_ID` — numeric ID of the target group
- `TELEGRAM_GROUP_MEMBERS` — optional JSON list of required members, e.g.
  ```json
  [{"id": 123456789, "name": "Employee Name"}]
  ```

Without `TELEGRAM_GROUP_MEMBERS`, reminders and confirmation buttons still work, but the bot cannot tag each unconfirmed employee by name. Keep the roster in Render Secrets; do not commit it to the repository.

The following display names are treated as exempt from confirmation: Emin Khalilov, Marta Rzayeva, Rahim, Behbudov, and Javidan.

Render schedules use UTC. A Cron job is billed while running and has a $1/month minimum.
