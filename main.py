import os
import time
import logging
import asyncio
import aiohttp
import discord
import json
from discord.ext import commands, tasks

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("status-bot")

TOKEN = os.getenv("TOKEN")
WEB_URL = "https://zoream.pages.dev"
APP_STATUS_URL = "https://raw.githubusercontent.com/WolfGames156/Zoream-Server/refs/heads/main/public/stat.txt"

ONLINE = "<:online:1441849395757973574>"
OFFLINE = "<:offline:1441850753248526446>"
CARE = "<:bakim:1441850693387292925>"

CHECK_INTERVAL = 30  # Mesaj her 30 saniyede güncellenecek
UPTIME_FILE = "/data/uptime.json"

# ---------------- Uptime ----------------
def load_uptime():
    if not os.path.exists(UPTIME_FILE):
        return {"web": {"up":0,"total":0}, "app":{"up":0,"total":0}}
    with open(UPTIME_FILE,"r") as f:
        return json.load(f)

def save_uptime(data):
    with open(UPTIME_FILE,"w") as f:
        json.dump(data,f,indent=2)

uptime = load_uptime()

def percent(val):
    return round((val["up"] / val["total"] * 100), 2) if val["total"] > 0 else 0.0

def progress_bar(percentage):
    filled = int(percentage // 10)
    empty = 10 - filled
    return "█" * filled + "░" * empty

def format_seconds(seconds: int) -> str:
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    parts = []
    if days > 0: parts.append(f"{days}g")
    if hours > 0: parts.append(f"{hours}s")
    if minutes > 0: parts.append(f"{minutes}dk")
    parts.append(f"{seconds}s")
    return " ".join(parts)

# ---------------- Bot ----------------
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=".", intents=intents)

aio_session = None

# Sunucu bazlı status mesajlarını saklamak için
status_data = {}  # {guild_id: {"channel": channel, "message_id": id}}

# ---------------- HTTP Status ----------------
async def get_web_status(url: str) -> str:
    global aio_session
    try:
        async with aio_session.get(url, timeout=10) as resp:
            return "online" if resp.status == 200 else "offline"
    except:
        return "offline"

async def get_app_status(url: str) -> str:
    global aio_session
    try:
        async with aio_session.get(url, timeout=10) as resp:
            text = (await resp.text()).strip().lower()
            if text == "up": return "online"
            if text == "down": return "offline"
            if text in ("care","bakim","maintenance"): return "bakim"
            return "offline"
    except:
        return "offline"

# ---------------- Embed ----------------
def format_status_message(web_status: str, app_status: str) -> discord.Embed:
    web_emoji = ONLINE if web_status == "online" else OFFLINE
    app_emoji = (
        ONLINE if app_status == "online"
        else CARE if app_status == "bakim"
        else OFFLINE
    )

    if web_status == "online" and app_status == "online":
        color = discord.Color.green()
    elif app_status == "bakim":
        color = discord.Color.yellow()
    else:
        color = discord.Color.red()

    web_percent = percent(uptime["web"])
    app_percent = percent(uptime["app"])
    total_percent = round((web_percent + app_percent) / 2, 2)

    web_total_seconds = uptime["web"]["total"] * CHECK_INTERVAL
    app_total_seconds = uptime["app"]["total"] * CHECK_INTERVAL
    total_seconds = (web_total_seconds + app_total_seconds) // 2
    total_time_str = format_seconds(total_seconds)

    bar = progress_bar(total_percent)

    embed = discord.Embed(
        title="<a:status:1441869522658267186> Sistem Durum Paneli",
        description=f"🔄 **Son Güncelleme:** <t:{int(time.time())}:R>",
        color=color
    )

    embed.add_field(
        name="🌐 Web Sitesi Durumu",
        value=f"{web_emoji} **{web_status.capitalize()}**\nUptime: **{web_percent}%**\n\n",
        inline=False
    )

    embed.add_field(
        name="💻 Uygulama Durumu",
        value=f"{app_emoji} **{app_status.capitalize()}**\nUptime: **{app_percent}%**\n\n",
        inline=False
    )

    embed.add_field(
        name="📊 Toplam Uptime",
        value=f"**{total_percent}%** ({total_time_str})\n```\n{bar}\n```",
        inline=False
    )

    embed.set_footer(text="Zoream Monitoring • By SYS_0xA7")
    embed.timestamp = discord.utils.utcnow()
    return embed

# ---------------- Güncelleme ----------------
async def update_status_message_for_guild(guild_id, channel):
    global status_data, uptime

    web_status = await get_web_status(WEB_URL)
    app_status = await get_app_status(APP_STATUS_URL)

    # Uptime sayaçları
    uptime["web"]["total"] += 1
    uptime["app"]["total"] += 1
    if web_status == "online": uptime["web"]["up"] += 1
    if app_status == "online": uptime["app"]["up"] += 1

    save_uptime(uptime)

    embed = format_status_message(web_status, app_status)

    msg_id = status_data.get(guild_id, {}).get("message_id")
    try:
        if msg_id:
            try:
                msg = await channel.fetch_message(msg_id)
                await msg.edit(embed=embed)
            except discord.NotFound:
                msg = await channel.send(embed=embed)
                status_data[guild_id] = {"channel": channel, "message_id": msg.id}
        else:
            msg = await channel.send(embed=embed)
            status_data[guild_id] = {"channel": channel, "message_id": msg.id}

    except Exception as e:
        log.exception(e)

    return web_status, app_status

# ---------------- Döngü ----------------
@tasks.loop(seconds=CHECK_INTERVAL)
async def check_status_loop():
    for guild_id, data in status_data.items():
        channel = data["channel"]
        if channel:
            await update_status_message_for_guild(guild_id, channel)

# ---------------- Events ----------------
@bot.event
async def on_ready():
    global aio_session
    log.info(f"Bot logged in as {bot.user}")

# ---------------- Commands ----------------
@bot.command(name="status")
async def cmd_status(ctx):
    guild_id = ctx.guild.id
    channel = ctx.channel

    # Eski status mesajını sil
    old_msg_id = status_data.get(guild_id, {}).get("message_id")
    if old_msg_id:
        try:
            old_msg = await channel.fetch_message(old_msg_id)
            await old_msg.delete()
        except:
            pass

    # Yeni status mesajını gönder ve kaydet
    await update_status_message_for_guild(guild_id, channel)

    if not check_status_loop.is_running():
        check_status_loop.start()


class IdlePresenceBot(discord.Client):
    async def on_ready(self):
        await self.change_presence(
            status=discord.Status.online,
            activity=discord.Game(name="Zoream oynuyor")
        )
        log.info(f"Idle bot logged in as {self.user}")

async def start_idle_bot():
    intents = discord.Intents.none()
    client = IdlePresenceBot(intents=intents)
    await client.start(os.getenv("IDLE_TOKEN"))
async def main():
    global aio_session
    aio_session = aiohttp.ClientSession()

    task_main_bot = asyncio.create_task(bot.start(TOKEN))
    task_idle_bot = asyncio.create_task(start_idle_bot())

    await asyncio.gather(task_main_bot, task_idle_bot)


if __name__ == "__main__":
    asyncio.run(main())
