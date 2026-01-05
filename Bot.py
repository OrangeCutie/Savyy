import discord
from discord.ext import commands, tasks
from better_profanity import profanity
import json
import os
import re
from datetime import datetime

# Environment variables on Railway
TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID"))

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
profanity.load_censor_words()  # default words

# File paths
WARNINGS_FILE = "warnings.json"
LOGS_DIR = "logs/"

# Ensure logs folder exists
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

# Load warnings or start fresh
if not os.path.exists(WARNINGS_FILE):
    with open(WARNINGS_FILE, "w") as f:
        json.dump({}, f)

with open(WARNINGS_FILE, "r") as f:
    try:
        warnings_data = json.load(f)
    except json.JSONDecodeError:
        warnings_data = {}

# -------------------------------
# Utility Functions
# -------------------------------
def save_warnings():
    with open(WARNINGS_FILE, "w") as f:
        json.dump(warnings_data, f, indent=4)

def log_action(action):
    now = datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
    with open(f"{LOGS_DIR}log_{now}.txt", "a", encoding="utf-8") as f:
        f.write(action + "\n")

def is_profanity(message_content):
    # Check default words
    if profanity.contains_profanity(message_content):
        return True
    # Add extra global words / bypasses here
    blacklisted_words = ["neger", "fuck", "bitch", "asshole", "faggot"]
    for word in blacklisted_words:
        pattern = re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)
        if pattern.search(message_content):
            return True
    return False

# -------------------------------
# Anti-raid variables
# -------------------------------
recent_joins = {}

# -------------------------------
# Events
# -------------------------------
@bot.event
async def on_ready():
    print(f"{bot.user} is online and ready!")

@bot.event
async def on_member_join(member):
    guild_id = member.guild.id
    if guild_id not in recent_joins:
        recent_joins[guild_id] = []
    recent_joins[guild_id].append(member.id)
    # Anti-raid: if more than 3 join in 10 seconds, kick new members
    if len(recent_joins[guild_id]) > 3:
        for user_id in recent_joins[guild_id]:
            user = member.guild.get_member(user_id)
            if user:
                try:
                    await user.kick(reason="Anti-raid protection")
                    log_action(f"Anti-raid: Kicked {user} from {member.guild.name}")
                except:
                    pass
        recent_joins[guild_id] = []

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Auto moderation
    if is_profanity(message.content):
        user_id = str(message.author.id)
        reason = f"Used blacklisted word: {message.content}"
        if user_id not in warnings_data:
            warnings_data[user_id] = {"count": 0, "reasons": []}

        warnings_data[user_id]["count"] += 1
        warnings_data[user_id]["reasons"].append(reason)
        save_warnings()

        await message.delete()
        await message.author.send(f"You have been warned in **{message.guild.name}** ({warnings_data[user_id]['count']}/4). Reason: {reason}")
        await message.channel.send(f"{message.author.mention} has been warned ({warnings_data[user_id]['count']}/4).", delete_after=5)
        log_action(f"{message.author} warned in {message.guild.name}: {reason}")

        if warnings_data[user_id]["count"] >= 4:
            try:
                await message.guild.ban(message.author, reason="Reached 4 warnings")
                log_action(f"{message.author} banned in {message.guild.name} for 4 warnings")
            except:
                pass

    await bot.process_commands(message)

# -------------------------------
# Commands
# -------------------------------
def is_owner(ctx):
    if ctx.author.id == OWNER_ID:
        return True
    # Detect server highest role
    if ctx.author.guild_permissions.administrator:
        return True
    return False

@bot.command()
async def warn(ctx, member: discord.Member, *, reason: str):
    if not is_owner(ctx):
        return await ctx.send("You cannot use this command.")
    user_id = str(member.id)
    if user_id not in warnings_data:
        warnings_data[user_id] = {"count": 0, "reasons": []}
    warnings_data[user_id]["count"] += 1
    warnings_data[user_id]["reasons"].append(reason)
    save_warnings()
    await ctx.send(f"Manual warn issued to {member.mention}. Reason: {reason}")
    await member.send(f"You have been manually warned in **{ctx.guild.name}**. Reason: {reason}")
    log_action(f"Manual warn: {member} Reason: {reason}")

@bot.command()
async def warnings(ctx, member: discord.Member):
    user_id = str(member.id)
    if user_id not in warnings_data:
        return await ctx.send(f"{member} has no warnings.")
    count = warnings_data[user_id]["count"]
    reasons = "\n".join(warnings_data[user_id]["reasons"])
    await ctx.send(f"{member} has {count} warnings.\nReasons:\n{reasons}")

@bot.command()
async def warn_list(ctx):
    if not is_owner(ctx):
        return await ctx.send("You cannot use this command.")
    lines = []
    for user_id, data in warnings_data.items():
        member = ctx.guild.get_member(int(user_id))
        if member:
            lines.append(f"{member}: {data['count']} warnings | Reasons: {', '.join(data['reasons'])}")
    if not lines:
        return await ctx.send("No warnings found.")
    await ctx.send("\n".join(lines))

@bot.command()
async def reset_warnings(ctx, member: discord.Member):
    if not is_owner(ctx):
        return await ctx.send("You cannot use this command.")
    user_id = str(member.id)
    if user_id in warnings_data:
        warnings_data[user_id] = {"count": 0, "reasons": []}
        save_warnings()
    await ctx.send(f"{member} warnings reset.")

@bot.command()
async def unban(ctx, user_id: int):
    if not is_owner(ctx):
        return await ctx.send("You cannot use this command.")
    user = await bot.fetch_user(user_id)
    for guild in bot.guilds:
        try:
            await guild.unban(user)
            log_action(f"Unbanned {user} in {guild.name}")
        except:
            pass
    await ctx.send(f"{user} has been unbanned.")

# -------------------------------
# Run bot
# -------------------------------
bot.run(TOKEN)
