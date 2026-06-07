from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class Platform(str, Enum):
    ANDROID = "android"
    IOS = "ios"


class UserStatus(str, Enum):
    ACTIVE = "active"
    DISABLED = "disabled"
    EXPIRED = "expired"


@dataclass
class User:
    """User model"""
    name: str
    uuid: str
    status: UserStatus = UserStatus.ACTIVE
    created_at: datetime = None
    telegram_id: Optional[int] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        data['status'] = self.status.value
        data['created_at'] = self.created_at.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'User':
        """Create User from dictionary"""
        data['status'] = UserStatus(data.get('status', 'active'))
        if 'created_at' in data and data['created_at']:
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        return cls(**data)


@dataclass
class TrafficStats:
    """Traffic statistics model"""
    user: str
    upload: int = 0
    download: int = 0
    total: int = 0
    last_updated: Optional[datetime] = None
    
    def update(self, upload: int, download: int) -> None:
        """Update traffic stats"""
        self.upload = upload
        self.download = download
        self.total = upload + download
        self.last_updated = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'user': self.user,
            'upload': self.upload,
            'download': self.download,
            'total': self.total,
            'last_updated': self.last_updated.isoformat() if self.last_updated else None
        }


@dataclass
class ServerConfig:
    """Server configuration model"""
    domain: str
    port: str
    public_key: str
    short_id: str
    vless_sni: str
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ServerConfig':
        return cls(
            domain=data.get('domain', ''),
            port=data.get('port', '6443'),
            public_key=data.get('public_key', ''),
            short_id=data.get('short_id', ''),
            vless_sni=data.get('vless_sni', '')
        )
