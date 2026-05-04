import json
import asyncio
import copy
from typing import Dict, Any, List
from config import Config
from models import User, ServerConfig
from utils.logger import logger
from utils.locks import FileLock


class SingBoxService:
    """Service for managing sing-box configuration"""
    
    def __init__(self):
        self.config_path = Config.SINGBOX_CONFIG
        self.stats_path = Config.TRAFFIC_STATS_FILE
        self.lock = FileLock(self.config_path)
    
    async def load_users(self) -> List[User]:
        """Load users from sing-box config"""
        if not self.config_path.exists():
            return []
        
        try:
            with self.lock.read_json() as config:
                users = []
                for inbound in config.get('inbounds', []):
                    if inbound.get('type') == 'vless':
                        for user_data in inbound.get('users', []):
                            user = User(
                                name=user_data.get('name'),
                                uuid=user_data.get('uuid')
                            )
                            users.append(user)
                
                logger.info(f"Loaded {len(users)} users from config")
                return users
        except Exception as e:
            logger.error(f"Failed to load users: {e}")
            return []
    
    async def save_users(self, users: List[User]) -> bool:
        """Save users to sing-box config"""
        if not self.config_path.exists():
            logger.error("Config file does not exist")
            return False
        
        try:
            with self.lock.read_json() as config:
                # Update users in config
                for inbound in config.get('inbounds', []):
                    if inbound.get('type') == 'vless':
                        inbound['users'] = [
                            {
                                'name': user.name,
                                'uuid': user.uuid,
                                'flow': 'xtls-rprx-vision'
                            }
                            for user in users
                        ]
                        break
            
            # Write back
            with self.lock.write_json(config):
                pass
            
            logger.info(f"Saved {len(users)} users to config")
            return True
        except Exception as e:
            logger.error(f"Failed to save users: {e}")
            return False

    def _load_config_unlocked(self) -> Dict[str, Any]:
        """Load config while the caller is already holding the file lock."""
        if not self.config_path.exists():
            return {}

        with open(self.config_path, 'r') as f:
            content = f.read().strip()
            return json.loads(content) if content else {}

    def _extract_users_from_config(self, config: Dict[str, Any]) -> List[User]:
        """Build user models from loaded sing-box config."""
        users = []
        for inbound in config.get('inbounds', []):
            if inbound.get('type') == 'vless':
                for user_data in inbound.get('users', []):
                    users.append(
                        User(
                            name=user_data.get('name'),
                            uuid=user_data.get('uuid')
                        )
                    )
        return users

    def _write_config_unlocked(self, config: Dict[str, Any]) -> None:
        """Persist config while the caller is already holding the file lock."""
        temp_path = self.config_path.with_suffix('.tmp')
        with open(temp_path, 'w') as f:
            json.dump(config, f, indent=2)
        temp_path.replace(self.config_path)

    def _write_users_to_config(self, config: Dict[str, Any], users: List[User]) -> bool:
        """Replace vless users in config and persist atomically."""
        updated = False
        for inbound in config.get('inbounds', []):
            if inbound.get('type') == 'vless':
                inbound['users'] = [
                    {
                        'name': user.name,
                        'uuid': user.uuid,
                        'flow': 'xtls-rprx-vision'
                    }
                    for user in users
                ]
                updated = True
                break

        if not updated:
            logger.error("VLESS inbound not found in config")
            return False

        self._write_config_unlocked(config)
        return True
    
    async def add_user(self, user: User) -> tuple[bool, str]:
        """Add user to configuration"""
        try:
            if not self.config_path.exists():
                logger.error("Config file does not exist")
                return False, "Не удалось сохранить конфигурацию"

            with self.lock:
                config = self._load_config_unlocked()
                original_config = copy.deepcopy(config)
                users = self._extract_users_from_config(config)

                if any(u.name.lower() == user.name.lower() for u in users):
                    return False, "Пользователь с таким именем уже существует"

                users.append(user)

                if not self._write_users_to_config(config, users):
                    return False, "Не удалось сохранить конфигурацию"
            
            if not await self.restart():
                with self.lock:
                    self._write_config_unlocked(original_config)
                return False, "Конфигурация сохранена, но sing-box не применил изменения. Изменения отменены."

            logger.info(f"User added: {user.name}")
            return True, "Success"
        except Exception as e:
            logger.error(f"Failed to add user: {e}")
            return False, str(e)
    
    async def remove_user(self, username: str) -> tuple[bool, str]:
        """Remove user from configuration"""
        try:
            if not self.config_path.exists():
                logger.error("Config file does not exist")
                return False, "Не удалось сохранить конфигурацию"

            with self.lock:
                config = self._load_config_unlocked()
                original_config = copy.deepcopy(config)
                users = self._extract_users_from_config(config)

                user_to_remove = next(
                    (u for u in users if u.name.lower() == username.lower()),
                    None
                )

                if not user_to_remove:
                    return False, "Пользователь не найден"

                users = [u for u in users if u.name.lower() != username.lower()]

                if not self._write_users_to_config(config, users):
                    return False, "Не удалось сохранить конфигурацию"
            
            if not await self.restart():
                with self.lock:
                    self._write_config_unlocked(original_config)
                return False, "Конфигурация сохранена, но sing-box не применил изменения. Изменения отменены."

            logger.info(f"User removed: {username}")
            return True, "Success"
        except Exception as e:
            logger.error(f"Failed to remove user: {e}")
            return False, str(e)
    
    async def restart(self) -> bool:
        """Restart sing-box with HUP signal"""
        try:
            process = await asyncio.create_subprocess_exec(
                'docker', 'exec', 'sing-box', 'kill', '-HUP', '1',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                logger.info("Sing-box restarted successfully (HUP)")
                return True
            else:
                logger.error(f"Failed to restart sing-box: {stderr.decode()}")
                return False
        except Exception as e:
            logger.error(f"Error restarting sing-box: {e}")
            return False
    
    async def get_server_config(self) -> ServerConfig:
        """Get server configuration from sing-box config"""
        config = ServerConfig(
            domain=Config.DEFAULT_DOMAIN,
            port=Config.DEFAULT_PORT,
            public_key=Config.DEFAULT_PUBLIC_KEY,
            short_id='',
            vless_sni=Config.DEFAULT_VLESS_SNI
        )
        
        if not self.config_path.exists():
            return config
        
        try:
            with self.lock.read_json() as data:
                for inbound in data.get('inbounds', []):
                    if inbound.get('type') == 'vless':
                        config.port = str(inbound.get('listen_port', config.port))
                        tls = inbound.get('tls', {})
                        reality = tls.get('reality', {})
                        
                        config.short_id = reality.get('short_id', '')
                        config.vless_sni = tls.get('server_name', config.vless_sni)
                        break
        except Exception as e:
            logger.error(f"Failed to load server config: {e}")
        
        return config
