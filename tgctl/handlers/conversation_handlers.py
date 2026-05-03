from enum import IntEnum
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from templates.messages import Messages, ButtonLabels, CallbackData
from handlers.base_handler import BaseHandler


class ConversationStates(IntEnum):
    """States for conversation handlers"""
    NAME = 1
    CONFIRM = 2


class ConversationHandlers(BaseHandler):
    """Handlers for conversation management"""

    def __init__(self, user_handler):
        self.user_handler = user_handler
    
    async def cancel_operation(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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

        # Handle both callback and message
        if update.callback_query:
            await self.user_handler.menu(update, context)
        else:
            await self.user_handler.start(update, context)
        
        return ConversationHandler.END

