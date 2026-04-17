from enum import IntEnum
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from templates.messages import Messages, ButtonLabels, CallbackData
from handlers.base_handler import BaseHandler
from utils.logger import logger
from services.user_service import UserService, UserMappingService
from services.singbox_service import SingBoxService
from services.config_service import ConfigGenerator
from services.stats_service import TrafficStatsService


class ConversationStates(IntEnum):
    """States for conversation handlers"""
    NAME = 1
    CONFIRM = 2


class ConversationHandlers(BaseHandler):
    """Handlers for conversation management"""
    
    @staticmethod
    async def cancel_operation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Cancel current operation"""
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.edit_text(
                Messages.OPERATION_CANCELLED,
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text(
                Messages.OPERATION_CANCELLED,
                parse_mode='HTML'
            )
        
        context.user_data.clear()
        
        # Return to menu
        from handlers.user_handlers import UserHandlers
        
        singbox = SingBoxService()
        mapping_service = UserMappingService()
        user_service = UserService(singbox, mapping_service)
        stats_service = TrafficStatsService()
        server_config = await singbox.get_server_config()
        config_generator = ConfigGenerator(server_config)
        
        user_handler = UserHandlers(user_service, config_generator, stats_service)
        
        # Handle both callback and message
        if update.callback_query:
            await user_handler.menu(update, context)
        else:
            await user_handler.start(update, context)
        
        return ConversationHandler.END

