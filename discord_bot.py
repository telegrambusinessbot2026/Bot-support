import discord
from discord import app_commands
import logging
import database
import time
import datetime

logger = logging.getLogger(__name__)

# Configuration Variables
DISCORD_ADMIN_ROLE_ID = 123456789012345678  # TODO: Replace with actual
EXTERNAL_LOG_CHANNEL_ID = 123456789012345678 # TODO: Replace with actual

# Injected from main.py
send_to_telegram_callback = None
set_telegram_permissions_callback = None

async def update_leaderboard(guild: discord.Guild):
    mgmt = discord.utils.get(guild.categories, name="Management")
    if not mgmt: return
    lb_ch = discord.utils.get(mgmt.channels, name="admin-leaderboard")
    if not lb_ch:
        lb_ch = await guild.create_text_channel('admin-leaderboard', category=mgmt)
        
    times = await database.get_all_admin_times()
    
    board = "🏆 **Admin Duty Leaderboard** 🏆\n\n"
    for dc_id, total_sec in times:
        member = guild.get_member(dc_id)
        name = member.display_name if member else f"User {dc_id}"
        hours, remainder = divmod(int(total_sec), 3600)
        minutes, _ = divmod(remainder, 60)
        board += f"```\n[Name]: {name}\n[User ID]: {dc_id}\n[Total Time Served/Duration]: {hours} Hours, {minutes} Minutes\n```\n"
        
    await lb_ch.purge(limit=10)
    await lb_ch.send(board)

