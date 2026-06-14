"""Manglish UI strings for Kanthari Command Telegram interactions."""

from config import BOT_NAME

WELCOME = (
    f"Welcome to {BOT_NAME}! 👋\n\n"
    "Njan Telegram-um Discord-um connect cheyyunna support bot aanu.\n"
    "Thazhe ulla button use cheythu ninte option select cheyyu:"
)

BTN_SUPPORT = "📢 Support"
BTN_ADMIN = "🛡️ Admin Application"
BTN_RULES = "📜 Rules"
BTN_BACK = "⬅️ Back"

SUPPORT_READY = (
    "Super! Ninte Support channel ready aanu. ✅\n\n"
    "Complaint workflow start cheythu — ninte issue detail aayi type cheyy.\n"
    "Admin team Discord-il real-time kaanum."
)
SUPPORT_EXISTING = (
    "Ninte Support channel already undu. ✅\n\n"
    "Complaint continue cheyyam — message type cheythal admin team kanum."
)

ADMIN_CHANNEL_READY = (
    "Admin application channel create cheythu. ✅\n"
    "Interview start cheyyunnu — questions answer cheyyu."
)
ADMIN_CHANNEL_EXISTING = (
    "Ninte Admin channel already undu. ✅\n"
    "Interview continue cheyyam."
)

RULES_PICK_LANGUAGE = "Rules evide language-il venum? Select cheyyu 👇"

RULES_LANG_LABELS = {
    "english": "English",
    "malayalam": "Malayalam",
    "hindi": "Hindi",
    "manglish": "Manglish",
}

RULES_EMPTY = "Sorry bro, ee language-il rules ippol available alla. Admin update cheyyum."
RULES_SENT_PREFIX = "📜 Rules ({language}):\n\n"

INTERVIEW_QUESTIONS = {
    "step_name": "Step 1/6: Ninte full name parayu 📝",
    "step_age": "Step 2/6: Ninte age ethra aanu? 🔢",
    "step_city": "Step 3/6: Ninte city/location parayu 📍",
    "step_telegram": "Step 4/6: Ninte Telegram username confirm cheyyu (e.g. @username) 💬",
    "step_reason": "Step 5/6: Admin aakan enthu aanu reason? 🤔",
    "step_experience": "Step 6/6: Previous admin/moderation experience undo? Parayu 💼",
}

INTERVIEW_COMPLETE = (
    "Thank you bro! 🎉\n\n"
    "Ninte admin application submit cheythu. Team review cheythu contact cheyyum.\n"
    "Ippo message type cheythal admin channel-il poyikum."
)

USE_MENU_FIRST = "Menu use cheythu Support or Admin select cheyyu bro."

INVALID_AGE = "Valid number type cheyyu bro (e.g. 21)."

DISCORD_NOT_READY = "Discord connect aayilla bro. Admin contact cheyyu."
