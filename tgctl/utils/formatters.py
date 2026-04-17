from typing import Union


def format_bytes(bytes_num: Union[int, float]) -> str:
    """Format bytes to human readable format"""
    if bytes_num == 0:
        return "0 B"
    
    bytes_num = float(bytes_num)
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    
    for unit in units:
        if bytes_num < 1024.0:
            return f"{bytes_num:.2f} {unit}"
        bytes_num /= 1024.0
    
    return f"{bytes_num:.2f} PB"


def format_username_for_display(username: str, max_length: int = 20) -> str:
    """Format username for display, truncate if too long"""
    if len(username) > max_length:
        return username[:max_length-3] + "..."
    return username


def format_duration(seconds: int) -> str:
    """Format seconds to human readable duration"""
    if seconds < 60:
        return f"{seconds} сек"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes} мин"
    elif seconds < 86400:
        hours = seconds // 3600
        return f"{hours} ч"
    else:
        days = seconds // 86400
        return f"{days} д"