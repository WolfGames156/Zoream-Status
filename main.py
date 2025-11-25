import discord
from discord.ext import commands, tasks
import aiohttp
import os
import time

# ENV token
TOKEN = 'MTQ0Mjk1NjYxNjU5NTkzNTM5Ng.GedUde.g_JyyU_0foEkpy4r__tAFGUrl57m0ugEuk6MFI'

# Sistem emojileri
ONLINE = ":online:"
OFFLINE = ":offline:"
CARE = ":bakim:"  # Bakım emojisi, uygun ID ile değiştir

# Kontrol aralıkları
CHECK_INTERVAL_UP = 30  # saniye
CHECK_INTERVAL_DOWN = 5  # saniye

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
bot = commands.Bot(command_prefix=".", intents=intents)

# Status mesajını saklamak için
status_message_id = None
status_channel = None

# Önceki durumları saklamak için
previous_status = {
    "web": None,
    "app": None
}

async def get_web_status(url: str):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    return "online"
                else:
                    return "offline"
    except:
        return "offline"

async def get_app_status(url: str):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                text = await resp.text()
                text = text.strip().lower()
                if text == "up":
                    return "online"
                elif text == "down":
                    return "offline"
                elif text == "care":
                    return "bakim"
                else:
                    return "offline"
    except:
        return "offline"

def format_status_message(web_status, app_status):
    web_emoji = ONLINE if web_status == "online" else OFFLINE
    app_emoji = ONLINE if app_status == "online" else CARE if app_status == "bakim" else OFFLINE
    current_timestamp = int(time.time())
    message = (
        f"**:status: Sistem Durum Paneli**\n"
        f"Son Güncelleme: <t:{current_timestamp}:R>\n"
        "Aşağıda sistemlerimizin anlık durumunu görebilirsiniz.\n"
        f"**Web Sitesi Durumu:** {web_emoji} {web_status.capitalize()}\n"
        f"**Uygulama Durumu:** {app_emoji} {app_status.capitalize()}"
    )
    return message

async def update_status_message():
    global status_message_id, status_channel
    if status_channel is None:
        return

    web_url = "https://zoream.pages.dev"
    app_url = "https://raw.githubusercontent.com/WolfGames156/hidzor/refs/heads/main/stat1.txt"

    web_status = await get_web_status(web_url)
    app_status = await get_app_status(app_url)

    content = format_status_message(web_status, app_status)

    # Önceki durumdan farklıysa mesajı güncelle
    if previous_status["web"] != web_status or previous_status["app"] != app_status:
        previous_status["web"] = web_status
        previous_status["app"] = app_status

        if status_message_id:
            try:
                msg = await status_channel.fetch_message(status_message_id)
                await msg.edit(content=content)
            except discord.NotFound:
                msg = await status_channel.send(content)
                status_message_id = msg.id
        else:
            msg = await status_channel.send(content)
            status_message_id = msg.id

@tasks.loop(seconds=5)
async def check_status_loop():
    """Duruma göre kontrol aralığını ayarlayan döngü"""
    interval = CHECK_INTERVAL_UP if previous_status["web"] == "online" and previous_status["app"] == "online" else CHECK_INTERVAL_DOWN
    await update_status_message()
    check_status_loop.change_interval(seconds=interval)

@bot.event
async def on_ready():
    print(f"{bot.user} hazır.")

@bot.command()
async def status(ctx):
    global status_channel
    # Sadece adminler komutu kullanabilir
    if ctx.author.guild_permissions.administrator:
        status_channel = ctx.channel
        await ctx.send("Sistem durum paneli bu kanalda başlatıldı.")
        # Başlangıç durumu
        await update_status_message()
        check_status_loop.start()
    else:
        await ctx.send("Bu komutu kullanmak için admin olmalısınız.")

bot.run(TOKEN)
