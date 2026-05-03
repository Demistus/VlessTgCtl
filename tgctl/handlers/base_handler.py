from typing import Union
from telegram import Update, CallbackQuery, Message
from config import Config
from utils.logger import logger


class BaseHandler:
    """Base handler with common utilities"""
    
    @staticmethod
    async def is_admin(update: Update) -> bool:
        """Check if user is admin"""
        user_id = update.effective_user.id
        return Config.is_admin(user_id)
    
    @staticmethod
    async def send_menu(bot, chat_id: int, user_id: int) -> None:
        """Send main menu to user"""
        from handlers.user_handlers import UserHandlers
        await UserHandlers.send_menu(bot, chat_id, user_id)

    @staticmethod
    def build_fake_update(chat_id: int, user_id: int):
        """Build a minimal update-like object for menu rendering flows."""
        class FakeUpdate:
            def __init__(self, chat_id, user_id):
                self.effective_chat = type('obj', (object,), {'id': chat_id})()
                self.effective_user = type('obj', (object,), {'id': user_id})()

        return FakeUpdate(chat_id, user_id)
    
    @staticmethod
    def get_user_id(update: Update) -> int:
        """Get user ID from update"""
        return update.effective_user.id
    
    @staticmethod
    def get_chat_id(update: Update) -> int:
        """Get chat ID from update"""
        return update.effective_chat.id
    
    @staticmethod
    async def safe_edit_message(
        obj: Union[CallbackQuery, Message],
        text: str,
        parse_mode: str = 'HTML',
        reply_markup=None
    ) -> None:
        """Safely edit or send message"""
        try:
            if hasattr(obj, 'edit_message_text'):
                await obj.edit_message_text(
                    text=text,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup
                )
            elif hasattr(obj, 'message') and hasattr(obj.message, 'edit_text'):
                await obj.message.edit_text(
                    text=text,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup
                )
            else:
                await obj.reply_text(
                    text=text,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup
                )
        except Exception as e:
            logger.warning(f"Failed to edit message: {e}")
            if hasattr(obj, 'message'):
                await obj.message.reply_text(
                    text=text,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup
                )
    
    @staticmethod
    async def delete_message_safely(message: Message) -> None:
        """Safely delete a message"""
        try:
            await message.delete()
        except Exception as e:
            logger.warning(f"Failed to delete message: {e}")
