from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from telegram.ext import ContextTypes
from templates.messages import Messages, ButtonLabels, CallbackData
from handlers.base_handler import BaseHandler
from services.user_service import UserService
from services.config_service import ConfigGenerator
from services.stats_service import TrafficStatsService
from services.singbox_service import SingBoxService
from utils.logger import logger
from config import Config


class UserHandlers(BaseHandler):
    """Handlers for regular user commands"""
    
    def __init__(self, user_service: UserService, config_generator: ConfigGenerator, stats_service: TrafficStatsService):
        self.user_service = user_service
        self.config_generator = config_generator
        self.stats_service = stats_service
    
    @staticmethod
    async def send_menu(bot, chat_id: int, user_id: int) -> None:
        """Send main menu to user"""
        keyboard = [
            [InlineKeyboardButton(ButtonLabels.MY_CONFIGS, callback_data=CallbackData.MY_CONFIGS)],
            [InlineKeyboardButton(ButtonLabels.MY_TRAFFIC, callback_data=CallbackData.MY_TRAFFIC)],
            [InlineKeyboardButton(ButtonLabels.CREATE_CONFIG, callback_data=CallbackData.CREATE_CONFIG)],
            [InlineKeyboardButton(ButtonLabels.SERVER_INFO, callback_data=CallbackData.SERVER_INFO)],
            [InlineKeyboardButton(ButtonLabels.HELP, callback_data=CallbackData.HELP)]
        ]
        
        if Config.is_admin(user_id):
            keyboard.insert(0, [
                InlineKeyboardButton(ButtonLabels.ADD_USER, callback_data=CallbackData.ADD_USER),
                InlineKeyboardButton(ButtonLabels.DELETE_USER, callback_data=CallbackData.DELETE_USER)
            ])
            # Две отдельные кнопки для админа
            keyboard.append([InlineKeyboardButton(ButtonLabels.USER_STATS, callback_data=CallbackData.USER_STATS)])
            keyboard.append([InlineKeyboardButton(ButtonLabels.USER_STATUS, callback_data=CallbackData.USER_STATUS)])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await bot.send_message(
            chat_id=chat_id,
            text=Messages.MENU,
            parse_mode='HTML',
            reply_markup=reply_markup
        )
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command"""
        user_id = self.get_user_id(update)
        chat_id = self.get_chat_id(update)
        await self.send_menu(context.bot, chat_id, user_id)
    
    async def menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /menu command"""
        user_id = self.get_user_id(update)
        chat_id = self.get_chat_id(update)
        await self.send_menu(context.bot, chat_id, user_id)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command"""
        help_text = Messages.get_help_text()
        
        if update.callback_query:
            query = update.callback_query
            await self.safe_edit_message(
                query,
                help_text,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(ButtonLabels.BACK, callback_data=CallbackData.BACK_TO_MENU)]
                ])
            )
        else:
            await update.message.reply_text(help_text, parse_mode='HTML')
    
    async def show_my_configs(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show user's configurations"""
        query = update.callback_query
        
        user_id = self.get_user_id(update)
        is_admin = await self.is_admin(update)
        
        users = await self.user_service.get_user_configs(user_id, is_admin)
        
        if not users:
            keyboard = [
                [InlineKeyboardButton(ButtonLabels.CREATE_CONFIG, callback_data=CallbackData.CREATE_CONFIG)],
                [InlineKeyboardButton(ButtonLabels.BACK, callback_data=CallbackData.BACK_TO_MENU)]
            ]
            await self.safe_edit_message(
                query,
                Messages.NO_CONFIGS,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
        
        keyboard = [
            [InlineKeyboardButton(f"📄 {user.name}", callback_data=f"{CallbackData.CONFIG_PREFIX}{user.name}")]
            for user in users
        ]
        keyboard.append([InlineKeyboardButton(ButtonLabels.BACK, callback_data=CallbackData.BACK_TO_MENU)])
        
        text = Messages.get_configs_list_message(is_admin)
        await self.safe_edit_message(
            query,
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def show_user_config(self, query: CallbackQuery, username: str, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show specific user configuration"""
        user_id = query.message.chat.id
        is_admin = Config.is_admin(user_id)
        
        if not is_admin:
            user = await self.user_service.get_user_by_telegram_id(user_id)
            if not user or user.name.lower() != username.lower():
                await self.safe_edit_message(query, Messages.ACCESS_DENIED)
                return
        
        user = await self.user_service.get_user_by_username(username)
        if not user:
            await self.safe_edit_message(query, Messages.USER_NOT_FOUND)
            return
        
        await self.send_client_config(query, context, user.name, user.uuid)
    
    async def send_client_config(self, query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, username: str, user_uuid: str) -> None:
        """Send client configuration to user"""
        context.user_data['current_config_user'] = username
        context.user_data['current_config_uuid'] = user_uuid
        
        keyboard = [
            [
                InlineKeyboardButton(ButtonLabels.ANDROID, callback_data=f"{CallbackData.CONFIG_ANDROID_PREFIX}{username}"),
                InlineKeyboardButton(ButtonLabels.IOS, callback_data=f"{CallbackData.CONFIG_IOS_PREFIX}{username}")
            ],
            [InlineKeyboardButton(ButtonLabels.BACK_TO_MENU, callback_data=CallbackData.BACK_TO_MENU)]
        ]
        
        await self.safe_edit_message(
            query,
            Messages.SELECT_PLATFORM,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def _can_access_config(self, user_id: int, username: str) -> bool:
        """Check whether the caller may access the requested config."""
        if Config.is_admin(user_id):
            return True

        user = await self.user_service.get_user_by_telegram_id(user_id)
        return bool(user and user.name.lower() == username.lower())
    
    async def send_config_by_platform(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send configuration for specific platform"""
        query = update.callback_query
        
        # Parse platform and username
        if query.data.startswith(CallbackData.CONFIG_ANDROID_PREFIX):
            platform = "android"
            username = query.data.replace(CallbackData.CONFIG_ANDROID_PREFIX, "")
        else:
            platform = "ios"
            username = query.data.replace(CallbackData.CONFIG_IOS_PREFIX, "")

        user_id = query.from_user.id
        if not await self._can_access_config(user_id, username):
            logger.warning(f"Unauthorized config access attempt by {user_id} for {username}")
            await self.safe_edit_message(query, Messages.ACCESS_DENIED)
            return
        
        logger.info(f"Sending config for username: {username}, platform: {platform}")
        
        # Get user from sing-box config
        singbox = self.user_service.singbox
        users = await singbox.load_users()
        
        user = None
        for u in users:
            if u.name == username:
                user = u
                break
        
        if not user:
            logger.error(f"User {username} not found")
            await query.message.edit_text(
                f"❌ Пользователь {username} не найден",
                parse_mode='HTML'
            )
            return
        
        # Generate config
        from models import Platform
        platform_enum = Platform.ANDROID if platform == "android" else Platform.IOS
        
        server_config = await singbox.get_server_config()
        self.config_generator.server = server_config
        
        client_config = self.config_generator.generate_client_config(
            user.name,
            user.uuid,
            platform_enum
        )
        
        # Save and send config file
        import time
        import json
        timestamp = int(time.time())
        config_file = Config.DATA_DIR / f"{user.name}_{platform}_{timestamp}.json"
        
        with open(config_file, 'w') as f:
            json.dump(client_config, f, indent=2, ensure_ascii=False)
        
        # Send document
        bot = context.bot
        chat_id = query.message.chat_id
        
        with open(config_file, 'rb') as f:
            await bot.send_document(
                chat_id=chat_id,
                document=f,
                filename=f"{user.name}_singbox_{platform}_{timestamp}.json",
                caption=Messages.get_config_caption(user.name, user.uuid),
                parse_mode='HTML'
            )
        
        # Generate and send QR code
        vless_link = self.config_generator.generate_vless_link(user.name, user.uuid)
        qr_image = ConfigGenerator.generate_qr_code(vless_link)
        
        await bot.send_photo(
            chat_id=chat_id,
            photo=qr_image,
            caption=Messages.get_qr_caption(user.name),
            parse_mode='HTML'
        )
        
        # Clean up
        config_file.unlink()
        
        # Send back button
        keyboard = [[InlineKeyboardButton(ButtonLabels.BACK_TO_MENU, callback_data=CallbackData.BACK_TO_MENU)]]
        await bot.send_message(
            chat_id=chat_id,
            text=Messages.CONFIG_SENT.format(username=user.name),
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def create_my_config(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Create new configuration for user"""
        query = update.callback_query
        
        user_id = self.get_user_id(update)
        username = update.effective_user.username or f"user_{user_id}"
    
        from utils.validators import UserValidator
        username = UserValidator.sanitize_username(username)
    
        logger.info(f"Create config request for user_id={user_id}, username={username}")
    
        # СНАЧАЛА ПРОВЕРЯЕМ - есть ли уже конфиг у этого пользователя?
        existing_username = await self.user_service.mapping.get_username(user_id)
        logger.info(f"Existing mapping for {user_id}: {existing_username}")
    
        if existing_username:
           # Проверяем, существует ли этот пользователь в конфиге sing-box
            singbox = self.user_service.singbox
            users = await singbox.load_users()
            existing_user = next((u for u in users if u.name.lower() == existing_username.lower()), None)
            
            if existing_user:
                logger.info(f"Found existing config for user {existing_username}, sending it")
                status_msg = await query.message.reply_text(
                    "📱 <b>У вас уже есть конфиг! Отправляю...</b>",
                    parse_mode='HTML'
                )
                await status_msg.delete()
            
                # Отправляем существующий конфиг
                server_config = await singbox.get_server_config()
                self.config_generator.server = server_config
                await self.send_client_config(query, context, existing_user.name, existing_user.uuid)
                return
            else:
                # Маппинг есть, но пользователя в конфиге нет - удаляем маппинг
                logger.warning(f"Mapping exists but user not found in config, deleting mapping")
                await self.user_service.mapping.delete_mapping(user_id)
    
        # Если дошли сюда - создаем нового пользователя
        logger.info(f"No existing config found, creating new user")
    
        status_msg = await query.message.reply_text(
            Messages.PROCESSING.format(action="создаем конфиг"),
            parse_mode='HTML'
        )
    
        success, error, user = await self.user_service.create_user(user_id, username)
    
        if not success:
            await status_msg.edit_text(
                Messages.OPERATION_FAILED.format(error=error),
                parse_mode='HTML'
            )
            return
    
        await status_msg.delete()
    
        singbox = self.user_service.singbox
        server_config = await singbox.get_server_config()
        self.config_generator.server = server_config
    
        await self.send_client_config(query, context, user.name, user.uuid)
        context.user_data.clear()
    
    async def show_my_traffic(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show user's traffic statistics"""
        query = update.callback_query
        
        user_id = self.get_user_id(update)
        user = await self.user_service.get_user_by_telegram_id(user_id)
        
        if not user:
            keyboard = [
                [InlineKeyboardButton(ButtonLabels.CREATE_CONFIG, callback_data=CallbackData.CREATE_CONFIG)],
                [InlineKeyboardButton(ButtonLabels.BACK, callback_data=CallbackData.BACK_TO_MENU)]
            ]
            await self.safe_edit_message(
                query,
                Messages.NO_CONFIGS,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
        
        stats = await self.stats_service.get_user_stats(user.name)
        
        if stats:
            text = Messages.get_traffic_message(
                user.name,
                stats.upload,
                stats.download,
                stats.total
            )
        else:
            text = Messages.NO_TRAFFIC.format(username=user.name)
        
        await self.safe_edit_message(
            query,
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(ButtonLabels.BACK, callback_data=CallbackData.BACK_TO_MENU)]
            ])
        )
    
    async def show_server_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show server information"""
        query = update.callback_query
        
        singbox = self.user_service.singbox
        server_config = await singbox.get_server_config()
        users = await singbox.load_users()
        
        text = Messages.get_server_info_message(
            server_config.domain,
            server_config.port,
            len(users)
        )
        
        await self.safe_edit_message(
            query,
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(ButtonLabels.BACK, callback_data=CallbackData.BACK_TO_MENU)]
            ])
        )
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle callback queries"""
        if not update.callback_query:
            return
        
        query = update.callback_query
        await query.answer()
        
        logger.info(f"Received callback data: {query.data}")
        
        if query.data == CallbackData.MY_CONFIGS:
            await self.show_my_configs(update, context)
        elif query.data == CallbackData.CREATE_CONFIG:
            await self.create_my_config(update, context)
        elif query.data == CallbackData.MY_TRAFFIC:
            await self.show_my_traffic(update, context)
        elif query.data == CallbackData.SERVER_INFO:
            await self.show_server_info(update, context)
        elif query.data == CallbackData.HELP:
            await self.help_command(update, context)
        elif query.data == CallbackData.BACK_TO_MENU:
            await self.menu(update, context)
        # Admin callbacks - перенаправляем в admin_handlers
        elif query.data in [CallbackData.USER_STATS, CallbackData.USER_STATUS]:
            # Эти callback обрабатываются в admin_handlers
            # Просто игнорируем здесь, они уже обработаны отдельным хендлером
            pass
        elif query.data.startswith(CallbackData.CONFIG_PREFIX) and not query.data.startswith(CallbackData.CONFIG_ANDROID_PREFIX) and not query.data.startswith(CallbackData.CONFIG_IOS_PREFIX):
            username = query.data.replace(CallbackData.CONFIG_PREFIX, "")
            await self.show_user_config(query, username, context)
        elif query.data.startswith(CallbackData.CONFIG_ANDROID_PREFIX) or query.data.startswith(CallbackData.CONFIG_IOS_PREFIX):
            await self.send_config_by_platform(update, context)
        else:
            logger.warning(f"Unknown callback data: {query.data}")
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle regular text messages"""
        if not update.message:
            return
        
        text = update.message.text.lower()
        
        if text == '/start':
            await self.start(update, context)
        elif text == '/menu':
            await self.menu(update, context)
        elif text == '/help':
            await self.help_command(update, context)
        else:
            await update.message.reply_text(
                "❓ Пожалуйста, используйте команды:\n"
                "/start - Главное меню\n"
                "/menu - Показать меню\n"
                "/help - Помощь",
                parse_mode='HTML'
            )
    
    async def show_id(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show user ID for debugging"""
        user_id = self.get_user_id(update)
        username = update.effective_user.username
        
        mapped_name = await self.user_service.mapping.get_username(user_id)
        users = await self.user_service.singbox.load_users()
        
        text = f"🆔 <b>Ваш ID:</b> <code>{user_id}</code>\n"
        text += f"👤 <b>Username:</b> @{username}\n"
        text += f"🔗 <b>Привязанный конфиг:</b> {mapped_name or 'Нет'}\n\n"
        text += "<b>Доступные конфиги:</b>\n"
        for u in users:
            text += f"• {u.name}\n"
        
        await update.message.reply_text(text, parse_mode='HTML')
