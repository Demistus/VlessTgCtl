from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from templates.messages import Messages, ButtonLabels, CallbackData
from handlers.base_handler import BaseHandler
from services.user_service import UserService
from services.config_service import ConfigGenerator
from services.stats_service import TrafficStatsService
from services.singbox_service import SingBoxService
from utils.formatters import format_bytes
from utils.validators import UserValidator
from utils.logger import logger
from config import Config


class AdminHandlers(BaseHandler):
    """Handlers for admin commands"""
    
    def __init__(
        self,
        user_service: UserService,
        stats_service: TrafficStatsService,
        config_generator: ConfigGenerator,
        user_handler
    ):
        self.user_service = user_service
        self.stats_service = stats_service
        self.config_generator = config_generator
        self.user_handler = user_handler

    async def _ensure_admin_callback(self, update: Update) -> bool:
        """Validate admin access for callback-based admin actions."""
        query = update.callback_query
        if not query:
            return False
        if Config.is_admin(query.from_user.id):
            return True

        await query.answer(Messages.ACCESS_DENIED, show_alert=True)
        return False

    async def _return_to_menu(self, chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send the main menu back to the current user."""
        fake_update = self.build_fake_update(chat_id, user_id)
        await self.user_handler.menu(fake_update, context)
    
    async def show_user_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show traffic statistics for all users (admin only)"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        if not Config.is_admin(user_id):
            await query.edit_message_text("❌ Доступ запрещен", parse_mode='HTML')
            return
        
        # Send loading message
        await query.edit_message_text(
            "📊 Загрузка статистики...",
            parse_mode='HTML'
        )
        
        # Get stats
        stats = await self.stats_service.get_all_stats_sorted()
        
        if not stats:
            await query.edit_message_text(
                "📊 Нет данных о трафике",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(ButtonLabels.BACK, callback_data=CallbackData.BACK_TO_MENU)]
                ])
            )
            return
        
        # Format message - только статистика трафика
        text = "📊 <b>Статистика трафика пользователей</b>\n\n"
        
        for stat in stats[:20]:
            text += f"👤 <b>{stat.user}</b>\n"
            text += f"  📥 Получено: {format_bytes(stat.download)}\n"
            text += f"  📤 Отправлено: {format_bytes(stat.upload)}\n"
            text += f"  📊 Всего: {format_bytes(stat.total)}\n\n"
        
        await query.edit_message_text(
            text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Обновить", callback_data=CallbackData.USER_STATS)],
                [InlineKeyboardButton(ButtonLabels.BACK, callback_data=CallbackData.BACK_TO_MENU)]
            ])
        )
    
    async def show_user_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show online/offline status for all users (admin only)"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        if not Config.is_admin(user_id):
            await query.edit_message_text("❌ Доступ запрещен", parse_mode='HTML')
            return
        
        # Send loading message
        await query.edit_message_text(
            "🟢 Загрузка статусов...",
            parse_mode='HTML'
        )
        
        # Get users with activity status
        users = await self.stats_service.get_active_users_with_details()
        
        if not users:
            await query.edit_message_text(
                "🟢 Нет данных о пользователях",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(ButtonLabels.BACK, callback_data=CallbackData.BACK_TO_MENU)]
                ])
            )
            return
        
        # Format message using Messages class
        text = Messages.get_user_status_message(users)
        
        await query.edit_message_text(
            text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Обновить", callback_data=CallbackData.USER_STATUS)],
                [InlineKeyboardButton(ButtonLabels.BACK, callback_data=CallbackData.BACK_TO_MENU)]
            ])
        )
    
    async def add_user_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Start add user conversation (admin only)"""
        if not await self.is_admin(update):
            await update.callback_query.answer(Messages.ACCESS_DENIED, show_alert=True)
            return -1
        
        message = update.callback_query.message
        context.user_data['menu_message_id'] = message.message_id
        
        await message.edit_text(
            Messages.ADD_USER_PROMPT,
            parse_mode='HTML'
        )
        await update.callback_query.answer()
        
        from handlers.conversation_handlers import ConversationStates
        return ConversationStates.NAME
    
    async def add_user_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle username input for new user"""
        username = update.message.text.strip()
        
        is_valid, error = UserValidator.validate_username(username)
        if not is_valid:
            await update.message.reply_text(f"❌ {error}\nПопробуйте еще раз:")
            from handlers.conversation_handlers import ConversationStates
            return ConversationStates.NAME
        
        users = await self.user_service.singbox.load_users()
        
        if any(u.name.lower() == username.lower() for u in users):
            await update.message.reply_text(f"❌ Пользователь {username} уже существует!")
            from handlers.conversation_handlers import ConversationStates
            return ConversationStates.NAME
        
        import uuid
        user_uuid = str(uuid.uuid4())
        context.user_data['new_user'] = {'name': username, 'uuid': user_uuid}
        
        keyboard = [
            [
                InlineKeyboardButton(ButtonLabels.CONFIRM, callback_data=CallbackData.CONFIRM_ADD),
                InlineKeyboardButton(ButtonLabels.CANCEL, callback_data=CallbackData.CANCEL_ADD)
            ]
        ]
        
        await update.message.reply_text(
            Messages.ADD_USER_CONFIRM.format(username=username, uuid=user_uuid),
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        from handlers.conversation_handlers import ConversationStates
        return ConversationStates.CONFIRM
    
    async def confirm_add_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Confirm adding new user"""
        query = update.callback_query
        await query.answer()
        
        bot = context.bot
        user_info = context.user_data.get('new_user')
        
        if not user_info:
            await query.message.reply_text("❌ Ошибка: данные пользователя не найдены")
            return -1
        
        username = user_info['name']
        chat_id = query.message.chat_id
        
        # Delete confirmation message
        try:
            await query.message.delete()
        except:
            pass
        
        # Delete previous menu message if exists
        if 'menu_message_id' in context.user_data:
            try:
                await bot.delete_message(chat_id=chat_id, message_id=context.user_data['menu_message_id'])
            except:
                pass
        
        # Send processing message
        status_msg = await bot.send_message(
            chat_id=chat_id,
            text=f"🔄 <b>Добавляем {username}...</b>",
            parse_mode='HTML'
        )
        
        # Add user
        singbox = self.user_service.singbox
        from models import User
        user = User(name=username, uuid=user_info['uuid'])
        
        success, error = await singbox.add_user(user)
        
        if not success:
            await status_msg.edit_text(
                f"❌ <b>Ошибка:</b>\n<code>{error}</code>",
                parse_mode='HTML'
            )
            return -1
        
        await status_msg.delete()
        
        # Send success message
        await bot.send_message(
            chat_id=chat_id,
            text=f"✅ <b>Пользователь {username} добавлен!</b>",
            parse_mode='HTML'
        )
        
        # Send config directly without FakeQuery
        server_config = await singbox.get_server_config()
        self.config_generator.server = server_config
        
        # Get the user object
        user_obj = await self.user_service.get_user_by_username(username)
        if user_obj:
            # Send config using direct bot messages
            await self._send_config_directly(bot, chat_id, user_obj.name, user_obj.uuid)
        
        context.user_data.clear()
        return -1
    
    async def _send_config_directly(self, bot, chat_id: int, username: str, user_uuid: str):
        """Send config directly without FakeQuery"""
        singbox = self.user_service.singbox
        server_config = await singbox.get_server_config()
        self.config_generator.server = server_config
        
        # Send platform selection
        keyboard = [
            [
                InlineKeyboardButton("📱 Android", callback_data=f"config_android_{username}"),
                InlineKeyboardButton("🍎 iOS", callback_data=f"config_ios_{username}")
            ],
            [InlineKeyboardButton("🔙 Вернуться в меню", callback_data="back_to_menu")]
        ]
        
        await bot.send_message(
            chat_id=chat_id,
            text="📱 <b>Выберите вашу платформу:</b>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def delete_user_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Start delete user process (admin only)"""
        if not await self.is_admin(update):
            await update.callback_query.answer(Messages.ACCESS_DENIED, show_alert=True)
            return
        
        users = await self.user_service.singbox.load_users()
        
        if not users:
            await update.callback_query.message.edit_text("❌ Нет пользователей для удаления")
            return
        
        keyboard = [
            [InlineKeyboardButton(f"🗑️ {user.name}", callback_data=f"{CallbackData.DELETE_PREFIX}{user.name}")]
            for user in users
        ]
        keyboard.append([InlineKeyboardButton(ButtonLabels.BACK, callback_data=CallbackData.BACK_TO_MENU)])
        
        await update.callback_query.message.edit_text(
            "🗑️ <b>Выберите пользователя для удаления:</b>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        await update.callback_query.answer()
    
    async def confirm_delete_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Confirm user deletion"""
        query = update.callback_query
        if not await self._ensure_admin_callback(update):
            return

        await query.answer()
        
        username = query.data.replace(CallbackData.DELETE_PREFIX, "")
        context.user_data['delete_username'] = username
        
        keyboard = [
            [
                InlineKeyboardButton(ButtonLabels.CONFIRM, callback_data=CallbackData.CONFIRM_DELETE),
                InlineKeyboardButton(ButtonLabels.CANCEL, callback_data=CallbackData.CANCEL_DELETE)
            ]
        ]
        
        await query.message.edit_text(
            f"⚠️ <b>Удалить пользователя {username}?</b>\n\nЭто действие нельзя отменить!",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def perform_delete_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Perform user deletion"""
        query = update.callback_query
        if not await self._ensure_admin_callback(update):
            return

        await query.answer()
        
        username = context.user_data.get('delete_username')
        if not username:
            await query.message.edit_text("❌ Ошибка: пользователь не указан")
            return
        
        status_msg = await query.message.edit_text(
            f"🔄 <b>Удаляем {username}...</b>",
            parse_mode='HTML'
        )
        
        success, error = await self.user_service.delete_user_by_username(username)
        
        if not success:
            await status_msg.edit_text(
                f"❌ <b>Ошибка:</b>\n<code>{error}</code>",
                parse_mode='HTML'
            )
            return
        
        await status_msg.edit_text(
            f"✅ <b>Пользователь {username} удален!</b>",
            parse_mode='HTML'
        )
        
        context.user_data.clear()
        await self._return_to_menu(query.message.chat_id, query.from_user.id, context)
    
    async def cancel_delete(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Cancel user deletion"""
        query = update.callback_query
        if not await self._ensure_admin_callback(update):
            return

        await query.answer()

        context.user_data.clear()
        await self._return_to_menu(query.message.chat_id, query.from_user.id, context)
