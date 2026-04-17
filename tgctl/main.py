#!/usr/bin/env python3
"""
Telegram bot for managing sing-box VPN
Production-ready version
"""

import asyncio
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ConversationHandler
)
from telegram.request import HTTPXRequest

from config import Config
from services.singbox_service import SingBoxService
from services.user_service import UserService, UserMappingService
from services.config_service import ConfigGenerator
from services.stats_service import TrafficStatsService
from handlers.user_handlers import UserHandlers
from handlers.admin_handlers import AdminHandlers
from handlers.conversation_handlers import ConversationHandlers, ConversationStates
from templates.messages import CallbackData
from utils.logger import logger


async def error_handler(update, context):
    """Handle errors in the bot"""
    logger.error(f"Update {update} caused error {context.error}")
    
    # Notify user about error
    if update and update.effective_chat:
        from templates.messages import ErrorMessages
        await update.effective_chat.send_message(
            ErrorMessages.CONFIG_LOAD_ERROR
        )


async def main_async():
    """Main async function to run the bot"""
    # Validate configuration
    Config.validate()
    
    # Initialize services
    singbox_service = SingBoxService()
    mapping_service = UserMappingService()
    user_service = UserService(singbox_service, mapping_service)
    stats_service = TrafficStatsService()
    
    # Get server config for config generator
    server_config = await singbox_service.get_server_config()
    config_generator = ConfigGenerator(server_config)
    
    # Initialize handlers
    user_handlers = UserHandlers(user_service, config_generator, stats_service)
    admin_handlers = AdminHandlers(user_service, stats_service)
    conv_handlers = ConversationHandlers()
    
    # Create application
    request = HTTPXRequest(
        connect_timeout=Config.CONNECTION_TIMEOUT,
        read_timeout=Config.READ_TIMEOUT,
        write_timeout=Config.WRITE_TIMEOUT,
        pool_timeout=Config.POOL_TIMEOUT
    )
    
    application = Application.builder() \
        .token(Config.BOT_TOKEN) \
        .request(request) \
        .build()
    
    # Add conversation handler for adding users
    add_user_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_handlers.add_user_start, pattern='^add_user$')],
        states={
            ConversationStates.NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handlers.add_user_name)],
            ConversationStates.CONFIRM: [
                CallbackQueryHandler(admin_handlers.confirm_add_user, pattern='^confirm_add$'),
                CallbackQueryHandler(conv_handlers.cancel_operation, pattern='^cancel_add$')
            ],
        },
        fallbacks=[CommandHandler('cancel', conv_handlers.cancel_operation)],
        allow_reentry=True,
        per_message=False
    )
    
    # Add conversation handler
    application.add_handler(add_user_conv)
    
    # Command handlers
    application.add_handler(CommandHandler("start", user_handlers.start))
    application.add_handler(CommandHandler("menu", user_handlers.menu))
    application.add_handler(CommandHandler("help", user_handlers.help_command))
    application.add_handler(CommandHandler("id", user_handlers.show_id))  # Debug command
    
    # Admin callback handlers - новые обработчики для статистики и статуса
    application.add_handler(CallbackQueryHandler(admin_handlers.show_user_stats, pattern='^user_stats$'))
    application.add_handler(CallbackQueryHandler(admin_handlers.show_user_status, pattern='^user_status$'))
    
    # Admin callback handlers - остальные
    application.add_handler(CallbackQueryHandler(admin_handlers.delete_user_start, pattern='^delete_user$'))
    application.add_handler(CallbackQueryHandler(admin_handlers.confirm_delete_user, pattern='^del_'))
    application.add_handler(CallbackQueryHandler(admin_handlers.perform_delete_user, pattern='^confirm_delete$'))
    application.add_handler(CallbackQueryHandler(admin_handlers.cancel_delete, pattern='^cancel_delete$'))
    
    # User callback handler - обрабатывает все остальные callback
    application.add_handler(CallbackQueryHandler(
        user_handlers.handle_callback, 
        pattern='^(?!.*(add_user|delete_user|del_|confirm_delete|cancel_delete|user_stats|user_status)).*'
    ))
    
    # Message handler - для обычных текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, user_handlers.handle_message))
    
    # Error handler
    application.add_error_handler(error_handler)
    
    # Start bot
    logger.info("🚀 Bot started successfully!")
    
    # Start polling
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    # Keep running
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    finally:
        await application.updater.stop()
        await application.stop()
        await application.shutdown()


def main():
    """Main function to run the bot"""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise


if __name__ == '__main__':
    main()