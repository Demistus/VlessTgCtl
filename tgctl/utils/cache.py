import time
from typing import Optional, Any, Dict
from functools import lru_cache, wraps
from collections import OrderedDict


class TTLCache:
    """Time-To-Live cache implementation"""
    
    def __init__(self, ttl: int = 300, max_size: int = 100):
        self.ttl = ttl
        self.max_size = max_size
        self._cache: OrderedDict = OrderedDict()
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired"""
        if key in self._cache:
            value, timestamp = self._cache[key]
            if time.time() - timestamp < self.ttl:
                # Move to end (most recently used)
                self._cache.move_to_end(key)
                return value
            else:
                del self._cache[key]
        return None
    
    def set(self, key: str, value: Any) -> None:
        """Set value in cache"""
        if key in self._cache:
            self._cache.move_to_end(key)
        elif len(self._cache) >= self.max_size:
            self._cache.popitem(last=False)
        
        self._cache[key] = (value, time.time())
    
    def clear(self) -> None:
        """Clear all cache"""
        self._cache.clear()
    
    def delete(self, key: str) -> None:
        """Delete specific key from cache"""
        self._cache.pop(key, None)


def cached(ttl: int = 300):
    """Decorator for method caching"""
    def decorator(func):
        cache = TTLCache(ttl=ttl)
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Create cache key from function name and arguments
            key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
            
            # Try to get from cache
            cached_value = cache.get(key)
            if cached_value is not None:
                return cached_value
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            cache.set(key, result)
            return result
        
        return wrapper
    return decorator