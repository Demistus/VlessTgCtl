"""
Message templates for the bot.
Centralized location for all bot messages to support easy updates and i18n.
"""

from typing import Dict, Any


class Messages:
    """Centralized message templates"""
    
    # General messages
    WELCOME = "📱 <b>Добро пожаловать в VPN бот!</b>\n\nВыберите действие в меню:"
    MENU = "📱 <b>Главное меню</b>\n\nВыберите действие:"
    ACCESS_DENIED = "❌ <b>Доступ запрещен</b>\nУ вас нет прав для этого действия."
    USER_NOT_FOUND = "❌ <b>Пользователь не найден</b>"
    CONFIG_NOT_FOUND = "❌ <b>Конфиг не найден</b>"
    NO_CONFIGS = "❌ <b>У вас нет активных конфигов</b>\n\nНажмите кнопку ниже, чтобы создать:"
    NO_TRAFFIC_DATA = "📊 <b>Нет данных о трафике</b>"
    OPERATION_CANCELLED = "❌ Операция отменена"
    OPERATION_FAILED = "❌ <b>Ошибка:</b>\n<code>{error}</code>"
    OPERATION_SUCCESS = "✅ <b>Операция выполнена успешно!</b>"
    PROCESSING = "🔄 <b>{action}...</b>"
    
    # User management
    USER_ADDED = "✅ <b>Пользователь {username} добавлен!</b>"
    USER_DELETED = "✅ <b>Пользователь {username} удален!</b>"
    USER_EXISTS = "❌ Пользователь {username} уже существует!"
    USER_NOT_EXISTS = "❌ Пользователь {username} не найден!"
    
    # Config messages
    CONFIG_PREPARING = "📱 <b>Подготовка конфига...</b>"
    CONFIG_SENT = "✅ <b>Конфиги успешно отправлены для {username}!</b>\n\nВыберите действие:"
    SELECT_PLATFORM = "📱 <b>Выберите вашу платформу:</b>"
    
    # Traffic messages
    TRAFFIC_TITLE = "📊 <b>Ваш трафик</b>"
    TOTAL_TRAFFIC_TITLE = "📊 <b>Статистика всех пользователей</b>"
    NO_TRAFFIC = "📊 <b>Ваш трафик</b>\n\n👤 {username}\nНет данных о трафике"
    
    # Server info
    SERVER_INFO_TITLE = "🖥️ <b>Информация о сервере</b>"
    
    # Add user conversation
    ADD_USER_PROMPT = "➕ <b>Введите имя пользователя</b> (a-z, 3-20 символов):\n<i>/cancel - отмена</i>"
    ADD_USER_INVALID_NAME = "❌ {error}\nПопробуйте еще раз:"
    ADD_USER_CONFIRM = (
        "📝 <b>Подтвердите добавление:</b>\n\n"
        "👤 <b>Имя:</b> {username}\n"
        "🔑 <b>UUID:</b> <code>{uuid}</code>\n\n"
        "Добавить пользователя?"
    )
    
    # Delete user conversation
    DELETE_USER_PROMPT = "🗑️ <b>Выберите пользователя для удаления:</b>"
    DELETE_USER_CONFIRM = "⚠️ <b>Удалить пользователя {username}?</b>\n\nЭто действие нельзя отменить!"
    NO_USERS_TO_DELETE = "❌ Нет пользователей для удаления"
    
    # Config captions
    @staticmethod
    def get_config_caption(username: str, uuid: str) -> str:
        """Get caption for config file"""
        return (
            f"📱 <b>Конфиг для Sing-box</b>\n\n"
            f"👤 <b>Имя:</b> {username}\n"
            f"🔑 <b>UUID:</b> <code>{uuid}</code>\n\n"
            f"<b>⭐ Особенности версии:</b>\n"
            f"• Российские сайты (Госуслуги, Сбер) пойдут через прямое подключение\n"
            f"• Заблокированные сайты — через VPN\n\n"
            f"<b>📱 Как подключиться:</b>\n"
            f"1. Сохраните этот файл\n"
            f"2. Установите Sing-box из магазина приложений:\n"
            f"   • Android: https://play.google.com/store/apps/details?id=io.nekohasekai.sfa\n"
            f"   • iOS: https://apps.apple.com/ru/app/sing-box-vt/id6673731168\n"
            f"3. В приложении нажмите '+' → 'Import from file'\n"
            f"4. Выберите этот сохраненный файл\n"
            f"5. Нажмите для подключения кнопку ▶️"
        )
    
    @staticmethod
    def get_qr_caption(username: str) -> str:
        """Get caption for QR code"""
        return (
            f"📱 <b>QR-код VLESS</b> для {username}\n\n"
            f"<b>📱 Альтернативный клиент — Happ:</b>\n"
            f"• Весь трафик проходит через VPN\n"
            f"• Для доступа к Госуслугам и банкам потребуется отключить VPN вручную\n\n"
            f"<b>Как подключиться через Happ:</b>\n"
            f"1. Сохраните этот QR-код в галерею\n"
            f"2. Установите Happ из магазина приложений:\n"
            f"   • Android: https://play.google.com/store/apps/details?id=com.happproxy\n"
            f"   • iOS: https://apps.apple.com/ru/app/happ-proxy-utility-plus/id6746188973\n"
            f"3. В приложении нажмите '+' → 'Сканировать QR код'\n"
            f"4. Выберите из галереи и отсканируйте сохраненный QR-код\n"
            f"5. Нажмите для подключения на центральную кнопку ⏻"
        )
    
    @staticmethod
    def get_traffic_message(username: str, upload: int, download: int, total: int) -> str:
        """Get formatted traffic message"""
        from utils.formatters import format_bytes
        return (
            f"📊 <b>Ваш трафик</b>\n\n"
            f"👤 <b>{username}</b>\n"
            f"📥 <b>Получено:</b> {format_bytes(download)}\n"
            f"📤 <b>Отправлено:</b> {format_bytes(upload)}\n"
            f"📊 <b>Всего:</b> {format_bytes(total)}"
        )
    
    @staticmethod
    def get_total_traffic_message(stats: list) -> str:
        """Get formatted total traffic message for all users"""
        from utils.formatters import format_bytes
        
        if not stats:
            return "📊 <b>Нет данных о трафике</b>"
        
        text = "📊 <b>Статистика пользователей</b>\n\n"
        for stat in stats[:20]:  # Limit to 20 users
            text += f"👤 <b>{stat.user}</b>\n"
            text += f"  📥 Получено: {format_bytes(stat.download)}\n"
            text += f"  📤 Отправлено: {format_bytes(stat.upload)}\n"
            text += f"  📊 Всего: {format_bytes(stat.total)}\n\n"
        
        return text
    
    @staticmethod
    def get_user_status_message(users: list) -> str:
        """Get formatted user status message for admin (mobile-friendly)"""
        from utils.formatters import format_bytes
        
        if not users:
            return "🟢 Нет данных"
        
        # Находим максимальную длину имени
        max_name_len = max(len(u['username'][:9]) for u in users[:15])
        max_name_len = max(max_name_len, 9)
        
        # Находим максимальную длину трафика
        max_traffic_len = max(len(format_bytes(u['total'])) for u in users[:15])
        
        text = "🟢 <b>Статус</b>\n\n"
        text += "<code>"
        
        for user in users[:15]:
            status_emoji = user['status_emoji']
            username = user['username'][:9].ljust(max_name_len)
            total = format_bytes(user['total']).rjust(max_traffic_len)
            status = user['status']
            last_seen = user.get('last_seen', '-')
            
            if status == "Онлайн":
                text += f"{status_emoji} {username} {total} | Онлайн | {last_seen}\n"
            else:
                text += f"{status_emoji} {username} {total} | {status} | {last_seen}\n"
        
        text += "</code>"
        return text
    
    @staticmethod
    def get_server_info_message(domain: str, port: str, users_count: int) -> str:
        """Get formatted server info message"""
        return (
            f"🖥️ <b>Информация о сервере</b>\n\n"
            f"🌐 <b>Адрес:</b> {domain}:{port}\n"
            f"👥 <b>Пользователей:</b> {users_count}\n"
            f"🔒 <b>Протокол:</b> VLESS + REALITY\n"
            f"⚡ <b>Статус:</b> 🟢 Работает"
        )
    
    @staticmethod
    def get_help_text() -> str:
        """Get help text"""
        return (
            "❓ <b>Помощь и инструкция</b>\n\n"
            "<b>📱 Как подключиться через Sing-box:</b>\n"
            "1. Скачайте сгенерированный для Вас JSON конфиг\n"
            "2. Установите Sing-box из магазина приложений:\n"
            "   • Android: https://play.google.com/store/apps/details?id=io.nekohasekai.sfa\n"
            "   • iOS: https://apps.apple.com/ru/app/sing-box-vt/id6673731168\n"
            "3. В приложении нажмите '+' → 'Import from file'\n"
            "4. Выберите скачанный JSON файл\n"
            "5. Нажмите для подключения кнопку ▶️\n\n"
            "<b>📱 Как подключиться через Happ (альтернатива):</b>\n"
            "1. Установите Happ из магазина приложений:\n"
            "   • Android: https://play.google.com/store/apps/details?id=com.happproxy\n"
            "   • iOS: https://apps.apple.com/ru/app/happ-proxy-utility-plus/id6746188973\n"
            "2. В приложении нажмите '+' → 'Сканировать QR код'\n"
            "3. Выберите из галереи и отсканируйте сохраненный QR-код\n"
            "4. Нажмите для подключения на центральную кнопку ⏻\n\n"
            "<b>📱 Альтернативные клиенты:</b>\n"
            "• NekoBox: https://github.com/MatsuriDayo/NekoBoxForAndroid/releases\n\n"
            "<b>🔧 Команды:</b>\n"
            "/start - Начать работу\n"
            "/menu - Главное меню\n"
            "/help - Эта справка"
        )
    
    @staticmethod
    def get_configs_list_message(is_admin: bool = False) -> str:
        """Get configs list title"""
        return "📱 <b>Ваши конфиги:</b>" if not is_admin else "📱 <b>Все конфиги:</b>"
    
    @staticmethod
    def get_error_message(error: str) -> str:
        """Get formatted error message"""
        return f"❌ <b>Ошибка:</b>\n<code>{error}</code>"
    
    @staticmethod
    def get_success_message(action: str, username: str = None) -> str:
        """Get formatted success message"""
        if username:
            return f"✅ <b>{action} {username} выполнено успешно!</b>"
        return f"✅ <b>{action} выполнено успешно!</b>"


