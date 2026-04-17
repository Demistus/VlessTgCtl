#!/bin/bash
set -e

echo "=== Установка VlessTgCtl (Telegram Bot + sing-box) ==="

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. Проверка прав root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}❌ Пожалуйста, запустите с sudo: sudo bash install.sh${NC}"
    exit 1
fi

# 2. Установка базовых зависимостей
echo -e "${YELLOW}[1/9] Установка зависимостей...${NC}"
apt-get update && apt-get install -y jq nftables git curl wget

# 3. Установка Docker
echo -e "${YELLOW}[2/9] Установка Docker...${NC}"
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
fi

# 4. Установка Docker Compose
echo -e "${YELLOW}[3/9] Установка Docker Compose...${NC}"
if ! command -v docker-compose &> /dev/null; then
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
fi

# 5. Клонирование репозитория
echo -e "${YELLOW}[4/9] Клонирование репозитория VlessTgCtl...${NC}"
cd /opt
rm -rf vlesstgctl
git clone https://github.com/Demistus/VlessTgCtl.git vlesstgctl
cd vlesstgctl

# 6. Запрос переменных
echo -e "${YELLOW}[5/9] Настройка бота...${NC}"
echo "Введите BOT_TOKEN (получите у @BotFather):"
read -r BOT_TOKEN </dev/tty
echo "Введите ADMIN_IDS (ваш Telegram ID, можно несколько через запятую):"
read -r ADMIN_IDS </dev/tty

# 7. Создание .env файла
echo -e "${YELLOW}[6/9] Создание .env файла...${NC}"
cat > .env << ENV_EOF
BOT_TOKEN=$BOT_TOKEN
ADMIN_IDS=$ADMIN_IDS
ENV_EOF

# 8. Создание директорий (в соответствии с config.py)
echo -e "${YELLOW}[7/9] Создание директорий...${NC}"
mkdir -p /opt/vlesstgctl/data
mkdir -p /opt/vlesstgctl/stats
mkdir -p /etc/sing-box

# 9. Копирование конфига sing-box из vless/
echo -e "${YELLOW}[8/9] Установка конфига sing-box...${NC}"
if [ -f vless/config.json ]; then
    cp vless/config.json /etc/sing-box/config.json
    echo -e "${GREEN}✅ Конфиг sing-box скопирован${NC}"
else
    echo -e "${RED}❌ Файл vless/config.json не найден!${NC}"
    exit 1
fi

# 10. Копирование скрипта трафика (новый путь)
echo -e "${YELLOW}[9/9] Настройка сбора статистики...${NC}"
# Ищем traffic_nft.sh в новой структуре
if [ -f tgctl/services/traffic_nft.sh ]; then
    cp tgctl/services/traffic_nft.sh /opt/vlesstgctl/stats/traffic_nft.sh
elif [ -f scripts/traffic_nft.sh ]; then
    # fallback для совместимости
    cp scripts/traffic_nft.sh /opt/vlesstgctl/stats/traffic_nft.sh
else
    echo -e "${RED}❌ traffic_nft.sh не найден!${NC}"
    exit 1
fi
chmod +x /opt/vlesstgctl/stats/traffic_nft.sh

# 11. Настройка systemd сервиса для сбора статистики
cat > /etc/systemd/system/traffic-stats.service << 'EOF'
[Unit]
Description=VlessTgCtl Traffic Statistics Collector
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

# 12. Создание docker-compose.yml
echo -e "${YELLOW}Создание docker-compose.yml...${NC}"
cat > docker-compose.yml << 'DOCKER_COMPOSE_EOF'
version: '3.8'

services:
  sing-box:
    build:
      context: .
      dockerfile: vless/Dockerfile.vless
    container_name: sing-box
    restart: unless-stopped
    network_mode: host
    cap_add:
      - NET_ADMIN
      - SYS_ADMIN
    volumes:
      - /etc/sing-box/config.json:/etc/sing-box/config.json:rw
      - /opt/vlesstgctl/data:/opt/vlesstgctl/data
      - /opt/vlesstgctl/stats:/opt/vlesstgctl/stats
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  telegram-bot:
    build:
      context: .
      dockerfile: tgctl/Dockerfile.tgctl
    container_name: telegram-bot
    restart: unless-stopped
    depends_on:
      - sing-box
    environment:
      - BOT_TOKEN=${BOT_TOKEN}
      - ADMIN_IDS=${ADMIN_IDS}
    volumes:
      - /etc/sing-box/config.json:/etc/sing-box/config.json:rw
      - /opt/vlesstgctl/data:/opt/vlesstgctl/data
      - /opt/vlesstgctl/stats:/opt/vlesstgctl/stats
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
DOCKER_COMPOSE_EOF

# 13. Сборка и запуск
echo -e "${YELLOW}Сборка и запуск контейнеров (может занять несколько минут)...${NC}"
docker-compose down 2>/dev/null || true
docker-compose build --no-cache
docker-compose up -d

# 14. Проверка статуса
echo -e "${YELLOW}Проверка статуса контейнеров...${NC}"
sleep 5
if docker ps | grep -q "sing-box"; then
    echo -e "${GREEN}✅ sing-box запущен${NC}"
else
    echo -e "${RED}❌ Ошибка запуска sing-box${NC}"
    docker logs sing-box --tail 20
fi

if docker ps | grep -q "telegram-bot"; then
    echo -e "${GREEN}✅ Telegram бот запущен${NC}"
else
    echo -e "${RED}❌ Ошибка запуска бота${NC}"
    docker logs telegram-bot --tail 20
fi

# 15. Создание скрипта удаления
cat > /opt/vlesstgctl/uninstall.sh << 'UNINSTALL_EOF'
#!/bin/bash
echo "=== Удаление VlessTgCtl ==="
cd /opt/vlesstgctl 2>/dev/null && docker-compose down 2>/dev/null
docker rmi vlesstgctl_sing-box vlesstgctl_telegram-bot 2>/dev/null
rm -rf /opt/vlesstgctl
rm -rf /etc/sing-box
systemctl disable traffic-stats.timer
systemctl stop traffic-stats.timer
rm -f /etc/systemd/system/traffic-stats.{service,timer}
systemctl daemon-reload
echo "✅ Удаление завершено"
UNINSTALL_EOF
chmod +x /opt/vlesstgctl/uninstall.sh

echo ""
echo "╔════════════════════════════════════════════════════════════════════════╗"
echo "║                    ✅ УСТАНОВКА VlessTgCtl ЗАВЕРШЕНА                   ║"
echo "╠════════════════════════════════════════════════════════════════════════╣"
echo "║  📁 Директория:        /opt/vlesstgctl                                  ║"
echo "║  🔧 Конфиг sing-box:   /etc/sing-box/config.json                        ║"
echo "║  📊 Статистика:        /opt/vlesstgctl/stats/traffic.json               ║"
echo "║  👥 Маппинг юзеров:    /opt/vlesstgctl/data/telegram_users.json         ║"
echo "║  🤖 Логи бота:         docker logs telegram-bot                         ║"
echo "║  🌐 Логи sing-box:     docker logs sing-box                             ║"
echo "║  🔄 Обновление стат.:  каждые 5 минут (timer)                           ║"
echo "║  🧹 Удаление:          /opt/vlesstgctl/uninstall.sh                     ║"
echo "╚════════════════════════════════════════════════════════════════════════╝"
echo ""
echo -e "${GREEN}📱 Откройте Telegram и напишите /start вашему боту${NC}"
