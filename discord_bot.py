import discord
import logging
import database

logger = logging.getLogger(__name__)

# Injected from main.py
send_to_telegram_callback = None

class LogView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def get_user_id_from_embed(self, message: discord.Message):
        if message.embeds:
            desc = message.embeds[0].description
            for line in desc.split('\n'):
                if "Telegram User ID:" in line:
                    return int(line.split(":")[1].strip())
        return None

    @discord.ui.button(label="Delete Channel", style=discord.ButtonStyle.danger, custom_id="log_delete_channel")
    async def delete_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = await self.get_user_id_from_embed(interaction.message)
        if not user_id: 
            return await interaction.response.send_message("Could not find user ID.", ephemeral=True)
            
        ch_id = await database.get_discord_channel(user_id, 'Support')
        if not ch_id:
            ch_id = await database.get_discord_channel(user_id, 'Admin')
            
        if ch_id:
            ch = interaction.guild.get_channel(ch_id)
            if ch:
                await ch.delete(reason="Admin requested deletion via Log button.")
            await database.delete_channel_mapping(ch_id)
            await interaction.response.send_message("Channel deleted and unmapped.", ephemeral=True)
        else:
            await interaction.response.send_message("No active channel found for this user.", ephemeral=True)

    @discord.ui.button(label="Feedback/Resolution", style=discord.ButtonStyle.success, custom_id="log_send_feedback")
    async def send_feedback(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = await self.get_user_id_from_embed(interaction.message)
        if not user_id: return
        if send_to_telegram_callback:
            await send_to_telegram_callback(user_id, "✅ Ningalude issue pariharichittund. Abhiprayam ariyikkuka!")
        await interaction.response.send_message("Feedback requested sent to Telegram.", ephemeral=True)

    @discord.ui.button(label="Check Status", style=discord.ButtonStyle.primary, custom_id="log_check_status")
    async def check_status(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = await self.get_user_id_from_embed(interaction.message)
        if not user_id: return
        if send_to_telegram_callback:
            await send_to_telegram_callback(user_id, "⏳ Ningalude issue/interview status njangal check cheyyukayanu. Dayavayi kaathirikkuka.")
        await interaction.response.send_message("Status inquiry sent to Telegram.", ephemeral=True)

class KanthariDiscordBot(discord.Client):
    def __init__(self, guild_id: int):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        super().__init__(intents=intents)
        self.target_guild_id = guild_id
        
    async def setup_hook(self):
        self.add_view(LogView())

    async def on_ready(self):
        logger.info(f'Logged in as {self.user}')
        guild = self.get_guild(self.target_guild_id)
        if not guild:
            # Fallback to the first guild if specific ID is not found or not set
            if self.guilds:
                guild = self.guilds[0]
                self.target_guild_id = guild.id
            else:
                logger.error("Bot is not in any guilds!")
                return
                
        logger.info(f"Operating in guild: {guild.name}")
        
        # Ensure categories exist
        categories = {
            'Support': None,
            'Admin': None,
            'Rules': None,
            'Management': None
        }
        
        for cat in guild.categories:
            if cat.name in categories:
                categories[cat.name] = cat
                
        for name, cat in categories.items():
            if not cat:
                categories[name] = await guild.create_category(name)
                logger.info(f"Created category: {name}")
                
        # Ensure log channels exist
        mgmt_category = categories['Management']
        for log_ch in ['support-logs', 'admin-logs']:
            ch = discord.utils.get(mgmt_category.channels, name=log_ch)
            if not ch:
                await guild.create_text_channel(log_ch, category=mgmt_category)
                logger.info(f"Created log channel: {log_ch}")
                
        # Ensure rules channels exist and fetch rules
        rule_langs = ['English', 'Malayalam', 'Hindi', 'Manglish']
        rules_category = categories['Rules']
        
        for lang in rule_langs:
            channel = discord.utils.get(rules_category.channels, name=lang.lower())
            if not channel:
                channel = await guild.create_text_channel(lang.lower(), category=rules_category)
                logger.info(f"Created rules channel: {lang}")
            
            # Fetch rule from channel
            messages = [message async for message in channel.history(limit=1)]
            if messages:
                rule_text = messages[0].content
                await database.update_rule(lang, rule_text)
            else:
                await database.update_rule(lang, f"No rules posted yet in #{channel.name}")
                
    async def on_message(self, message: discord.Message):
        if message.author == self.user:
            return
            
        # Ignore messages not in text channels
        if not isinstance(message.channel, discord.TextChannel):
            return
            
        # Check if the channel is mapped to a telegram user
        user_id = await database.get_telegram_user_from_channel(message.channel.id)
        if user_id and send_to_telegram_callback:
            # Forward the admin's message back to telegram user
            await send_to_telegram_callback(user_id, message.content)

    async def send_from_telegram(self, user_id: int, username: str, category_name: str, text: str):
        guild = self.get_guild(self.target_guild_id)
        if not guild:
            return
            
        # Check if channel exists
        channel_id = await database.get_discord_channel(user_id, category_name)
        channel = None
        
        if channel_id:
            channel = guild.get_channel(channel_id)
            
        if not channel:
            # Create channel
            category = discord.utils.get(guild.categories, name=category_name)
            if not category:
                category = await guild.create_category(category_name)
                
            channel_name = f"{category_name.lower()}-{username.lower()}"
            channel = await guild.create_text_channel(channel_name, category=category)
            await database.save_channel_mapping(user_id, channel.id, category_name)
            
            # Post to log channel
            log_ch_name = f"{category_name.lower()}-logs"
            mgmt_cat = discord.utils.get(guild.categories, name="Management")
            log_ch = discord.utils.get(mgmt_cat.channels, name=log_ch_name) if mgmt_cat else None
            if log_ch:
                embed = discord.Embed(title=f"New {category_name} Request", color=discord.Color.green())
                embed.description = f"User Name: {username}\nTelegram User ID: {user_id}\nChannel: <#{channel.id}>"
                await log_ch.send(embed=embed, view=LogView())
            
        # Send message
        await channel.send(f"**From {username}:**\n{text}")

def setup_discord_bot(guild_id: int):
    return KanthariDiscordBot(guild_id)
