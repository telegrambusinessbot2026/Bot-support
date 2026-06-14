import os

from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")

DISCORD_GUILD_ID = int(os.getenv("DISCORD_GUILD_ID", "0") or "0")
DISCORD_ADMIN_ROLE_ID = int(os.getenv("DISCORD_ADMIN_ROLE_ID", "0") or "0")

SUPPORT_CATEGORY_NAME = os.getenv("SUPPORT_CATEGORY_NAME", "Support")
ADMIN_CATEGORY_NAME = os.getenv("ADMIN_CATEGORY_NAME", "Admin")
RULES_CATEGORY_NAME = os.getenv("RULES_CATEGORY_NAME", "Rules")

RULE_CHANNEL_NAMES = {
    "english": os.getenv("RULES_CHANNEL_ENGLISH", "english-rules"),
    "malayalam": os.getenv("RULES_CHANNEL_MALAYALAM", "malayalam-rules"),
    "hindi": os.getenv("RULES_CHANNEL_HINDI", "hindi-rules"),
    "manglish": os.getenv("RULES_CHANNEL_MANGLISH", "manglish-rules"),
}

INTERVIEW_STEPS = [
    "step_name",
    "step_age",
    "step_city",
    "step_telegram",
    "step_reason",
    "step_experience",
]
