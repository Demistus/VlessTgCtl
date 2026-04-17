import re
from typing import Optional
from config import Config


class UserValidator:
    """User input validation"""
    
    @staticmethod
    def validate_username(username: str) -> tuple[bool, Optional[str]]:
        """
        Validate username format
        Returns: (is_valid, error_message)
        """
        if not username:
            return False, "Имя пользователя не может быть пустым"
        
        if len(username) < Config.MIN_USERNAME_LENGTH:
            return False, f"Имя должно быть не менее {Config.MIN_USERNAME_LENGTH} символов"
        
        if len(username) > Config.MAX_USERNAME_LENGTH:
            return False, f"Имя должно быть не более {Config.MAX_USERNAME_LENGTH} символов"
        
        if not re.match(Config.USERNAME_PATTERN, username):
            return False, "Имя может содержать только латинские буквы, цифры и нижнее подчеркивание. Должно начинаться с буквы."
        
        return True, None
    
    @staticmethod
    def sanitize_username(username: str) -> str:
        """Sanitize username for safe use"""
        # Remove unsafe characters
        username = re.sub(r'[^a-zA-Z0-9_\-]', '_', username)
        
        # Ensure it starts with letter
        if username and username[0].isdigit():
            username = f"user_{username}"
        
        # Truncate to max length
        if len(username) > Config.MAX_USERNAME_LENGTH:
            username = username[:Config.MAX_USERNAME_LENGTH]
        
        return username.lower()
    
    @staticmethod
    def is_valid_uuid(uuid_str: str) -> bool:
        """Validate UUID format"""
        uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        return bool(re.match(uuid_pattern, uuid_str, re.IGNORECASE))