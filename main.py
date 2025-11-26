# main.py
import os
import time
import logging
import asyncio
import aiohttp
import discord
from discord.ext import commands, tasks

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("status-bot")

# ----- CONFIG -----
TOKEN = "MTQ0Mjk1NjYxNjU5NTkzNTM5Ng.GedUde.g_JyyU_0foEkpy4r__tAFGUrl57m0ug0Euk6MFI" 
WEB_URL = "https://zoream.pages.dev"
APP_STATUS_URL = "https://raw.githubusercontent.com/WolfGames156/hidzor/main/stat1.txt"

ONLINE = "<:online:1441849395757973574>"
OFFLINE = "<:offline:1441850753248526446>"
CARE = "<:bakim:1441850693387292925>"

CHECK_INTERVAL_ONLINE = 60   # ONLINE olsa bile 1 dakikada bir güncelle
CHECK_INTERVAL_PROBLEM = 5    # Offline/bakım varsa 5 sn
# -------------------

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix=".", intents=intents)

status_channel: discord.TextChannel | None = None
status_message_id: int | None = None
previous_status = {"web": None, "app": None}
_last_interval = None
aio_session: aiohttp.ClientSession | None = None


# ---- STATUS FETCH ----
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
            if text == "up":
                return "online"
            if text == "down":
                return "offline"
            if text in ("care", "bakim", "maintenance"):
                return "bakim"
            return "offline"
    except:
        return "offline"


# ---- EMBED FORMAT ----
def format_status_message(web_status: str, app_status: str) -> discord.Embed:
    web_emoji = ONLINE if web_status == "online" else OFFLINE

    if app_status == "online":
        app_emoji = ONLINE
    elif app_status == "bakim":
        app_emoji = CARE
    else:
        app_emoji = OFFLINE

    # embed color
    if web_status == "online" and app_status == "online":
        color = discord.Color.green()
    elif app_status == "bakim":
        color = discord.Color.yellow()
    else:
        color = discord.Color.red()

    ts = int(time.time())

    embed = discord.Embed(
        title="🛰️<a:status:1441869522658267186> Sistem Durum Paneli",
        description=f"🔄 **Son Güncelleme:** <t:{ts}:R>",
        color=color
    )

    embed.add_field(
        name="🌐 Web Sitesi Durumu",
        value=f"{web_emoji} **{web_status.capitalize()}**",
        inline=False
    )

    embed.add_field(
        name="📱 Uygulama Durumu",
        value=f"{app_emoji} **{app_status.capitalize()}**",
        inline=False
    )

    embed.set_footer(text="Zoream Monitoring • Otomatik Durum Sistemi")
    embed.timestamp = discord.utils.utcnow()

    return embed


# ---- SEND/UPDATE MESSAGE ----
async def update_status_message_in_channel(channel: discord.TextChannel):
    global status_message_id, previous_status

    web_status = await get_web_status(WEB_URL)
    app_status = await get_app_status(APP_STATUS_URL)

    previous_status["web"] = web_status
    previous_status["app"] = app_status

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
        log.exception("Embed update error: %s", e)

    return (web_status, app_status)


# ---- LOOP ----
@tasks.loop(seconds=CHECK_INTERVAL_ONLINE)
async def check_status_loop():
    global status_channel, _last_interval

    if not status_channel:
        return

    web_status, app_status = await update_status_message_in_channel(status_channel)

    # online ise 60 saniye — problem varsa 5 saniye
    desired = CHECK_INTERVAL_ONLINE if (web_status == "online" and app_status == "online") else CHECK_INTERVAL_PROBLEM

    if desired != _last_interval:
        check_status_loop.change_interval(seconds=desired)
        _last_interval = desired
        log.info(f"Loop interval changed to {desired} seconds")


# ---- EVENTS ----
@bot.event
async def on_ready():
    global aio_session
    log.info(f"Bot logged in as {bot.user}")
    if aio_session is None:
        aio_session = aiohttp.ClientSession()


@bot.command(name="status")
@commands.has_guild_permissions(administrator=True)
async def cmd_status(ctx: commands.Context):
    global status_channel
    status_channel = ctx.channel

    await ctx.send("🛰️ Sistem durumu bu kanalda izleniyor.")

    await update_status_message_in_channel(status_channel)

    if not check_status_loop.is_running():
        check_status_loop.start()


@cmd_status.error
async def cmd_status_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("Bu komutu kullanmak için **admin olmalısın**.")
    else:
        await ctx.send("Bir hata oluştu.")


def run_bot():
    try:
        bot.run(TOKEN)
    except Exception as e:
        log.exception("Fatal error: %s", e)


if __name__ == "__main__":
    run_bot()
