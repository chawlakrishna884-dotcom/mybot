# Railway Discord Moderation Bot

Python `discord.py` moderation bot with SQLite, slash commands, automoderation, Railway deployment, and cross-server custom emoji importing.

## Commands

`/warn` `/warnings` `/clearwarnings` `/timeout` `/untimeout` `/kick` `/ban` `/purge` `/slowmode` `/lock` `/unlock` `/setlog` `/config` `/steal`

## Steal custom emojis

Use `/steal` with one or more custom emoji mentions copied from another server:

`/steal emojis:<:party:123456789> <a:dance:987654321>`

The bot downloads each emoji from Discord's CDN and creates it in the current server. The bot needs **Manage Expressions** permission, and the destination server must have available emoji slots. Discord limits each command to 20 emojis.

Use this only for emojis you are allowed to copy; do not copy copyrighted or server-exclusive artwork without permission.

## Discord setup

Create a bot in the Discord Developer Portal. Enable **Server Members Intent** and **Message Content Intent**. Invite it with the `bot` and `applications.commands` scopes and the required moderation permissions, including **Manage Expressions** for `/steal`.

## Railway setup

1. Create a Railway project from this repository and choose branch `feature/moderation-bot`.
2. Add `DISCORD_TOKEN` as a Railway variable. Never commit the token.
3. Optionally add `LOG_CHANNEL_ID`, `BAD_WORDS`, and `DATABASE_PATH`.
4. Deploy. Railway uses the included Dockerfile.

For persistent SQLite data, attach a Railway Volume and set `DATABASE_PATH=/data/moderation.db`.
