import os
import sys
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Config:
    """Centralized configuration management"""
    
    # Bot configuration
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    

    DATA_DIR: Path = Path("/opt/vlesstgctl/data")
    SINGBOX_CONFIG: Path = Path("/etc/sing-box/config.json")
    TRAFFIC_STATS_FILE: Path = Path("/opt/vlesstgctl/stats/traffic.json")
    USER_MAPPING_FILE: Path = Path("/opt/vlesstgctl/data/telegram_users.json")
    
    # Timeouts
    CONNECTION_TIMEOUT: float = 60.0
    READ_TIMEOUT: float = 60.0
    WRITE_TIMEOUT: float = 60.0
    POOL_TIMEOUT: float = 60.0
    
    # Cache settings
    CACHE_TTL: int = 300
    MAX_CACHE_SIZE: int = 100
    
    # Rate limiting
    RATE_LIMIT_CALLS: int = 10
    RATE_LIMIT_PERIOD: int = 60
    
    # User validation
    MAX_USERNAME_LENGTH: int = 20
    MIN_USERNAME_LENGTH: int = 3
    USERNAME_PATTERN: str = r'^[a-z][a-z0-9_]{2,19}$'
    
    # Server defaults
    DEFAULT_DOMAIN: str = "jacket.casacam.net"
    DEFAULT_PORT: str = "443"
    DEFAULT_PUBLIC_KEY: str = "sGUInZ4epsI4uzQ9CKHWAzwIhG9Cy5P9KTAuzTVmfzg"
    DEFAULT_VLESS_SNI: str = "www.microsoft.com"
    
    @classmethod
    def get_admin_ids(cls) -> List[int]:
        """Get admin IDs from environment"""
        admin_ids_str = os.getenv("ADMIN_IDS", "")
        if admin_ids_str:
            return [int(id_.strip()) for id_ in admin_ids_str.split(",") if id_.strip()]
        return []
    
    @classmethod
    def validate(cls) -> None:
        """Validate required configuration"""
        if not cls.BOT_TOKEN:
            logger.error("BOT_TOKEN environment variable is not set!")
            sys.exit(1)
        
        # Create required directories
        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Configuration validated. Admin IDs: {cls.get_admin_ids()}")
        logger.info(f"Data directory: {cls.DATA_DIR}")
        logger.info(f"User mapping file: {cls.USER_MAPPING_FILE}")
    
    @classmethod
    def is_admin(cls, user_id: int) -> bool:
        """Check if user is admin"""
        return user_id in cls.get_admin_ids()


# Initialize config on import
Config.validate()
