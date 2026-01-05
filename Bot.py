import discord
from discord.ext import commands
import json
import os
import asyncio
from better_profanity import profanity

# ---------------- Config ----------------
TOKEN = "YOUR_BOT_TOKEN_HERE"
OWNER_ID = 739411481342509059
WARNINGS_FILE = "warnings.json"
BAD_WORDS = ["fuck", "bitch", "neger", "du hure", "idiot", "gay"]  # Expand as needed
DELETE_AFTER = 5  # seconds
MAX_WARNINGS = 4

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="/", intents=intents)

# ---------------- Load warnings ----------------
if os.path.exists(WARNINGS_FILE):
    with open(WARNINGS_FILE, "r") as f:
        try:
            warnings = json.load(f)
        except json.JSONDecodeError:
            warnings = {}
else:
    warnings = {}

def save_warnings():
    with open(WARNINGS_FILE, "w") as f:
        json.dump(warnings, f, indent=4)

# ---------------- Utility ----------------
def is_admin(ctx):
    if ctx.author.id == OWNER_ID:
        return True
    if ctx.guild:
        top_role = max(ctx.author.roles, key=lambda r: r.position)
        if top_role.permissions.administrator:
            return True
    return False

def warn_user(user_id, word):
    if str(user_id) not in warnings:
        warnings[str(user_id)] = {"count": 0, "last_word": ""}
    warnings[str(user_id)]["count"] += 1
    warnings[str(user_id)]["last_word"] = word
    save_warnings()
    return warnings[str(user_id)]["count"]

# ---------------- Events ----------------
@bot.event
async def on_ready():
    print(f"Bot logged in as {bot.user}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    content_lower = message.content.lower()

    # Check for bad words
    for word in BAD_WORDS:
        if word in content_lower:
            count = warn_user(message.author.id, word)
            await message.delete()
            await message.author.send(
                f"You have been warned in **{message.guild.name}** for saying: `{word}`. "
                f"This is warning {count}/{MAX_WARNINGS}. Please stop."
            )
            if count >= MAX_WARNINGS:
                await message.guild.ban(message.author, reason=f"Reached {MAX_WARNINGS} warnings.")
            return

    await bot.process_commands(message)

# ---------------- Commands ----------------
@bot.command()
async def warnings(ctx, member: discord.Member):
    data = warnings.get(str(member.id), {"count": 0, "last_word": "None"})
    await ctx.send(f"{member} has {data['count']} warnings. Last word: {data['last_word']}")

@bot.command()
async def warn(ctx, member: discord.Member, *, reason: str = "Manual warning"):
    if not is_admin(ctx):
        await ctx.send("You do not have permission to warn.")
        return
    count = warn_user(member.id, reason)
    await ctx.send(f"Manual warn issued to {member}. Warning {count}/{MAX_WARNINGS}")
    await member.send(f"You have been manually warned in {ctx.guild.name} for: {reason}")

@bot.command()
async def warnlist(ctx):
    embed = discord.Embed(title="Warn List")
    for user_id, data in warnings.items():
        member = ctx.guild.get_member(int(user_id))
        if member:
            embed.add_field(name=member.name, value=f"Warnings: {data['count']}\nLast: {data['last_word']}", inline=False)
    await ctx.send(embed=embed)

@bot.command()
async def resetwarnings(ctx, member: discord.Member):
    if not is_admin(ctx):
        await ctx.send("You do not have permission to reset warnings.")
        return
    warnings.pop(str(member.id), None)
    save_warnings()
    await ctx.send(f"Warnings for {member} have been reset.")

@bot.command()
async def ban(ctx, member: discord.Member):
    if not is_admin(ctx):
        await ctx.send("You do not have permission to ban.")
        return
    await member.ban(reason="Banned via command.")
    await ctx.send(f"{member} has been banned.")

@bot.command()
async def unban(ctx, user_id: int):
    if not is_admin(ctx):
        await ctx.send("You do not have permission to unban.")
        return
    user = await bot.fetch_user(user_id)
    await ctx.guild.unban(user)
    await ctx.send(f"{user} has been unbanned.")

# ---------------- Run Bot ----------------
bot.run(TOKEN)
