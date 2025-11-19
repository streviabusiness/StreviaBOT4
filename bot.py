import discord
from discord import app_commands
from discord.ext import commands
import json
import os
from datetime import datetime, timedelta
import re

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

CONFIG_FILE = "config.json"
COOLDOWNS_FILE = "cooldowns.json"

def load_json(filename):
    if os.path.exists(filename):
        try:
            with open(filename, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}

def save_json(filename, data):
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)

def parse_interval(interval_str):
    match = re.match(r'(\d+)([dhm])', interval_str.lower())
    if not match:
        return None
    amount, unit = match.groups()
    amount = int(amount)
    if unit == 'd':
        return timedelta(days=amount)
    elif unit == 'h':
        return timedelta(hours=amount)
    elif unit == 'm':
        return timedelta(minutes=amount)
    return None

def format_timedelta(td):
    total_seconds = int(td.total_seconds())
    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    parts = []
    if days > 0:
        parts.append(f"{days} Tag{'e' if days != 1 else ''}")
    if hours > 0:
        parts.append(f"{hours} Stunde{'n' if hours != 1 else ''}")
    if minutes > 0:
        parts.append(f"{minutes} Minute{'n' if minutes != 1 else ''}")
    if seconds > 0 and not parts:
        parts.append(f"{seconds} Sekunde{'n' if seconds != 1 else ''}")
    return ", ".join(parts) if parts else "0 Sekunden"

@bot.event
async def on_ready():
    print(f'{bot.user} ist online und bereit!')
    try:
        await bot.tree.sync()
    except Exception:
        pass

@bot.tree.command(name="set-window", description="Setze ein Message-Cooldown-Fenster für eine Rolle in einem Channel")
@app_commands.describe(
    role="Die Rolle, für die das Cooldown gelten soll",
    channel="Der Channel, in dem das Cooldown aktiv ist",
    interval="Das Cooldown-Intervall (z.B. 3d, 7d, 12h, 30m)"
)
async def set_window(interaction: discord.Interaction, role: discord.Role, channel: discord.TextChannel, interval: str):
    parsed_interval = parse_interval(interval)
    if parsed_interval is None:
        await interaction.response.send_message("❌ Ungültiges Intervall-Format! Nutze z.B.: `3d`, `12h`, `30m`", ephemeral=True)
        return
    config = load_json(CONFIG_FILE)
    key = f"{interaction.guild_id}_{channel.id}_{role.id}"
    config[key] = {
        "guild_id": interaction.guild_id,
        "channel_id": channel.id,
        "role_id": role.id,
        "interval": interval,
        "interval_seconds": int(parsed_interval.total_seconds())
    }
    save_json(CONFIG_FILE, config)
    await interaction.response.send_message(f"✅ Cooldown für {role.name} in {channel.name} auf {interval} gesetzt.", ephemeral=True)

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return
    await bot.process_commands(message)
    config = load_json(CONFIG_FILE)
    cooldowns = load_json(COOLDOWNS_FILE)
    for key, rule in config.items():
        if rule["channel_id"] == message.channel.id and rule["guild_id"] == message.guild.id:
            role_id = rule["role_id"]
            if any(r.id == role_id for r in message.author.roles):
                user_key = f"{message.guild.id}_{message.channel.id}_{message.author.id}"
                if user_key in cooldowns:
                    last_message_time = datetime.fromisoformat(cooldowns[user_key])
                    interval_seconds = rule["interval_seconds"]
                    time_passed = (datetime.now() - last_message_time).total_seconds()
                    if time_passed < interval_seconds:
                        remaining = timedelta(seconds=interval_seconds - time_passed)
                        try:
                            await message.delete()
                            warning = await message.channel.send(f"⏳ {message.author.mention}, du kannst erst in **{format_timedelta(remaining)}** wieder schreiben!")
                            await warning.delete(delay=5)
                        except discord.Forbidden:
                            pass
                        return
                cooldowns[user_key] = datetime.now().isoformat()
                save_json(COOLDOWNS_FILE, cooldowns)
                break

token = os.getenv('DISCORD_BOT_TOKEN')
if not token:
    print("❌ FEHLER: DISCORD_BOT_TOKEN nicht gefunden!")
else:
    bot.run(token)
