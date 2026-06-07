import json
from io import BytesIO
from typing import Dict, Any
import qrcode
from models import Platform, ServerConfig
from config import Config


class ConfigGenerator:
    """Generate client configurations"""
    
    def __init__(self, server_config: ServerConfig):
        self.server = server_config
    
    def generate_client_config(self, username: str, user_uuid: str, platform: Platform) -> Dict[str, Any]:
        """Generate sing-box client configuration"""
        
        # DNS configuration based on platform
        dns_servers = [
            {"tag": "dns-direct", "server": "208.67.222.220", "server_port": 5353},
            {"tag": "dns-remote", "server": "dns.google", "server_port": 853, "detour": "vless-out"}
        ]
        
        if platform == Platform.ANDROID:
            dns_servers[0]["type"] = "udp"
            dns_servers[1]["type"] = "tls"
        elif platform == Platform.IOS:
            dns_servers[0]["type"] = "udp"
            dns_servers[1]["type"] = "tls"
        
        return {
            "log": {"level": "warn"},
            "dns": {
                "servers": dns_servers,
                "rules": [
                    {
                        "domain": [self.server.domain, "github.com", "raw.githubusercontent.com", "dns.google"],
                        "server": "dns-direct"
                    },
                    {"server": "dns-remote"}
                ],
                "strategy": "prefer_ipv4"
            },
            "inbounds": [{
                "type": "tun",
                "tag": "tun-in",
                "interface_name": "tun0",
                "mtu": 1400,
                "address": "172.19.0.1/30",
                "auto_route": True,
                "strict_route": True,
                "stack": "system"
            }],
            "outbounds": [
                {"type": "direct", "tag": "direct"},
                {
                    "type": "vless",
                    "tag": "vless-out",
                    "server": self.server.domain,
                    "server_port": int(self.server.port),
                    "uuid": user_uuid,
                    "flow": "xtls-rprx-vision",
                    "tls": {
                        "enabled": True,
                        "server_name": self.server.vless_sni,
                        "utls": {"enabled": True, "fingerprint": "qq"},
                        "reality": {
                            "enabled": True,
                            "public_key": self.server.public_key,
                            "short_id": self.server.short_id
                        }
                    }
                }
            ],
            "route": {
                "default_domain_resolver": "dns-direct",
                "rule_set": [{
                    "tag": "geoip-ru",
                    "type": "remote",
                    "format": "binary",
                    "url": "https://github.com/SagerNet/sing-geoip/raw/rule-set/geoip-ru.srs",
                    "download_detour": "direct"
                }],
                "rules": [
                    {
                        "domain": [self.server.domain, "github.com", "raw.githubusercontent.com"],
                        "outbound": "direct"
                    },
                    {"rule_set": ["geoip-ru"], "outbound": "direct"}
                ],
                "final": "vless-out",
                "auto_detect_interface": True
            }
        }
    
    def generate_vless_link(self, username: str, user_uuid: str) -> str:
        """Generate VLESS link for QR code"""
        return (
            f"vless://{user_uuid}@{self.server.domain}:{self.server.port}"
            f"?encryption=none&security=reality&flow=xtls-rprx-vision"
            f"&type=tcp&sni={self.server.vless_sni}"
            f"&pbk={self.server.public_key}&sid={self.server.short_id}"
            f"&fp=chrome#{username}"
        )
    
    @staticmethod
    def generate_qr_code(data: str) -> BytesIO:
        """Generate QR code image from data"""
        qr = qrcode.QRCode(
            version=1,
            box_size=6,
            border=2
        )
        qr.add_data(data)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        bio = BytesIO()
        img.save(bio, 'PNG')
        bio.seek(0)
        return bio
