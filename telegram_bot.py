import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import database

# This will be injected from main.py
send_to_discord_callback = None

INTERVIEW_QUESTIONS = [
    "1. Ningalude peru enthanu?",
    "2. Ningalude vayas etra aanu?",
    "3. Admin aavanulla karanam enthanu?",
    "4. Munp ethengilum serveril admin aayittundo?",
    "5. Oru issue vannal engane handle cheyyum?",
    "6. Ningalude timezone ethanu?"
]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await database.get_or_create_user(user.id, user.username or user.first_name)
    await database.update_user_state(user.id, 'IDLE')
    
    keyboard = [
        [InlineKeyboardButton("📢 Support", callback_data='btn_support')],
        [InlineKeyboardButton("🛡️ Admin Application", callback_data='btn_admin')],
        [InlineKeyboardButton("📜 Rules", callback_data='btn_rules')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"Namaskaram {user.first_name}! Kanthari Commandilekku swagatham. Thazhe ulla options select cheyyuka:",
        reply_markup=reply_markup
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data == 'btn_support':
        await database.update_user_state(user_id, 'SUPPORT')
        await query.edit_message_text(text="📢 Ningalude prashnam enthanu? Thazhe type cheyyuka. Njagalude admins udane marupadi nalkum.")
        
    elif data == 'btn_admin':
        await database.update_user_state(user_id, 'ADMIN_STEP_0')
        await query.edit_message_text(text="🛡️ Admin aavanulla interview thudangukayanu. " + INTERVIEW_QUESTIONS[0])
        
    elif data == 'btn_rules':
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
        await query.edit_message_text(text="📜 Etha language vendath?", reply_markup=reply_markup)
        
    elif data.startswith('rule_'):
        language = data.split('_')[1]
        rule_content = await database.get_rule(language)
        await query.edit_message_text(text=f"📜 **{language} Rules:**\n\n{rule_content}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    text = update.message.text
    
    state = await database.get_user_state(user_id)
    
    if state == 'IDLE':
        await update.message.reply_text("Dayaavayi /start upayogich menu select cheyyuka.")
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
