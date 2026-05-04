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

echo -e "${YELLOW}[1/10] Установка зависимостей...${NC}"
apt-get update && apt-get install -y jq nftables git curl wget openssl

echo -e "${YELLOW}[2/10] Установка Docker...${NC}"
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
fi

echo -e "${YELLOW}[3/10] Установка Docker Compose...${NC}"
if ! command -v docker-compose &> /dev/null; then
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
fi

echo -e "${YELLOW}[3.5/10] Установка wgcf...${NC}"
case "$(uname -m)" in
    x86_64|amd64) WGCF_ARCH="amd64" ;;
    aarch64|arm64) WGCF_ARCH="arm64" ;;
    armv7l) WGCF_ARCH="armv7" ;;
    armv6l) WGCF_ARCH="armv6" ;;
    armv5l) WGCF_ARCH="armv5" ;;
    i386|i686) WGCF_ARCH="386" ;;
    *)
        echo -e "${RED}❌ Неподдерживаемая архитектура для wgcf: $(uname -m)${NC}"
        exit 1
        ;;
esac

WGCF_VERSION=$(curl -fsSL https://api.github.com/repos/ViRb3/wgcf/releases/latest | jq -r '.tag_name | ltrimstr("v")')
if [ -z "$WGCF_VERSION" ] || [ "$WGCF_VERSION" = "null" ]; then
    echo -e "${RED}❌ Не удалось определить последнюю версию wgcf${NC}"
    exit 1
fi

WGCF_URL="https://github.com/ViRb3/wgcf/releases/download/v${WGCF_VERSION}/wgcf_${WGCF_VERSION}_linux_${WGCF_ARCH}"
curl -fL "$WGCF_URL" -o /usr/local/bin/wgcf
chmod +x /usr/local/bin/wgcf

echo -e "${YELLOW}[4/10] Клонирование репозитория...${NC}"
cd /opt
rm -rf vlesstgctl
git clone https://github.com/Demistus/VlessTgCtl.git vlesstgctl
cd vlesstgctl

# Копируем requirements.txt в tgctl/ если его там нет
if [ -f requirements.txt ] && [ ! -f tgctl/requirements.txt ]; then
    cp requirements.txt tgctl/
fi

echo -e "${YELLOW}[5/10] Настройка бота...${NC}"
echo "Введите BOT_TOKEN:"
read -r BOT_TOKEN </dev/tty
echo "Введите ADMIN_IDS (Telegram ID, можно через запятую):"
read -r ADMIN_IDS </dev/tty
echo "Введите домен сервера (например vpn.example.com):"
read -r SERVER_DOMAIN </dev/tty
echo "Введите SNI для REALITY [www.microsoft.com]:"
read -r VLESS_SNI </dev/tty
VLESS_SNI=${VLESS_SNI:-www.microsoft.com}
VLESS_PORT=443

if [ -z "$SERVER_DOMAIN" ]; then
    echo -e "${RED}❌ SERVER_DOMAIN не может быть пустым${NC}"
    exit 1
fi

cat > .env << ENV_EOF
BOT_TOKEN=$BOT_TOKEN
ADMIN_IDS=$ADMIN_IDS
SERVER_DOMAIN=$SERVER_DOMAIN
VLESS_PORT=$VLESS_PORT
VLESS_SNI=$VLESS_SNI
ENV_EOF

echo -e "${YELLOW}[6/10] Создание директорий...${NC}"
mkdir -p /opt/vlesstgctl/data
mkdir -p /opt/vlesstgctl/stats
mkdir -p /etc/sing-box

echo -e "${YELLOW}[7/10] Установка конфига sing-box...${NC}"
if [ -f vless/config.json ]; then
    echo "Генерируем ключи REALITY..."
    docker build -t vlesstgctl-sing-box:latest -f vless/Dockerfile.vless vless
    KEYPAIR=$(docker run --rm --entrypoint sing-box vlesstgctl-sing-box:latest generate reality-keypair)
    REALITY_PRIVATE_KEY=$(printf "%s\n" "$KEYPAIR" | awk -F': *' 'tolower($1) ~ /private/ {print $2; exit}')
    REALITY_PUBLIC_KEY=$(printf "%s\n" "$KEYPAIR" | awk -F': *' 'tolower($1) ~ /public/ {print $2; exit}')
    REALITY_SHORT_ID=$(openssl rand -hex 8)

    if [ -z "$REALITY_PRIVATE_KEY" ] || [ -z "$REALITY_PUBLIC_KEY" ]; then
        echo -e "${RED}❌ Не удалось сгенерировать REALITY keypair${NC}"
        echo "$KEYPAIR"
        exit 1
    fi

    echo "Регистрируем Cloudflare WARP и генерируем WireGuard профиль..."
    WARP_WORKDIR=$(mktemp -d)
    trap 'rm -rf "$WARP_WORKDIR"' EXIT
    (
        cd "$WARP_WORKDIR"
        wgcf register --accept-tos
        wgcf generate
    )

    WARP_PROFILE="$WARP_WORKDIR/wgcf-profile.conf"
    if [ ! -f "$WARP_PROFILE" ]; then
        echo -e "${RED}❌ wgcf не создал wgcf-profile.conf${NC}"
        exit 1
    fi

    WARP_PRIVATE_KEY=$(awk -F'= *' '
        /^\[Interface\]/ { section = "interface"; next }
        /^\[Peer\]/ { section = "peer"; next }
        section == "interface" && $1 ~ /^[[:space:]]*PrivateKey[[:space:]]*$/ {
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", $2); print $2; exit
        }
    ' "$WARP_PROFILE")
    WARP_ADDRESSES=$(awk -F'= *' '
        /^\[Interface\]/ { section = "interface"; next }
        /^\[Peer\]/ { section = "peer"; next }
        section == "interface" && $1 ~ /^[[:space:]]*Address[[:space:]]*$/ {
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", $2); print $2; exit
        }
    ' "$WARP_PROFILE")
    WARP_PEER_PUBLIC_KEY=$(awk -F'= *' '
        /^\[Interface\]/ { section = "interface"; next }
        /^\[Peer\]/ { section = "peer"; next }
        section == "peer" && $1 ~ /^[[:space:]]*PublicKey[[:space:]]*$/ {
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", $2); print $2; exit
        }
    ' "$WARP_PROFILE")
    WARP_ENDPOINT=$(awk -F'= *' '
        /^\[Interface\]/ { section = "interface"; next }
        /^\[Peer\]/ { section = "peer"; next }
        section == "peer" && $1 ~ /^[[:space:]]*Endpoint[[:space:]]*$/ {
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", $2); print $2; exit
        }
    ' "$WARP_PROFILE")
    WARP_ENDPOINT_HOST="${WARP_ENDPOINT%:*}"
    WARP_ENDPOINT_PORT="${WARP_ENDPOINT##*:}"
    WARP_ADDRESSES_JSON=$(printf "%s" "$WARP_ADDRESSES" | jq -R 'split(",") | map(gsub("^[[:space:]]+|[[:space:]]+$"; ""))')

    if [ -z "$WARP_PRIVATE_KEY" ] || [ -z "$WARP_ADDRESSES" ] || [ -z "$WARP_PEER_PUBLIC_KEY" ] || [ -z "$WARP_ENDPOINT_HOST" ] || [ -z "$WARP_ENDPOINT_PORT" ]; then
        echo -e "${RED}❌ Не удалось разобрать WARP профиль wgcf${NC}"
        cat "$WARP_PROFILE"
        exit 1
    fi

    jq \
        --arg sni "$VLESS_SNI" \
        --arg private_key "$REALITY_PRIVATE_KEY" \
        --arg short_id "$REALITY_SHORT_ID" \
        --arg warp_private_key "$WARP_PRIVATE_KEY" \
        --argjson warp_addresses "$WARP_ADDRESSES_JSON" \
        --arg warp_peer_public_key "$WARP_PEER_PUBLIC_KEY" \
        --arg warp_endpoint_host "$WARP_ENDPOINT_HOST" \
        --argjson warp_endpoint_port "$WARP_ENDPOINT_PORT" \
        '(.inbounds[] | select(.type == "vless").listen_port) = 443 |
         (.inbounds[] | select(.type == "vless").tls.server_name) = $sni |
         (.inbounds[] | select(.type == "vless").tls.reality.handshake.server) = $sni |
         (.inbounds[] | select(.type == "vless").tls.reality.private_key) = $private_key |
         (.inbounds[] | select(.type == "vless").tls.reality.short_id) = $short_id |
         (.endpoints[] | select(.type == "wireguard" and .tag == "warp-out").private_key) = $warp_private_key |
         (.endpoints[] | select(.type == "wireguard" and .tag == "warp-out").address) = $warp_addresses |
         (.endpoints[] | select(.type == "wireguard" and .tag == "warp-out").peers[0].public_key) = $warp_peer_public_key |
         (.endpoints[] | select(.type == "wireguard" and .tag == "warp-out").peers[0].address) = $warp_endpoint_host |
         (.endpoints[] | select(.type == "wireguard" and .tag == "warp-out").peers[0].port) = $warp_endpoint_port' \
        vless/config.json > /etc/sing-box/config.json
    rm -rf "$WARP_WORKDIR"
    trap - EXIT

    cat >> .env << ENV_EOF
REALITY_PUBLIC_KEY=$REALITY_PUBLIC_KEY
REALITY_SHORT_ID=$REALITY_SHORT_ID
ENV_EOF
else
    echo -e "${RED}❌ vless/config.json не найден${NC}"
    exit 1
fi

echo -e "${YELLOW}[8/10] Настройка статистики...${NC}"
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

echo -e "${YELLOW}[9/10] Подготовка деинсталлятора...${NC}"
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

echo -e "${YELLOW}[10/10] Сборка и запуск контейнеров...${NC}"
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
      - ./data:/opt/vlesstgctl/data
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

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║              ✅ УСТАНОВКА VlessTgCtl ЗАВЕРШЕНА                 ║"
echo "╠════════════════════════════════════════════════════════════════╣"
echo "║  📁 Проект:       /opt/vlesstgctl                              ║"
echo "║  🤖 Логи бота:    docker logs telegram-bot                     ║"
echo "║  🌐 Логи sing-box: docker logs sing-box                        ║"
echo "║  🧹 Удаление:     /opt/vlesstgctl/uninstall.sh                 ║"
echo "╚════════════════════════════════════════════════════════════════╝"
