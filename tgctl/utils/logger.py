import logging
import sys
from typing import Optional
from datetime import datetime
import json


class SanitizedLogger:
    """Logger that sanitizes sensitive information"""
    
    SENSITIVE_FIELDS = {'uuid', 'token', 'password', 'private_key', 'pbk'}
    
    def __init__(self, name: str, level: int = logging.INFO):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
    
    def _sanitize(self, message: str) -> str:
        """Remove sensitive information from log messages"""
        for field in self.SENSITIVE_FIELDS:
            # Replace UUID patterns
            import re
            pattern = rf'{field}[=:]\s*[\w-]+'
            message = re.sub(pattern, f'{field}=[REDACTED]', message, flags=re.IGNORECASE)
        
        # Replace any UUID pattern
        uuid_pattern = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
        message = re.sub(uuid_pattern, '[REDACTED-UUID]', message, flags=re.IGNORECASE)
        
        return message
    
    def info(self, message: str, *args, **kwargs):
        self.logger.info(self._sanitize(message), *args, **kwargs)
    
    def error(self, message: str, *args, **kwargs):
        self.logger.error(self._sanitize(message), *args, **kwargs)
    
    def warning(self, message: str, *args, **kwargs):
        self.logger.warning(self._sanitize(message), *args, **kwargs)
    
    def debug(self, message: str, *args, **kwargs):
        self.logger.debug(self._sanitize(message), *args, **kwargs)


# Global logger instance
logger = SanitizedLogger(__name__)