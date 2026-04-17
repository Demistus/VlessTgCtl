#!/bin/bash
set -e

echo "=== Установка VlessTgCtl (Telegram Bot + sing-box) ==="

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}❌ Запустите с sudo: sudo bash install.sh${NC}"
    exit 1
fi

echo -e "${YELLOW}[1/9] Установка зависимостей...${NC}"
apt-get update && apt-get install -y jq nftables git curl wget

echo -e "${YELLOW}[2/9] Установка Docker...${NC}"
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
fi

echo -e "${YELLOW}[3/9] Установка Docker Compose...${NC}"
if ! command -v docker-compose &> /dev/null; then
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
fi

echo -e "${YELLOW}[4/9] Клонирование репозитория...${NC}"
cd /opt
rm -rf vlesstgctl
git clone https://github.com/Demistus/VlessTgCtl.git vlesstgctl
cd vlesstgctl

# Копируем requirements.txt в tgctl/ если его там нет
if [ -f requirements.txt ] && [ ! -f tgctl/requirements.txt ]; then
    cp requirements.txt tgctl/
fi

echo -e "${YELLOW}[5/9] Настройка бота...${NC}"
echo "Введите BOT_TOKEN:"
read -r BOT_TOKEN </dev/tty
echo "Введите ADMIN_IDS (Telegram ID, можно через запятую):"
read -r ADMIN_IDS </dev/tty

cat > .env << ENV_EOF
BOT_TOKEN=$BOT_TOKEN
ADMIN_IDS=$ADMIN_IDS
ENV_EOF

echo -e "${YELLOW}[6/9] Создание директорий...${NC}"
mkdir -p /opt/vlesstgctl/data
mkdir -p /opt/vlesstgctl/stats
mkdir -p /etc/sing-box

echo -e "${YELLOW}[7/9] Установка конфига sing-box...${NC}"
if [ -f vless/config.json ]; then
    cp vless/config.json /etc/sing-box/config.json
else
    echo -e "${RED}❌ vless/config.json не найден${NC}"
    exit 1
fi

echo -e "${YELLOW}[8/9] Настройка статистики...${NC}"
# Ищем скрипт трафика
if [ -f tgctl/services/traffic_nft.sh ]; then
    cp tgctl/services/traffic_nft.sh /opt/vlesstgctl/stats/traffic_nft.sh
elif [ -f services/traffic_nft.sh ]; then
    cp services/traffic_nft.sh /opt/vlesstgctl/stats/traffic_nft.sh
else
    echo -e "${RED}❌ traffic_nft.sh не найден${NC}"
    exit 1
fi
chmod +x /opt/vlesstgctl/stats/traffic_nft.sh

cat > /etc/systemd/system/traffic-stats.service << 'EOF'
[Unit]
Description=VlessTgCtl Traffic Stats
After=docker.service

[Service]
Type=oneshot
ExecStart=/opt/vlesstgctl/stats/traffic_nft.sh
StandardOutput=journal
StandardError=journal
User=root
EOF

cat > /etc/systemd/system/traffic-stats.timer << 'EOF'
[Unit]
Description=Run traffic-stats every 5 minutes

[Timer]
OnCalendar=*:0/5
Persistent=true

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable traffic-stats.timer
systemctl start traffic-stats.timer

echo "[7/8] Настройка nftables..."
cat > /etc/nftables.conf << 'NFT_EOF'
#!/usr/sbin/nft -f

flush ruleset

table ip filter {
    chain input {
        type filter hook input priority filter; policy drop;
        
        ct state established,related accept
        iif lo accept
        ip protocol icmp icmp type echo-request accept
        tcp dport 22 accept
        tcp dport {80, 443, 8080} accept
        udp dport 443 accept
        
        log prefix "BLOCKED: " limit rate 5/minute
        reject with icmp type port-unreachable
    }
    
    chain forward {
        type filter hook forward priority filter; policy drop;
        ct state established,related accept
    }
    
    chain output {
        type filter hook output priority filter; policy accept;
    }
}
NFT_EOF

nft -f /etc/nftables.conf
systemctl enable nftables
systemctl restart nftables

echo -e "${YELLOW}[9/9] Сборка и запуск контейнеров...${NC}"
cat > docker-compose.yml << 'DOCKER_EOF'
version: '3.8'

services:
  sing-box:
    build:
      context: ./vless
      dockerfile: Dockerfile.vless
    container_name: sing-box
    restart: unless-stopped
    network_mode: host
    cap_add:
      - NET_ADMIN
    volumes:
      - /etc/sing-box:/etc/sing-box
      - /var/lib/sing-box:/var/lib/sing-box
      - /var/log/sing-box:/var/log/sing-box
      - /dev/net/tun:/dev/net/tun

  telegram-bot:
    build:
      context: ./tgctl
      dockerfile: Dockerfile.tgctl
    container_name: telegram-bot
    restart: unless-stopped
    network_mode: host
    env_file:
      - .env
    volumes:
      - ./data:/app/data
      - /opt/vlesstgctl/stats:/opt/vlesstgctl/stats
      - /etc/sing-box:/etc/sing-box:rw
      - /usr/bin/docker:/usr/bin/docker
      - /var/run/docker.sock:/var/run/docker.sock
    depends_on:
      - sing-box

DOCKER_EOF

docker-compose down 2>/dev/null || true
docker-compose build --no-cache
docker-compose up -d

sleep 5
echo -e "${GREEN}✅ Статус контейнеров:${NC}"
docker ps --format "table {{.Names}}\t{{.Status}}" | grep -E "sing-box|telegram-bot"

cat > /opt/vlesstgctl/uninstall.sh << 'UNINSTALL'
#!/bin/bash
cd /opt/vlesstgctl && docker-compose down
docker rmi vlesstgctl-sing-box:latest vlesstgctl-telegram-bot:latest
docker builder prune -a -f
rm -rf /opt/vlesstgctl /etc/sing-box
systemctl disable --now traffic-stats.timer
rm -f /etc/systemd/system/traffic-stats.{service,timer}
systemctl daemon-reload
echo "✅ Удалено"
UNINSTALL
chmod +x /opt/vlesstgctl/uninstall.sh

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║              ✅ УСТАНОВКА VlessTgCtl ЗАВЕРШЕНА                 ║"
echo "╠════════════════════════════════════════════════════════════════╣"
echo "║  📁 Проект:       /opt/vlesstgctl                              ║"
echo "║  🤖 Логи бота:    docker logs telegram-bot                     ║"
echo "║  🌐 Логи sing-box: docker logs sing-box                        ║"
echo "║  🧹 Удаление:     /opt/vlesstgctl/uninstall.sh                 ║"
echo "╚════════════════════════════════════════════════════════════════╝"
