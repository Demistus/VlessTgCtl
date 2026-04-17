import json
import uuid
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from config import Config
from models import User, UserStatus
from utils.logger import logger
from utils.locks import FileLock
from utils.validators import UserValidator
from services.singbox_service import SingBoxService


class UserMappingService:
    """Service for managing Telegram user mappings"""
    
    def __init__(self):
        self.mapping_file = Config.USER_MAPPING_FILE
        self.lock = FileLock(self.mapping_file)
    
    async def _read_mapping(self) -> Dict[str, str]:
        """Safely read mapping file"""
        if not self.mapping_file.exists():
            return {}
        
        try:
            with self.lock.read_json() as mapping:
                if not mapping:
                    return {}
                return mapping
        except Exception as e:
            logger.error(f"Failed to read mapping: {e}")
            return {}
    
    async def save_mapping(self, telegram_id: int, username: str) -> None:
        """Save Telegram ID to username mapping"""
        try:
            mapping = await self._read_mapping()
            mapping[str(telegram_id)] = username
            
            with self.lock.write_json(mapping):
                pass
            
            logger.info(f"Saved mapping: {telegram_id} -> {username}")
        except Exception as e:
            logger.error(f"Failed to save mapping: {e}")
    
    async def get_username(self, telegram_id: int) -> Optional[str]:
        """Get username by Telegram ID"""
        mapping = await self._read_mapping()
        return mapping.get(str(telegram_id))
    
    async def delete_mapping(self, telegram_id: int) -> bool:
        """Delete mapping for Telegram ID"""
        try:
            mapping = await self._read_mapping()
            if str(telegram_id) in mapping:
                del mapping[str(telegram_id)]
                
                with self.lock.write_json(mapping):
                    pass
                
                logger.info(f"Deleted mapping for {telegram_id}")
                return True
        except Exception as e:
            logger.error(f"Failed to delete mapping: {e}")
        
        return False
    
    async def find_telegram_id_by_username(self, username: str) -> Optional[int]:
        """Find Telegram ID by username"""
        mapping = await self._read_mapping()
        for tid, uname in mapping.items():
            if uname.lower() == username.lower():
                return int(tid)
        return None


class UserService:
    """Main user service combining sing-box and mapping services"""
    
    def __init__(self, singbox_service: SingBoxService, mapping_service: UserMappingService):
        self.singbox = singbox_service
        self.mapping = mapping_service
    
    async def get_user_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Get user by Telegram ID"""
        username = await self.mapping.get_username(telegram_id)
        logger.info(f"get_user_by_telegram_id: {telegram_id} -> username={username}")
    
        if not username:
            return None
    
        users = await self.singbox.load_users()
        user = next(
            (u for u in users if u.name.lower() == username.lower()),
            None
        )
    
        if user:
            user.telegram_id = telegram_id
            logger.info(f"Found user: {user.name}")
        else:
            logger.warning(f"User {username} not found in config, cleaning up mapping")
            # Маппинг есть, но пользователя в конфиге нет - удаляем маппинг
            await self.mapping.delete_mapping(telegram_id)
    
        return user
    
    async def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username"""
        users = await self.singbox.load_users()
        user = next(
            (u for u in users if u.name.lower() == username.lower()),
            None
        )
        
        if user:
            telegram_id = await self.mapping.find_telegram_id_by_username(username)
            if telegram_id:
                user.telegram_id = telegram_id
        
        return user
    
    async def get_user_configs(self, telegram_id: int, is_admin: bool) -> List[User]:
        """Get user configurations based on permissions"""
        users = await self.singbox.load_users()
        
        if is_admin:
            return users
        
        username = await self.mapping.get_username(telegram_id)
        if not username:
            return []
        
        return [u for u in users if u.name.lower() == username.lower()]
    
    async def create_user(self, telegram_id: int, username: str) -> Tuple[bool, str, Optional[User]]:
        """Create new user"""
        # СНАЧАЛА ПРОВЕРЯЕМ - нет ли уже пользователя с таким telegram_id
        existing_user = await self.get_user_by_telegram_id(telegram_id)
        if existing_user:
            logger.info(f"User {existing_user.name} already exists for telegram_id {telegram_id}")
            return False, "У вас уже есть активный конфиг", existing_user
        
        # Validate username
        is_valid, error = UserValidator.validate_username(username)
        if not is_valid:
            return False, error, None
        
        # Check if username is taken
        existing_by_name = await self.get_user_by_username(username)
        if existing_by_name:
            # Generate unique username
            base_username = username
            counter = 1
            while existing_by_name:
                username = f"{base_username}_{counter}"
                existing_by_name = await self.get_user_by_username(username)
                counter += 1
        
        # Create user
        user = User(
            name=username,
            uuid=str(uuid.uuid4()),
            telegram_id=telegram_id
        )
        
        success, error = await self.singbox.add_user(user)
        if not success:
            return False, error, None
        
        # Save mapping
        await self.mapping.save_mapping(telegram_id, username)
        logger.info(f"Created user {username} for telegram_id {telegram_id}")
        
        return True, "Success", user
    
    async def delete_user_by_username(self, username: str) -> Tuple[bool, str]:
        """Delete user by username"""
        # Find telegram_id if exists
        telegram_id = await self.mapping.find_telegram_id_by_username(username)
        
        # Remove from sing-box
        success, error = await self.singbox.remove_user(username)
        if not success:
            return False, error
        
        # Remove mapping
        if telegram_id:
            await self.mapping.delete_mapping(telegram_id)
        
        logger.info(f"Deleted user {username}")
        return True, "Success"

