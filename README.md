# Yelo Mail Reminder Bot

This repository sends a corporate mail reminder to the configured Telegram group every day at **14:30, 16:30, and 17:00** in the `Asia/Baku` time zone. The message tags registered members and includes a **“✅ Təsdiq edirəm”** button. Each click is acknowledged in the group. After 15 minutes, the bot tags registered members who have not confirmed.

## Register group members

Telegram's Bot API does not provide a full group member list, so each member needs to register once.

1. In the Codespace terminal, run `python3 collect_members.py`.
2. Enter the bot token when prompted (it is hidden), then enter the group chat ID.
3. While the script listens for 5 minutes, ask every group member to send `/qeydiyyat@YeloMailXatirlatmaBot` in the target group.
4. Copy the JSON roster printed by the script.
5. In the repository, open **Settings → Secrets and variables → Actions** and add or update these repository secrets:
   - `TELEGRAM_BOT_TOKEN` — the rotated token from BotFather
   - `TELEGRAM_CHAT_ID` — the numeric ID of the group
   - `TELEGRAM_GROUP_MEMBERS` — the complete JSON roster printed in step 4

Do not commit any secret or roster to this repository. Re-run the member collection and update `TELEGRAM_GROUP_MEMBERS` when group members change. A person absent from this roster cannot be tagged or tracked for acknowledgements.

## Test

Use **Actions → Yelo mail reminders → Run workflow**. It will send a real group message, collect button clicks for 15 minutes, then post the result and tag any registered members who did not confirm. Do this when the group is ready for a test message.

The scheduled workflow is enabled on the default branch. Each scheduled run stays active for up to 15 minutes to collect confirmations.
