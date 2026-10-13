import os
import re
import sqlite3
import time
from collections import defaultdict, deque
from datetime import timedelta

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is required")
DB = os.getenv("DATABASE_PATH", "moderation.db")
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "0"))
BAD_WORDS = {x.strip().lower() for x in os.getenv("BAD_WORDS", "").split(",") if x.strip()}
LINKS = re.compile(r"https?://|www\\.", re.I)
CUSTOM_EMOJI = re.compile(r"<(a?):([A-Za-z0-9_~]+):(\\d+)>")
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
spam = defaultdict(lambda: deque(maxlen=8))


def database():
    con = sqlite3.connect(DB)
    con.execute("CREATE TABLE IF NOT EXISTS warnings (guild INTEGER, user INTEGER, moderator INTEGER, reason TEXT, created INTEGER)")
    con.execute("CREATE TABLE IF NOT EXISTS settings (guild INTEGER PRIMARY KEY, log_channel INTEGER DEFAULT 0, anti_links INTEGER DEFAULT 0, anti_spam INTEGER DEFAULT 1)")
    con.commit()
    return con


def setting(guild, name, default=0):
    con = database(); row = con.execute("SELECT log_channel, anti_links, anti_spam FROM settings WHERE guild=?", (guild,)).fetchone(); con.close()
    if not row: return default
    return dict(log_channel=row[0], anti_links=row[1], anti_spam=row[2]).get(name, default)


async def log(guild, title, text, color=discord.Color.blurple()):
    channel_id = setting(guild.id, "log_channel", LOG_CHANNEL_ID)
    channel = guild.get_channel(int(channel_id)) if channel_id else None
    if channel:
        await channel.send(embed=discord.Embed(title=title, description=text, color=color, timestamp=discord.utils.utcnow()))


def mod_check():
    return app_commands.checks.has_permissions(manage_messages=True)


async def valid_target(interaction, member):
    if member == interaction.user or member == interaction.guild.owner or (member.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner):
        await interaction.response.send_message("You cannot moderate that member.", ephemeral=True)
        return False
    return True


@bot.event
async def on_ready():
    database().close()
    await bot.tree.sync()
    print(f"Ready as {bot.user}")


@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return
    content = message.content.lower()
    if not message.author.guild_permissions.manage_messages:
        if BAD_WORDS and any(re.search(rf"\\b{re.escape(word)}\\b", content) for word in BAD_WORDS):
            await message.delete(); await log(message.guild, "Filtered message", f"{message.author.mention} in {message.channel.mention}", discord.Color.red()); return
        if setting(message.guild.id, "anti_links") and LINKS.search(message.content):
            await message.delete(); await log(message.guild, "Link removed", f"{message.author.mention} in {message.channel.mention}", discord.Color.orange()); return
        bucket = spam[(message.guild.id, message.author.id)]; now = time.monotonic(); bucket.append(now)
        if setting(message.guild.id, "anti_spam", 1) and len(bucket) >= 6 and now - bucket[0] < 8:
            await message.delete()
            try: await message.author.timeout(timedelta(minutes=1), reason="Anti-spam")
            except discord.HTTPException: pass
            bucket.clear(); await log(message.guild, "Anti-spam timeout", message.author.mention, discord.Color.red()); return
    await bot.process_commands(message)


