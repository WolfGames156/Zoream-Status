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
APP_STATUS_URL = "https://raw.githubusercontent.com/WolfGames156/hidzor/main/stat1.txt"

ONLINE = "<:online:1441849395757973574>"
OFFLINE = "<:offline:1441850753248526446>"
CARE = "<:bakim:1441850693387292925>"

CHECK_INTERVAL = 30  # Mesaj her 30 saniyede güncellenecek

UPTIME_FILE = "uptime.json"

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
    """Saniyeyi gün, saat, dakika, saniye formatına çevirir"""
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    parts = []
    if days > 0: parts.append(f"{days}g")
    if hours > 0: parts.append(f"{hours}s")
    if minutes > 0: parts.append(f"{minutes}dk")
    parts.append(f"{seconds}s")
    return " ".join(parts)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=".", intents=intents)

status_channel = None
status_message_id = None
aio_session = None


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


def format_status_message(web_status: str, app_status: str) -> discord.Embed:

    # Emojiler
    web_emoji = ONLINE if web_status == "online" else OFFLINE
    app_emoji = (
        ONLINE if app_status == "online"
        else CARE if app_status == "bakim"
        else OFFLINE
    )

    # Renk
    if web_status == "online" and app_status == "online":
        color = discord.Color.green()
    elif app_status == "bakim":
        color = discord.Color.yellow()
    else:
        color = discord.Color.red()

    # Uptime hesaplama
    web_percent = percent(uptime["web"])
    app_percent = percent(uptime["app"])
    total_percent = round((web_percent + app_percent) / 2, 2)

    # Toplam süre (saniye cinsinden)
    web_total_seconds = uptime["web"]["total"] * CHECK_INTERVAL
    app_total_seconds = uptime["app"]["total"] * CHECK_INTERVAL
    total_seconds = (web_total_seconds + app_total_seconds) // 2
    total_time_str = format_seconds(total_seconds)

    # Progress bar
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

    embed.set_footer(text="Zoream Monitoring • Otomatik Durum Sistemi")
    embed.timestamp = discord.utils.utcnow()
    return embed


async def update_status_message_in_channel(channel):
    global status_message_id, uptime

    web_status = await get_web_status(WEB_URL)
    app_status = await get_app_status(APP_STATUS_URL)

    # Uptime sayaçları
    uptime["web"]["total"] += 1
    uptime["app"]["total"] += 1
    if web_status == "online": uptime["web"]["up"] += 1
    if app_status == "online": uptime["app"]["up"] += 1

    save_uptime(uptime)

    embed = format_status_message(web_status, app_status)

    try:
        if status_message_id:
            try:
                msg = await channel.fetch_message(status_message_id)
                await msg.edit(embed=embed)
            except discord.NotFound:
                msg = await channel.send(embed=embed)
                status_message_id = msg.id
        else:
            msg = await channel.send(embed=embed)
            status_message_id = msg.id

    except Exception as e:
        log.exception(e)

    return web_status, app_status


@tasks.loop(seconds=CHECK_INTERVAL)
async def check_status_loop():
    if not status_channel:
        return
    await update_status_message_in_channel(status_channel)


@bot.event
async def on_ready():
    global aio_session
    log.info(f"Bot logged in as {bot.user}")
    aio_session = aiohttp.ClientSession()


@bot.command(name="status")
async def cmd_status(ctx):
    global status_channel
    status_channel = ctx.channel
    await update_status_message_in_channel(status_channel)
    if not check_status_loop.is_running():
        check_status_loop.start()


def run_bot():
    bot.run(TOKEN)


if __name__ == "__main__":
    run_bot()
