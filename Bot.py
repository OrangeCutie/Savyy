import discord
from discord import app_commands
from discord.ext import commands, tasks
from better_profanity import profanity
import json
import os
import re
from datetime import datetime

# -----------------------
# Config / Environment
# -----------------------
TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID"))

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

profanity.load_censor_words()  # default blacklist

WARNINGS_FILE = "warnings.json"
LOGS_DIR = "logs/"

# Ensure logs folder exists
os.makedirs(LOGS_DIR, exist_ok=True)

# Load warnings
if not os.path.exists(WARNINGS_FILE):
    with open(WARNINGS_FILE, "w") as f:
        json.dump({}, f)

with open(WARNINGS_FILE, "r") as f:
    try:
        warnings_data = json.load(f)
    except json.JSONDecodeError:
        warnings_data = {}

# -----------------------
# Utilities
# -----------------------
def save_warnings():
    with open(WARNINGS_FILE, "w") as f:
        json.dump(warnings_data, f, indent=4)

def log_action(action):
    now = datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
    with open(f"{LOGS_DIR}log_{now}.txt", "a", encoding="utf-8") as f:
        f.write(action + "\n")

def is_profanity(message_content):
    # Default profanity
    if profanity.contains_profanity(message_content):
        return True
    # Custom global bypassable words
    blacklisted_words = [
        "neger", "fuck", "bitch", "asshole", "faggot"
    ]
    for word in blacklisted_words:
        pattern = re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)
        if pattern.search(message_content):
            return True
    return False

def is_owner(user: discord.Member):
    return user.id == OWNER_ID or user.guild_permissions.administrator

# -----------------------
# Anti-raid
# -----------------------
recent_joins = {}

@bot.event
async def on_member_join(member):
    guild_id = member.guild.id
    if guild_id not in recent_joins:
        recent_joins[guild_id] = []
    recent_joins[guild_id].append(member.id)
    if len(recent_joins[guild_id]) > 3:
        for user_id in recent_joins[guild_id]:
            user = member.guild.get_member(user_id)
            if user:
                try:
                    await user.kick(reason="Anti-raid protection")
                    log_action(f"Anti-raid: Kicked {user} in {member.guild.name}")
                except:
                    pass
        recent_joins[guild_id] = []

# -----------------------
# Message moderation
# -----------------------
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if is_profanity(message.content):
        user_id = str(message.author.id)
        reason = f"Used blacklisted word: {message.content}"

        if user_id not in warnings_data:
            warnings_data[user_id] = {"count": 0, "reasons": []}

        warnings_data[user_id]["count"] += 1
        warnings_data[user_id]["reasons"].append(reason)
        save_warnings()

        await message.delete()
        await message.author.send(
            f"You have been warned in **{message.guild.name}** "
            f"({warnings_data[user_id]['count']}/4). Reason: {reason}"
        )
        await message.channel.send(
            f"{message.author.mention} has been warned ({warnings_data[user_id]['count']}/4).",
            delete_after=5
        )
        log_action(f"{message.author} warned in {message.guild.name}: {reason}")

        if warnings_data[user_id]["count"] >= 4:
            try:
                await message.guild.ban(message.author, reason="Reached 4 warnings")
                log_action(f"{message.author} banned in {message.guild.name} for 4 warnings")
            except:
                pass

    await bot.process_commands(message)

# -----------------------
# Slash Commands
# -----------------------
@tree.command(name="warn", description="Manually warn a user")
@app_commands.describe(member="The member to warn", reason="Reason for warning")
async def slash_warn(interaction: discord.Interaction, member: discord.Member, reason: str):
    if not is_owner(interaction.user):
        return await interaction.response.send_message("You cannot use this command.", ephemeral=True)
    user_id = str(member.id)
    if user_id not in warnings_data:
        warnings_data[user_id] = {"count": 0, "reasons": []}
    warnings_data[user_id]["count"] += 1
    warnings_data[user_id]["reasons"].append(reason)
    save_warnings()
    await interaction.response.send_message(f"Manual warn issued to {member.mention}. Reason: {reason}")
    await member.send(f"You have been manually warned in **{interaction.guild.name}**. Reason: {reason}")
    log_action(f"Manual warn: {member} Reason: {reason}")

@tree.command(name="warnings", description="Check warnings for a user")
@app_commands.describe(member="The member to check")
async def slash_warnings(interaction: discord.Interaction, member: discord.Member):
    user_id = str(member.id)
    if user_id not in warnings_data:
        return await interaction.response.send_message(f"{member} has no warnings.", ephemeral=True)
    count = warnings_data[user_id]["count"]
    reasons = "\n".join(warnings_data[user_id]["reasons"])
    await interaction.response.send_message(f"{member} has {count} warnings.\nReasons:\n{reasons}", ephemeral=True)

@tree.command(name="warn_list", description="Show all warned users")
async def slash_warn_list(interaction: discord.Interaction):
    if not is_owner(interaction.user):
        return await interaction.response.send_message("You cannot use this command.", ephemeral=True)
    lines = []
    for user_id, data in warnings_data.items():
        member = interaction.guild.get_member(int(user_id))
        if member:
            lines.append(f"{member}: {data['count']} warnings | {', '.join(data['reasons'])}")
    if not lines:
        return await interaction.response.send_message("No warnings found.", ephemeral=True)
    # Split into chunks if too long
    chunks = [lines[i:i+10] for i in range(0, len(lines), 10)]
    for chunk in chunks:
        await interaction.response.send_message("\n".join(chunk), ephemeral=True)

@tree.command(name="reset_warnings", description="Reset warnings for a user")
@app_commands.describe(member="The member to reset")
async def slash_reset_warnings(interaction: discord.Interaction, member: discord.Member):
    if not is_owner(interaction.user):
        return await interaction.response.send_message("You cannot use this command.", ephemeral=True)
    user_id = str(member.id)
    if user_id in warnings_data:
        warnings_data[user_id] = {"count": 0, "reasons": []}
        save_warnings()
    await interaction.response.send_message(f"{member} warnings reset.", ephemeral=True)

@tree.command(name="unban", description="Unban a user by ID")
@app_commands.describe(user_id="The user ID to unban")
async def slash_unban(interaction: discord.Interaction, user_id: str):
    if not is_owner(interaction.user):
        return await interaction.response.send_message("You cannot use this command.", ephemeral=True)
    user = await bot.fetch_user(int(user_id))
    for guild in bot.guilds:
        try:
            await guild.unban(user)
            log_action(f"Unbanned {user} in {guild.name}")
        except:
            pass
    await interaction.response.send_message(f"{user} has been unbanned.", ephemeral=True)

# -----------------------
# Start bot
# -----------------------
@bot.event
async def on_ready():
    await tree.sync()
    print(f"{bot.user} is online and ready with slash commands!")

bot.run(TOKEN)