class DutyToggleView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🟢 On Duty", style=discord.ButtonStyle.success, custom_id="btn_on_duty")
    async def on_duty(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        tg_id = await database.get_telegram_id_from_discord(user_id)
        if not tg_id:
            return await interaction.response.send_message("You must link your Telegram account first using !link in #account-linking.", ephemeral=True)
            
        role = interaction.guild.get_role(DISCORD_ADMIN_ROLE_ID)
        if role:
            try:
                await interaction.user.add_roles(role)
            except Exception as e:
                logger.error(f"Failed to add role: {e}")
                
        if set_telegram_permissions_callback:
            success = await set_telegram_permissions_callback(tg_id, True)
            if not success:
                logger.error("Failed to grant Telegram permissions.")
                
        await database.start_admin_session(user_id, time.time())
        
        mgmt = discord.utils.get(interaction.guild.categories, name="Management")
        if mgmt:
            log_ch = discord.utils.get(mgmt.channels, name="on-duty-logs")
            if not log_ch:
                log_ch = await interaction.guild.create_text_channel('on-duty-logs', category=mgmt)
            out = (f"```\n[Name]: {interaction.user.display_name}\n"
                   f"[User ID]: {user_id}\n"
                   f"[Duty Started At]: <t:{int(time.time())}:F>\n```")
            await log_ch.send(out)
            
        await interaction.response.send_message("You are now On Duty. Telegram Permissions granted and Discord Role assigned.", ephemeral=True)

    @discord.ui.button(label="🔴 Off Duty", style=discord.ButtonStyle.danger, custom_id="btn_off_duty")
    async def off_duty(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        tg_id = await database.get_telegram_id_from_discord(user_id)
        
        role = interaction.guild.get_role(DISCORD_ADMIN_ROLE_ID)
        if role:
            try:
                await interaction.user.remove_roles(role)
            except Exception as e:
                logger.error(f"Failed to remove role: {e}")
                
        if tg_id and set_telegram_permissions_callback:
            await set_telegram_permissions_callback(tg_id, False)
            
        now = time.time()
        total_sec = await database.end_admin_session(user_id, now)
        if total_sec is None:
            return await interaction.response.send_message("You are not currently on duty.", ephemeral=True)
            
        hours, remainder = divmod(int(total_sec), 3600)
        minutes, _ = divmod(remainder, 60)
        
        mgmt = discord.utils.get(interaction.guild.categories, name="Management")
        if mgmt:
            log_ch = discord.utils.get(mgmt.channels, name="off-duty-logs")
            if not log_ch:
                log_ch = await interaction.guild.create_text_channel('off-duty-logs', category=mgmt)
            out = (f"```\n[Name]: {interaction.user.display_name}\n"
                   f"[User ID]: {user_id}\n"
                   f"[Total Time Served/Duration]: {hours} Hours, {minutes} Minutes\n```")
            await log_ch.send(out)
            
        await update_leaderboard(interaction.guild)
        await interaction.response.send_message(f"You are now Off Duty. Logged {hours}h {minutes}m.", ephemeral=True)

class SupportLogView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def get_user_id_from_embed(self, message: discord.Message):
        if message.embeds:
            desc = message.embeds[0].description
            for line in desc.split('\n'):
                if "Telegram User ID:" in line:
                    return int(line.split(":")[1].strip())
        return None

    @discord.ui.button(label="Delete Channel", style=discord.ButtonStyle.danger, custom_id="sup_log_delete_channel")
    async def delete_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = await self.get_user_id_from_embed(interaction.message)
        if not user_id: 
            return await interaction.response.send_message("Could not find user ID.", ephemeral=True)
            
        ch_id = await database.get_discord_channel(user_id, 'Support')
        if ch_id:
            ch = interaction.guild.get_channel(ch_id)
            if ch:
                await ch.delete(reason="Admin requested deletion via Log button.")
            await database.delete_channel_mapping(ch_id)
            await interaction.response.send_message("Support Channel deleted and unmapped.", ephemeral=True)
        else:
            await interaction.response.send_message("No active Support channel found for this user.", ephemeral=True)

    @discord.ui.button(label="Support Feedback", style=discord.ButtonStyle.success, custom_id="sup_log_send_feedback")
    async def send_feedback(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = await self.get_user_id_from_embed(interaction.message)
        if not user_id: return
        if send_to_telegram_callback:
            await send_to_telegram_callback(user_id, "✅ Ningalude support ticket resolve cheythittund. Ee sevanathe kurichulla abhiprayam ariyikkuka!")
        await interaction.response.send_message("Support Feedback request sent to Telegram.", ephemeral=True)


class AdminLogView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def get_user_id_from_embed(self, message: discord.Message):
        if message.embeds:
            desc = message.embeds[0].description
            for line in desc.split('\n'):
                if "Telegram User ID:" in line:
                    return int(line.split(":")[1].strip())
        return None

    @discord.ui.button(label="Delete Channel", style=discord.ButtonStyle.danger, custom_id="adm_log_delete_channel")
    async def delete_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = await self.get_user_id_from_embed(interaction.message)
        if not user_id: 
            return await interaction.response.send_message("Could not find user ID.", ephemeral=True)
            
        ch_id = await database.get_discord_channel(user_id, 'Admin')
        if ch_id:
            ch = interaction.guild.get_channel(ch_id)
            if ch:
                await ch.delete(reason="Admin requested deletion via Log button.")
            await database.delete_channel_mapping(ch_id)
            await interaction.response.send_message("Admin Channel deleted and unmapped.", ephemeral=True)
        else:
            await interaction.response.send_message("No active Admin channel found for this user.", ephemeral=True)

    @discord.ui.button(label="Admin Feedback", style=discord.ButtonStyle.success, custom_id="adm_log_send_feedback")
    async def send_feedback(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = await self.get_user_id_from_embed(interaction.message)
        if not user_id: return
        if send_to_telegram_callback:
            await send_to_telegram_callback(user_id, "🛡️ Ningalude admin application interview poorntiyayi. Njangalude theerumanam udane ariyikkum. Abhiprayangal undo?")
        await interaction.response.send_message("Admin Feedback request sent to Telegram.", ephemeral=True)


class KanthariDiscordBot(discord.Client):
    def __init__(self, guild_id: int):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        super().__init__(intents=intents)
        self.target_guild_id = guild_id
        self.tree = app_commands.CommandTree(self)
        
    async def setup_hook(self):
        self.add_view(SupportLogView())
        self.add_view(AdminLogView())
        self.add_view(DutyToggleView())
        
        guild = discord.Object(id=self.target_guild_id)
        
        @self.tree.command(name="link_account", description="Link a Telegram ID to a Discord ID", guild=guild)
        @app_commands.describe(telegram_id="The Telegram User ID", discord_id="The Discord User ID")
        async def link_account(interaction: discord.Interaction, telegram_id: str, discord_id: str):
            if interaction.channel.name != 'account-linking':
                return await interaction.response.send_message("This command can only be used in #account-linking.", ephemeral=True)
            try:
                tg_id = int(telegram_id)
                dc_id = int(discord_id)
                await database.link_account(tg_id, dc_id)
                await interaction.response.send_message(f"Successfully linked Telegram ID {tg_id} to Discord ID {dc_id}.")
            except ValueError:
                await interaction.response.send_message("IDs must be numbers.", ephemeral=True)

        @self.tree.command(name="member_info", description="Get join date and duration of a user", guild=guild)
        @app_commands.describe(user_id="The Telegram User ID to search for")
        async def member_info(interaction: discord.Interaction, user_id: str):
            if interaction.channel.name != 'member-info':
                return await interaction.response.send_message("This command can only be used in #member-info.", ephemeral=True)
                
            await interaction.response.defer()
            join_log_ch = self.get_channel(EXTERNAL_LOG_CHANNEL_ID)
            if not join_log_ch:
                return await interaction.followup.send("Error: EXTERNAL_LOG_CHANNEL_ID is not configured correctly.")
            
            found = False
            async for log_msg in join_log_ch.history(limit=5000):
                if user_id in log_msg.content:
                    found = True
                    join_time = log_msg.created_at
                    now = discord.utils.utcnow()
                    diff = now - join_time
                    days = diff.days
                    hours, remainder = divmod(diff.seconds, 3600)
                    minutes, _ = divmod(remainder, 60)
                    
                    out = (f"```\n[Name]: {user_id}\n"
                           f"[User ID]: {user_id}\n"
                           f"[Joined At]: {join_time.strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
                           f"[Total Time Served/Duration]: {days} Days, {hours} Hours, {minutes} Minutes\n```")
                    await interaction.followup.send(out)
                    break
            
            if not found:
                await interaction.followup.send(f"Could not find any join logs for user {user_id} in the external channel.")

        await self.tree.sync(guild=guild)

    async def on_ready(self):
        logger.info(f'Logged in as {self.user}')
        guild = self.get_guild(self.target_guild_id)
        if not guild:
            if self.guilds:
                guild = self.guilds[0]
                self.target_guild_id = guild.id
            else:
                logger.error("Bot is not in any guilds!")
                return
                
        logger.info(f"Operating in guild: {guild.name}")
        
        categories = {'Support': None, 'Admin': None, 'Rules': None, 'Management': None}
        for cat in guild.categories:
            if cat.name in categories:
                categories[cat.name] = cat
                
        for name, cat in categories.items():
            if not cat:
                categories[name] = await guild.create_category(name)
                
        mgmt_category = categories['Management']
        mgmt_channels = ['support-logs', 'admin-logs', 'on-duty-logs', 'off-duty-logs', 'admin-leaderboard', 'duty-toggle', 'account-linking', 'member-info', 'bot-commands']
        
        for ch_name in mgmt_channels:
            ch = discord.utils.get(mgmt_category.channels, name=ch_name)
            if not ch:
                await guild.create_text_channel(ch_name, category=mgmt_category)
                
        # Setup duty toggle buttons
        duty_ch = discord.utils.get(mgmt_category.channels, name='duty-toggle')
        if duty_ch:
            await duty_ch.purge(limit=10)
            await duty_ch.send("Toggle your Admin Duty status here:", view=DutyToggleView())
            
        # Setup bot commands
        cmd_ch = discord.utils.get(mgmt_category.channels, name='bot-commands')
        if cmd_ch:
            await cmd_ch.purge(limit=10)
            embed = discord.Embed(title="Bot Commands", description="Here are the available Slash Commands:", color=discord.Color.blue())
            embed.add_field(name="/link_account <telegram_id> <discord_id>", value="Link an admin's Telegram account to their Discord account. Run this in `#account-linking`.", inline=False)
            embed.add_field(name="/member_info <user_id>", value="Get the join date and duration of a user from the external join log. Run this in `#member-info`.", inline=False)
            await cmd_ch.send(embed=embed)
            
        rule_langs = ['English', 'Malayalam', 'Hindi', 'Manglish']
        rules_category = categories['Rules']
        for lang in rule_langs:
            channel = discord.utils.get(rules_category.channels, name=lang.lower())
            if not channel:
                channel = await guild.create_text_channel(lang.lower(), category=rules_category)
            messages = [message async for message in channel.history(limit=1)]
            if messages:
                await database.update_rule(lang, messages[0].content)
            else:
                await database.update_rule(lang, f"No rules posted yet in #{channel.name}")

    async def on_message(self, message: discord.Message):
        if message.author == self.user:
            return
            
        if not isinstance(message.channel, discord.TextChannel):
            return
            
        # Rule updates
        if message.channel.category and message.channel.category.name == 'Rules':
            language = message.channel.name.capitalize()
            if language in ['English', 'Malayalam', 'Hindi', 'Manglish']:
                await database.update_rule(language, message.content)
                logger.info(f"Updated cached rule for {language}")
                await message.channel.send("Rule successfully updated and synced to the bot.")
                return
            
        # Forward admin replies
        user_id = await database.get_telegram_user_from_channel(message.channel.id)
        if user_id and send_to_telegram_callback:
            await send_to_telegram_callback(user_id, message.content)

    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if after.author == self.user:
            return
            
        if not isinstance(after.channel, discord.TextChannel):
            return
            
        if after.channel.category and after.channel.category.name == 'Rules':
            language = after.channel.name.capitalize()
            if language in ['English', 'Malayalam', 'Hindi', 'Manglish']:
                await database.update_rule(language, after.content)
                logger.info(f"Updated cached rule for {language} via edit")
                await after.channel.send("Rule successfully updated and synced to the bot.")

    async def send_from_telegram(self, user_id: int, username: str, category_name: str, text: str):
        guild = self.get_guild(self.target_guild_id)
        if not guild:
            return
            
        channel_id = await database.get_discord_channel(user_id, category_name)
        channel = None
        
        if channel_id:
            channel = guild.get_channel(channel_id)
            
        if not channel:
            category = discord.utils.get(guild.categories, name=category_name)
            if not category:
                category = await guild.create_category(category_name)
                
            import re
            clean_name = re.sub(r'[^a-z0-9-]', '', username.lower())
            if not clean_name:
                clean_name = "user"
                
            channel_name = f"{clean_name}-{user_id}"
            
            try:
                channel = await guild.create_text_channel(channel_name, category=category)
                await database.save_channel_mapping(user_id, channel.id, category_name)
            except Exception as e:
                logger.error(f"DEBUG: Failed to create channel '{channel_name}' for user {user_id}. Reason: {e}")
                print(f"DEBUG ERROR: Failed to create channel. Reason: {e}")
                if category_name == 'Support' and send_to_telegram_callback:
                    await send_to_telegram_callback(user_id, "Channel create cheyyan pattiyailla. Admins-odu parayuka.")
                return
            
            log_ch_name = f"{category_name.lower()}-logs"
            mgmt_cat = discord.utils.get(guild.categories, name="Management")
            log_ch = discord.utils.get(mgmt_cat.channels, name=log_ch_name) if mgmt_cat else None
            if log_ch:
                embed = discord.Embed(title=f"New {category_name} Request", color=discord.Color.green())
                embed.description = f"User Name: {username}\nTelegram User ID: {user_id}\nChannel: <#{channel.id}>"
                view = SupportLogView() if category_name == 'Support' else AdminLogView()
                await log_ch.send(embed=embed, view=view)
                
            if category_name == 'Support' and send_to_telegram_callback:
                await send_to_telegram_callback(user_id, "Ningalude ticket create aayittundu! Ningalukku admin-umayi bandhapendan ivide vannu samsarikkunnathaanu.")
            
        await channel.send(f"**From {username}:**\n{text}")

def setup_discord_bot(guild_id: int):
    return KanthariDiscordBot(guild_id)