@bot.tree.command(name="warn", description="Warn a member")
@mod_check()
async def warn(i: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    con=database(); con.execute("INSERT INTO warnings VALUES (?,?,?,?,?)", (i.guild.id, member.id, i.user.id, reason, int(time.time()))); con.commit(); con.close()
    await i.response.send_message(f"Warned {member.mention}: {reason}"); await log(i.guild, "Member warned", f"{member.mention} — {reason}", discord.Color.orange())


@bot.tree.command(name="warnings", description="Show warnings")
@mod_check()
async def warnings(i: discord.Interaction, member: discord.Member):
    con=database(); rows=con.execute("SELECT reason,created FROM warnings WHERE guild=? AND user=? ORDER BY created DESC", (i.guild.id, member.id)).fetchall(); con.close()
    text="\\n".join(f"• <t:{stamp}:d> — {reason}" for reason,stamp in rows) or "No warnings."
    await i.response.send_message(embed=discord.Embed(title=f"Warnings for {member}", description=text), ephemeral=True)


@bot.tree.command(name="clearwarnings", description="Clear warnings")
@mod_check()
async def clearwarnings(i: discord.Interaction, member: discord.Member):
    con=database(); con.execute("DELETE FROM warnings WHERE guild=? AND user=?", (i.guild.id, member.id)); con.commit(); con.close(); await i.response.send_message(f"Cleared warnings for {member.mention}.")


@bot.tree.command(name="timeout", description="Timeout a member")
@mod_check()
async def timeout(i: discord.Interaction, member: discord.Member, minutes: app_commands.Range[int,1,40320], reason: str="No reason provided"):
    if not await valid_target(i, member): return
    await member.timeout(timedelta(minutes=minutes), reason=reason); await i.response.send_message(f"Timed out {member.mention} for {minutes} minutes."); await log(i.guild, "Timeout", f"{member.mention} — {reason}", discord.Color.orange())


@bot.tree.command(name="untimeout", description="Remove timeout")
@mod_check()
async def untimeout(i: discord.Interaction, member: discord.Member):
    await member.timeout(None, reason="Timeout removed"); await i.response.send_message(f"Removed timeout from {member.mention}.")


@bot.tree.command(name="kick", description="Kick a member")
@app_commands.checks.has_permissions(kick_members=True)
async def kick(i: discord.Interaction, member: discord.Member, reason: str="No reason provided"):
    if not await valid_target(i, member): return
    await member.kick(reason=reason); await i.response.send_message(f"Kicked {member}."); await log(i.guild, "Kick", f"{member} — {reason}", discord.Color.red())


@bot.tree.command(name="ban", description="Ban a member")
@app_commands.checks.has_permissions(ban_members=True)
async def ban(i: discord.Interaction, member: discord.Member, reason: str="No reason provided"):
    if not await valid_target(i, member): return
    await member.ban(reason=reason, delete_message_seconds=86400); await i.response.send_message(f"Banned {member}."); await log(i.guild, "Ban", f"{member} — {reason}", discord.Color.red())


@bot.tree.command(name="purge", description="Delete messages")
@mod_check()
async def purge(i: discord.Interaction, amount: app_commands.Range[int,1,100]):
    await i.response.defer(ephemeral=True); deleted=await i.channel.purge(limit=amount); await i.followup.send(f"Deleted {len(deleted)} messages.", ephemeral=True)


@bot.tree.command(name="slowmode", description="Set slowmode")
@mod_check()
async def slowmode(i: discord.Interaction, seconds: app_commands.Range[int,0,21600]):
    await i.channel.edit(slowmode_delay=seconds); await i.response.send_message(f"Slowmode set to {seconds} seconds.")


@bot.tree.command(name="lock", description="Lock channel")
@mod_check()
async def lock(i: discord.Interaction):
    await i.channel.set_permissions(i.guild.default_role, send_messages=False); await i.response.send_message("Channel locked.")


@bot.tree.command(name="unlock", description="Unlock channel")
@mod_check()
async def unlock(i: discord.Interaction):
    await i.channel.set_permissions(i.guild.default_role, send_messages=None); await i.response.send_message("Channel unlocked.")


@bot.tree.command(name="setlog", description="Set moderation log channel")
@app_commands.checks.has_permissions(administrator=True)
async def setlog(i: discord.Interaction, channel: discord.TextChannel):
    con=database(); con.execute("INSERT INTO settings(guild,log_channel) VALUES(?,?) ON CONFLICT(guild) DO UPDATE SET log_channel=excluded.log_channel", (i.guild.id,channel.id)); con.commit(); con.close(); await i.response.send_message(f"Logs set to {channel.mention}.")


@bot.tree.command(name="config", description="Configure automod")
@app_commands.checks.has_permissions(administrator=True)
async def config(i: discord.Interaction, anti_links: bool=False, anti_spam: bool=True):
    con=database(); con.execute("INSERT INTO settings(guild,anti_links,anti_spam) VALUES(?,?,?) ON CONFLICT(guild) DO UPDATE SET anti_links=excluded.anti_links, anti_spam=excluded.anti_spam", (i.guild.id,int(anti_links),int(anti_spam))); con.commit(); con.close(); await i.response.send_message(f"Anti-links: {anti_links} | Anti-spam: {anti_spam}")


@bot.tree.command(name="steal", description="Copy custom emojis into this server")
@app_commands.checks.has_permissions(manage_emojis_and_stickers=True)
async def steal(i: discord.Interaction, emojis: str):
    matches = list(CUSTOM_EMOJI.finditer(emojis))
    if not matches:
        await i.response.send_message("Send custom emoji mentions, for example `<:party:123456789>`.", ephemeral=True)
        return
    await i.response.defer(ephemeral=True)
    results = []
    async with aiohttp.ClientSession() as session:
        for match in matches[:20]:
            animated, name, emoji_id = match.groups()
            extension = "gif" if animated else "png"
            url = f"https://cdn.discordapp.com/emojis/{emoji_id}.{extension}?size=128&quality=lossless"
            try:
                async with session.get(url) as response:
                    if response.status != 200:
                        results.append(f"❌ `{name}`: download failed")
                        continue
                    image = await response.read()
                created = await i.guild.create_custom_emoji(name=name[:32], image=image, reason=f"Stolen by {i.user}")
                results.append(f"✅ {created} `{name}`")
            except discord.HTTPException as error:
                results.append(f"❌ `{name}`: {error.status} (check emoji slots and permissions)")
            except Exception:
                results.append(f"❌ `{name}`: failed")
    await i.followup.send("\n".join(results), ephemeral=True)


@bot.tree.error
async def command_error(i, error):
    msg="You do not have permission to use this command." if isinstance(error, app_commands.MissingPermissions) else "The command failed. Check bot permissions."
    if i.response.is_done(): await i.followup.send(msg, ephemeral=True)
    else: await i.response.send_message(msg, ephemeral=True)

bot.run(TOKEN)
