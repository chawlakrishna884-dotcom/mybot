# Railway Discord Moderation Bot

Python `discord.py` moderation bot with SQLite, slash commands, automoderation, and Railway deployment support.

## Commands

`/warn` `/warnings` `/clearwarnings` `/timeout` `/untimeout` `/kick` `/ban` `/purge` `/slowmode` `/lock` `/unlock` `/setlog` `/config`

## Discord setup

Create a bot in the Discord Developer Portal. Enable **Server Members Intent** and **Message Content Intent**. Invite it with the `bot` and `applications.commands` scopes and the required moderation permissions.

## Railway setup

1. Create a Railway project from this repository and choose branch `feature/moderation-bot`.
2. Add `DISCORD_TOKEN` as a Railway variable. Never commit the token.
3. Optionally add `LOG_CHANNEL_ID`, `BAD_WORDS`, and `DATABASE_PATH`.
4. Deploy. Railway uses the included Dockerfile.

For persistent SQLite data, attach a Railway Volume and set `DATABASE_PATH=/data/moderation.db`.
