import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import database

# This will be injected from main.py
send_to_discord_callback = None

INTERVIEW_QUESTIONS = [
    "1. Nammude group rules ningal mothathil vayichu nokkiyo?",
    "2. Ningalude muzhuvan peru enthanu? Ennitt ningalude prayam (age) onnu parayamo?",
    "3. Ithil ethavum mukhyapettathayi ningalkku thonnunnathu ethaanu? Entukondu?",
    "4. Rules 1 & 2 lamghichukondu aarenkilum group-il therivili parayukayo, athukellengil mattullavare DM cheyyan nirbandhikkukayo cheythal, ningal engane mathramayi aayirikkum athine handle cheyyuka?",
    "5. Rule 3, 5, 7 prakaram spam messages-um, anuvadamilathe ulla parasyangalum thadayunthil ningalude nilapaad enthanu? Oru verification illatha promotion kandu koodiyal ningal enthu nadapadi aayirikkum edukka?",
    "6. Group-il nadakkunna niyamalanghanangal sraddhayilpettal, athu report cheyyunathinum nadapadi edukunnathinum oru divasam ningalkku ethra neram samayam mathi aayirikkum?",
    "7. Nammude group-inte suraksha (security) kootunnathinum, member-skk vendi kooduthal nalla karyangal cheyyunnathinum ningalkku enthenkilum puthiya ideas undo?"
]

Q2, Q3, Q4, Q5, Q6, Q7 = range(6)

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
        f"Namaskaram {user.first_name}! Kanthari Commandilekku swagatham. Thazhe ulla options select cheyyuka:",
        reply_markup=reply_markup
    )

# --- CONVERSATION HANDLER LOGIC FOR ADMIN INTERVIEW ---

async def start_interview_q2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    username = query.from_user.username or query.from_user.first_name
    await database.get_or_create_user(user_id, username)
    
    if send_to_discord_callback:
        await send_to_discord_callback(user_id, username, 'Admin', f"**Q:** {INTERVIEW_QUESTIONS[0]}\n**A:** Yes")
        
    await query.edit_message_text(text="Nallathu! Adutha chodyam:\n\n" + INTERVIEW_QUESTIONS[1])
    return Q2

async def handle_q_generic(update: Update, step: int, next_state: int):
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    text = update.message.text
    
    if send_to_discord_callback:
        try:
            await send_to_discord_callback(user_id, username, 'Admin', f"**Q:** {INTERVIEW_QUESTIONS[step]}\n**A:** {text}")
        except Exception as e:
            import logging
            logging.error(f"Failed to forward answer to discord: {e}")
            
    if next_state == ConversationHandler.END:
        await update.message.reply_text("Interview theernnu! Admins udane marupadi nalkum.")
    else:
        await update.message.reply_text(INTERVIEW_QUESTIONS[step+1])
        
    return next_state

async def handle_q2(update: Update, context: ContextTypes.DEFAULT_TYPE): return await handle_q_generic(update, 1, Q3)
async def handle_q3(update: Update, context: ContextTypes.DEFAULT_TYPE): return await handle_q_generic(update, 2, Q4)
async def handle_q4(update: Update, context: ContextTypes.DEFAULT_TYPE): return await handle_q_generic(update, 3, Q5)
async def handle_q5(update: Update, context: ContextTypes.DEFAULT_TYPE): return await handle_q_generic(update, 4, Q6)
async def handle_q6(update: Update, context: ContextTypes.DEFAULT_TYPE): return await handle_q_generic(update, 5, Q7)
async def handle_q7(update: Update, context: ContextTypes.DEFAULT_TYPE): return await handle_q_generic(update, 6, ConversationHandler.END)

async def cancel_interview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Interview cancelled. Needing help? Try the menu.")
    return ConversationHandler.END

# --- NORMAL CALLBACK & MESSAGE HANDLING ---

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    username = query.from_user.username or query.from_user.first_name
    await database.get_or_create_user(user_id, username)
    
    data = query.data
    
    if data.startswith('rule_'):
        language = data.split('_')[1]
        rule_content = await database.get_rule(language)
        await query.edit_message_text(text=f"📜 **{language} Rules:**\n\n{rule_content}")
            
    elif data == 'admin_q1_no':
        await query.edit_message_text(text="Kshamikkuka, rules vayikkathe admin aavaan saadhikkilla. Dayaavayi rules vayichathinu shesham veendum sramikkuka.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    text = update.message.text
    
    await database.get_or_create_user(user_id, username)
    
    # 1. Menu commands
    if text == '📢 Support':
        await database.update_user_state(user_id, 'WAITING_FOR_COMPLAINT')
        await update.message.reply_text("Ningalude complaint enthanennu chodhikkuka.")
        return
        
    elif text == '🛡️ Admin Application':
        keyboard = [
            [InlineKeyboardButton("Yes", callback_data='admin_q1_yes'),
             InlineKeyboardButton("No", callback_data='admin_q1_no')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("🛡️ Admin aavanulla interview thudangukayanu.\n\n" + INTERVIEW_QUESTIONS[0], reply_markup=reply_markup)
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

    # 2. Check for active Support flow
    state = await database.get_user_state(user_id)
    if state == 'WAITING_FOR_COMPLAINT':
        if send_to_discord_callback:
            await send_to_discord_callback(user_id, username, 'Support', text)
        await database.update_user_state(user_id, 'IDLE')
        return

    # 3. Fallback message routing to existing Support channel
    support_channel = await database.get_discord_channel(user_id, 'Support')
    if support_channel:
        if send_to_discord_callback:
            await send_to_discord_callback(user_id, username, 'Support', text)
        return

    # If no support channel and no state
    await update.message.reply_text("Dayaavayi menuvil ninnum oru option select cheyyuka.")

async def send_to_telegram(app: Application, user_id: int, message: str):
    await app.bot.send_message(chat_id=user_id, text=message)

def setup_telegram_app(token: str):
    app = Application.builder().token(token).build()
    
    admin_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_interview_q2, pattern='^admin_q1_yes$')],
        states={
            Q2: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_q2)],
            Q3: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_q3)],
            Q4: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_q4)],
            Q5: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_q5)],
            Q6: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_q6)],
            Q7: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_q7)],
        },
        fallbacks=[CommandHandler('cancel', cancel_interview)]
    )
    
    app.add_handler(admin_conv_handler)
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return app
