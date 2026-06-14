import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import database

# This will be injected from main.py
send_to_discord_callback = None

INTERVIEW_QUESTIONS = [
    "1. (Yes/No)"
    "2. Basic Details: Ningalude muzhuvan peru enthanu? Ennitt ningalude prayam (age) onnu parayamo?",
    "3. Priority Rules: Ithil ethavum mukhyapettathayi ningalkku thonnunnathu ethaanu? Entukondu?",
    "4. Handling Misbehavior: Rules 1 & 2 lamghichukondu aarenkilum group-il therivili parayukayo, athukellengil mattullavare DM cheyyan nirbandhikkukayo cheythal, ningal engane mathramayi aayirikkum athine handle cheyyuka?",
    "5. Spam & Promotion: Rule 3, 5, 7 prakaram spam messages-um, anuvadamilathe ulla parasyangalum thadayunthil ningalude nilapaad enthanu? Oru verification illatha promotion kandu koodiyal ningal enthu nadapadi aayirikkum edukka?",
    "6. Responsibility: Group-il nadakkunna niyamalanghanangal sraddhayilpettal, athu report cheyyunathinum nadapadi edukunnathinum oru divasam ningalkku ethra neram samayam mathi aayirikkum?",
    "7. New Ideas: Nammude group-inte suraksha (security) kootunnathinum, member-skk vendi kooduthal nalla karyangal cheyyunnathinum ningalkku enthenkilum puthiya ideas undo?"
]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await database.get_or_create_user(user.id, user.username or user.first_name)
    await database.update_user_state(user.id, 'IDLE')
    
    keyboard = [
        ["📢 Support", "🛡️ Admin Application"],
        ["📜 Rules"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        f"Namaskaram {user.first_name}! Kanthari support teamine contact cheythathinnu nanni. Ningalkku njan enthu help cheyyatte? Please adiyilulla listil ninnu correct option select cheyyoo.",
        reply_markup=reply_markup
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data.startswith('rule_'):
        language = data.split('_')[1]
        rule_content = await database.get_rule(language)
        await query.edit_message_text(text=f"📜 **{language} Rules:**\n\n{rule_content}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    text = update.message.text
    
    if text == '📢 Support':
        await database.update_user_state(user_id, 'SUPPORT')
        await update.message.reply_text("📢 Ningalude support ticket create aayittund! Ningalkku enthaanu adminnod parayanullathu, athu ivide parayavunnathaanu.")
        return
        
    elif text == '🛡️ Admin Application':
        await database.update_user_state(user_id, 'ADMIN_STEP_0')
        await update.message.reply_text("🛡️ Rules Confirmation: Nammude group rules ningal mothathil vayichu nokkiyo? " + INTERVIEW_QUESTIONS[0])
        return
        
    elif text == '📜 Rules':
        keyboard = [
            [
                InlineKeyboardButton("English", callback_data='rule_English'),
                InlineKeyboardButton("Malayalam", callback_data='rule_Malayalam')
            ],
            [
                InlineKeyboardButton("Hindi", callback_data='rule_Hindi'),
                InlineKeyboardButton("Manglish", callback_data='rule_Manglish')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("📜 Etha language vendath?", reply_markup=reply_markup)
        return
        
    state = await database.get_user_state(user_id)
    
    if state == 'IDLE':
        await update.message.reply_text("Dayaavayi menuvil ninnum oru option select cheyyuka.")
        return
        
    elif state == 'SUPPORT':
        # Send to discord support channel
        if send_to_discord_callback:
            await send_to_discord_callback(user_id, username, 'Support', text)
            
    elif state.startswith('ADMIN_STEP_'):
        step = int(state.split('_')[2])
        
        # Send their answer to the discord admin channel
        if send_to_discord_callback:
            await send_to_discord_callback(user_id, username, 'Admin', f"**Q:** {INTERVIEW_QUESTIONS[step]}\n**A:** {text}")
        
        next_step = step + 1
        if next_step < len(INTERVIEW_QUESTIONS):
            await database.update_user_state(user_id, f'ADMIN_STEP_{next_step}')
            await update.message.reply_text(INTERVIEW_QUESTIONS[next_step])
        else:
            await database.update_user_state(user_id, 'ADMIN_DONE')
            await update.message.reply_text("Interview theernnu! Admins udane marupadi nalkum.")
            
    elif state == 'ADMIN_DONE':
        # Send followups to admin channel
        if send_to_discord_callback:
            await send_to_discord_callback(user_id, username, 'Admin', text)

async def send_to_telegram(app: Application, user_id: int, message: str):
    await app.bot.send_message(chat_id=user_id, text=message)

def setup_telegram_app(token: str):
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return app
