import asyncio
import os

from aiohttp import web
from dotenv import load_dotenv
from telegram.ext import Application

from config import DISCORD_TOKEN, TELEGRAM_TOKEN
from database import init_db
from discord_bot import dc_client, is_discord_ready, set_tg_bot
from telegram_handlers import register_telegram_handlers

load_dotenv()


async def health_check(_request):
    return web.Response(text="Bot is running!")


async def start_web_server():
    port = os.environ.get("PORT")
    if not port:
        return None
    app = web.Application()
    app.router.add_get("/", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(port))
    await site.start()
    print(f"Health server on port {port}")
    return runner


async def wait_for_discord(timeout: float = 120.0):
    elapsed = 0.0
    while not is_discord_ready() and elapsed < timeout:
        await asyncio.sleep(0.5)
        elapsed += 0.5
    if not is_discord_ready():
        print("Warning: Discord did not become ready in time; continuing anyway.")


async def main():
    if not DISCORD_TOKEN or not TELEGRAM_TOKEN:
        raise SystemExit("Set DISCORD_TOKEN and TELEGRAM_TOKEN in .env")

    await init_db()
    await start_web_server()

    tg_app = Application.builder().token(TELEGRAM_TOKEN).build()
    register_telegram_handlers(tg_app)
    set_tg_bot(tg_app.bot)

    discord_task = asyncio.create_task(dc_client.start(DISCORD_TOKEN))
    await wait_for_discord()
    print("Discord bot ready.")

    await tg_app.initialize()
    await tg_app.start()
    await tg_app.bot.delete_webhook(drop_pending_updates=False)
    await tg_app.updater.start_polling(drop_pending_updates=False)
    print("Telegram bot started.")

    await discord_task


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
