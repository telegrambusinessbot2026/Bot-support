import asyncio
from dotenv import load_dotenv
import os
import logging

import database
from telegram_bot import setup_telegram_app
import telegram_bot
from discord_bot import setup_discord_bot
import discord_bot

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def main():
    load_dotenv()
    
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
    DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
    GUILD_ID_STR = os.getenv('DISCORD_GUILD_ID', '0')
    
    try:
        GUILD_ID = int(GUILD_ID_STR)
    except ValueError:
        GUILD_ID = 0
    
    if not TELEGRAM_TOKEN or not DISCORD_TOKEN:
        logger.error("TELEGRAM_TOKEN or DISCORD_TOKEN is missing in .env file.")
        return

    # Initialize the database
    await database.init_db()
    
    # Initialize Bots
    telegram_app = setup_telegram_app(TELEGRAM_TOKEN)
    discord_client = setup_discord_bot(GUILD_ID)
    
    # Wire the callbacks
    async def send_to_discord(user_id: int, username: str, category_name: str, text: str):
        await discord_client.send_from_telegram(user_id, username, category_name, text)
        
    async def send_to_telegram(user_id: int, text: str):
        await telegram_bot.send_to_telegram(telegram_app, user_id, text)
        
    telegram_bot.send_to_discord_callback = send_to_discord
    discord_bot.send_to_telegram_callback = send_to_telegram
    
    # Start telegram bot manually instead of run_polling() to share event loop
    await telegram_app.initialize()
    await telegram_app.start()
    await telegram_app.updater.start_polling()
    logger.info("Telegram Bot started.")
    
    # Start discord bot (this blocks until stopped)
    try:
        logger.info("Starting Discord Bot...")
        await discord_client.start(DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info("Stopping bots...")
    finally:
        await telegram_app.updater.stop()
        await telegram_app.stop()
        await telegram_app.shutdown()
        await discord_client.close()

if __name__ == '__main__':
    # Need to run asyncio gracefully on Windows for discord.py
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
