import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from config import Config
from models import TrafficStats
from utils.logger import logger
from utils.locks import FileLock
from utils.cache import TTLCache


class TrafficStatsService:
    """Service for managing traffic statistics"""
    
    def __init__(self):
        self.stats_file = Config.TRAFFIC_STATS_FILE
        self.last_active_file = Path("/opt/vlesstgctl/stats/user_last_active.txt")
        self.lock = FileLock(self.stats_file)
        self.cache = TTLCache(ttl=60)
    
    async def _read_last_active(self) -> Dict[str, int]:
        """Read last activity timestamps from file"""
        active = {}
        if not self.last_active_file.exists():
            return active
        
        try:
            with open(self.last_active_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if ':' in line:
                        user, timestamp = line.split(':', 1)
                        active[user] = int(timestamp)
        except Exception as e:
            logger.error(f"Failed to read last_active file: {e}")
        
        return active
    
    async def get_stats(self, username: Optional[str] = None) -> List[TrafficStats]:
        """Get traffic statistics for user(s)"""
        cache_key = f"stats_{username if username else 'all'}"
        cached_stats = self.cache.get(cache_key)
        if cached_stats is not None:
            return cached_stats
        
        try:
            with self.lock.read_json() as data:
                stats_list = []
                for stat_data in data:
                    stat = TrafficStats(
                        user=stat_data.get('user', ''),
                        upload=stat_data.get('upload', 0),
                        download=stat_data.get('download', 0),
                        total=stat_data.get('total', 0),
                        last_updated=None
                    )
                    stats_list.append(stat)
                
                if username:
                    stats_list = [s for s in stats_list if s.user.lower() == username.lower()]
                
                self.cache.set(cache_key, stats_list)
                return stats_list
        except Exception as e:
            logger.error(f"Failed to read traffic stats: {e}")
            return []
    
    async def get_user_stats(self, username: str) -> Optional[TrafficStats]:
        stats = await self.get_stats(username)
        return stats[0] if stats else None
    
    async def get_all_stats_sorted(self) -> List[TrafficStats]:
        stats = await self.get_stats()
        return sorted(stats, key=lambda x: x.total, reverse=True)
    
    async def get_active_users_with_details(self) -> List[dict]:
        """Get all users with real online/offline status"""
        all_stats = await self.get_all_stats_sorted()
        last_active = await self._read_last_active()
        now = int(datetime.now().timestamp())
        
        active_users = []
        
        for stat in all_stats:
            username = stat.user
            last_ts = last_active.get(username, 0)
            
            if last_ts == 0:
                status = "Нет данных"
                status_emoji = "⚪"
                last_seen = "-"
            else:
                minutes_ago = (now - last_ts) // 60
                last_seen = datetime.fromtimestamp(last_ts).strftime("%d.%m %H:%M")

                if minutes_ago < 5:
                    status = "Онлайн"
                    status_emoji = "🟢"
                elif minutes_ago < 60:
                    status = f"{minutes_ago} мин"
                    status_emoji = "🟡"
                elif minutes_ago < 1440:
                    hours_ago = minutes_ago // 60
                    status = f"{hours_ago} ч"
                    status_emoji = "🟡"
                else:
                    days_ago = minutes_ago // 1440
                    status = f"{days_ago} д"
                    status_emoji = "⚪"
            
            active_users.append({
                'username': username,
                'upload': stat.upload,
                'download': stat.download,
                'total': stat.total,
                'status': status,
                'status_emoji': status_emoji,
                'last_seen': last_seen,
                'last_seen_ts': last_ts
            })
        
        return active_users