class ButtonLabels:
    """Button labels for inline keyboards"""
    
    # Main menu
    MY_CONFIGS = "📱 Мои конфиги"
    MY_TRAFFIC = "📊 Мой трафик"
    CREATE_CONFIG = "🔑 Создать мой конфиг"
    SERVER_INFO = "ℹ️ Информация о сервере"
    HELP = "❓ Помощь"
    
    # Admin menu
    ADD_USER = "➕ Добавить пользователя"
    DELETE_USER = "🗑️ Удалить пользователя"
    USER_STATS = "📊 Статистика пользователей"
    USER_STATUS = "🟢 Статус пользователей"
    
    # Navigation
    BACK = "🔙 Назад"
    BACK_TO_MENU = "🔙 Вернуться в меню"
    
    # Actions
    CONFIRM = "✅ Да"
    CANCEL = "❌ Нет"
    
    # Platforms
    ANDROID = "📱 Android"
    IOS = "🍎 iOS"


class CallbackData:
    """Callback data constants"""
    
    # User actions
    MY_CONFIGS = "my_configs"
    MY_TRAFFIC = "show_my_traffic"
    CREATE_CONFIG = "create_my_config"
    SERVER_INFO = "server_info"
    HELP = "help"
    BACK_TO_MENU = "back_to_menu"
    
    # Admin actions
    ADD_USER = "add_user"
    DELETE_USER = "delete_user"
    USER_STATS = "user_stats"
    USER_STATUS = "user_status"
    
    # Config actions
    CONFIG_PREFIX = "config_"
    CONFIG_ANDROID_PREFIX = "config_android_"
    CONFIG_IOS_PREFIX = "config_ios_"
    
    # Delete actions
    DELETE_PREFIX = "del_"
    
    # Confirm actions
    CONFIRM_ADD = "confirm_add"
    CANCEL_ADD = "cancel_add"
    CONFIRM_DELETE = "confirm_delete"
    CANCEL_DELETE = "cancel_delete"


class ErrorMessages:
    """Error message templates"""
    
    CONFIG_LOAD_ERROR = "Не удалось загрузить конфигурацию. Пожалуйста, попробуйте позже."
    CONFIG_SAVE_ERROR = "Не удалось сохранить конфигурацию. Проверьте права доступа."
    USER_CREATE_ERROR = "Не удалось создать пользователя. Возможно, имя уже существует."
    USER_DELETE_ERROR = "Не удалось удалить пользователя."
    STATS_LOAD_ERROR = "Не удалось загрузить статистику трафика."
    SERVER_RESTART_ERROR = "Не удалось перезагрузить сервер. Пожалуйста, свяжитесь с администратором."
    
    INVALID_USERNAME = "Имя может содержать только латинские буквы, цифры и нижнее подчеркивание. Должно начинаться с буквы."
    USERNAME_TOO_SHORT = "Имя должно быть не менее {min_length} символов."
    USERNAME_TOO_LONG = "Имя должно быть не более {max_length} символов."
    
    @staticmethod
    def format(message: str, **kwargs) -> str:
        """Format error message with parameters"""
        return message.format(**kwargs)


# Export all message classes
__all__ = ['Messages', 'ButtonLabels', 'CallbackData', 'ErrorMessages']
