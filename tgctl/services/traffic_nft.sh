#!/bin/bash
set -euo pipefail  # Безопасный режим: ошибки прерывают скрипт, неиспользуемые переменные - ошибка

export PATH=$PATH:/usr/sbin:/usr/local/sbin

LOCK_FILE="/tmp/traffic_nft.lock"
exec 200>"$LOCK_FILE"
flock -n 200 || exit 1

MAP_FILE="/opt/vlesstgctl/stats/ip_user_map.txt"
NFT_STATE_FILE="/opt/vlesstgctl/stats/user_nft_state.txt"
TOTAL_STATE_FILE="/opt/vlesstgctl/stats/user_total_state.txt"
LAST_ACTIVE_FILE="/opt/vlesstgctl/stats/user_last_active.txt"

# === 1. ПОЛУЧАЕМ ЛОГИ И ОЧИЩАЕМ ANSI ===
# Увеличил буфер до 20000 строк для активного трафика
LOGS=$(docker logs sing-box --tail 5000 2>&1 | sed -E 's/\x1b\[[0-9;]*m//g')

# === 2. МАППИНГ IP -> USER ПО ID ===
declare -A ID_TO_IP
declare -A ID_TO_USER

while IFS= read -r line; do
    if [[ "$line" =~ \[([0-9]+)\ .*inbound\ connection\ from\ ([0-9.]+) ]]; then
        id="${BASH_REMATCH[1]}"
        ip="${BASH_REMATCH[2]}"
        ID_TO_IP["$id"]="$ip"
    fi
done <<< "$LOGS"

while IFS= read -r line; do
    if [[ "$line" =~ \[([0-9]+)\ .*\[([A-Za-z0-9_]+)\].*inbound\ connection\ to ]]; then
        id="${BASH_REMATCH[1]}"
        user="${BASH_REMATCH[2]}"
        if [[ "$user" != "REALITY" && "$user" != "direct" ]]; then
            ID_TO_USER["$id"]="$user"
        fi
    fi
done <<< "$LOGS"

declare -A IP_TO_USER
for id in "${!ID_TO_IP[@]}"; do
    ip="${ID_TO_IP[$id]}"
    user="${ID_TO_USER[$id]}"
    if [[ -n "$ip" && -n "$user" ]]; then
        IP_TO_USER["$ip"]="$user"
    fi
done

if [[ -f "$MAP_FILE" ]]; then
    while IFS=':' read -r ip user; do
        [[ -z "${IP_TO_USER[$ip]}" ]] && IP_TO_USER["$ip"]="$user"
    done < "$MAP_FILE"
fi

> "$MAP_FILE"
for ip in "${!IP_TO_USER[@]}"; do
    echo "$ip:${IP_TO_USER[$ip]}" >> "$MAP_FILE"
done

# === 2.5. ОЧИСТКА СТАРЫХ ЦЕПОЧЕК (GARBAGE COLLECTION) ===
# Получаем список всех существующих цепочек traffic_*
ALL_CHAINS=$(/usr/sbin/nft list chains inet traffic 2>/dev/null | grep -oP 'traffic_(in|out)_[^\s]+' || true)

for chain in $ALL_CHAINS; do
    # Извлекаем IP из имени цепочки
    # Имена цепочек: traffic_in_username_1_2_3_4 или traffic_out_username_1_2_3_4
    # Нам нужно восстановить IP из последней части
    
    # Получаем суффикс после последнего подчеркивания
    suffix="${chain##*_}"
    # Пытаемся восстановить IP: 1_2_3_4 -> 1.2.3.4
    ip_candidate=$(echo "$suffix" | tr '_' '.')
    
    # Проверяем, является ли это валидным IP
    if [[ "$ip_candidate" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        # Если этого IP нет в текущем маппинге -> удаляем цепочку
        if [[ -z "${IP_TO_USER[$ip_candidate]:-}" ]]; then
            /usr/sbin/nft delete chain inet traffic "$chain" 2>/dev/null && \
                echo "Deleted old chain: $chain" >> /tmp/traffic_nft_cleanup.log
        fi
    fi
done

# === 3. NFT: СОЗДАЁМ ЦЕПОЧКИ ===
/usr/sbin/nft add table inet traffic 2>/dev/null

for ip in "${!IP_TO_USER[@]}"; do
    user="${IP_TO_USER[$ip]}"
    ip_clean="${ip//./_}"
    chain_in="traffic_in_${user}_${ip_clean}"
    chain_out="traffic_out_${user}_${ip_clean}"
    
    if ! /usr/sbin/nft list chain inet traffic "$chain_in" >/dev/null 2>&1; then
        /usr/sbin/nft add chain inet traffic "$chain_in" '{ type filter hook input priority 0; policy accept; }'
        /usr/sbin/nft add rule inet traffic "$chain_in" ip saddr "$ip" counter
    fi
    
    if ! /usr/sbin/nft list chain inet traffic "$chain_out" >/dev/null 2>&1; then
        /usr/sbin/nft add chain inet traffic "$chain_out" '{ type filter hook output priority 0; policy accept; }'
        /usr/sbin/nft add rule inet traffic "$chain_out" ip daddr "$ip" counter
    fi
done

# === 4. ЗАГРУЖАЕМ ПРОШЛЫЕ ПОКАЗАНИЯ NFT ===
declare -A PREV_NFT_UP
declare -A PREV_NFT_DOWN

if [[ -f "$NFT_STATE_FILE" ]]; then
    while IFS=':' read -r user up down; do
        PREV_NFT_UP["$user"]="$up"
        PREV_NFT_DOWN["$user"]="$down"
    done < "$NFT_STATE_FILE"
fi

# === 5. ЗАГРУЖАЕМ ОБЩИЙ ТРАФИК ===
declare -A TOTAL_UP
declare -A TOTAL_DOWN

if [[ -f "$TOTAL_STATE_FILE" ]]; then
    while IFS=':' read -r user up down; do
        TOTAL_UP["$user"]="$up"
        TOTAL_DOWN["$user"]="$down"
    done < "$TOTAL_STATE_FILE"
fi

# === 6. СБОР ТЕКУЩИХ ПОКАЗАНИЙ ИЗ NFT ===
declare -A CURRENT_NFT_UP
declare -A CURRENT_NFT_DOWN

for ip in "${!IP_TO_USER[@]}"; do
    user="${IP_TO_USER[$ip]}"
    ip_clean="${ip//./_}"
    chain_in="traffic_in_${user}_${ip_clean}"
    chain_out="traffic_out_${user}_${ip_clean}"
    
    up=0
    down=0
    
    in_rule=$(/usr/sbin/nft list chain inet traffic "$chain_in" 2>/dev/null | grep "ip saddr $ip")
    if [[ -n "$in_rule" && "$in_rule" =~ bytes\ ([0-9]+) ]]; then
        up="${BASH_REMATCH[1]}"
    fi
    
    out_rule=$(/usr/sbin/nft list chain inet traffic "$chain_out" 2>/dev/null | grep "ip daddr $ip")
    if [[ -n "$out_rule" && "$out_rule" =~ bytes\ ([0-9]+) ]]; then
        down="${BASH_REMATCH[1]}"
    fi
    
    CURRENT_NFT_UP["$user"]=$(( ${CURRENT_NFT_UP["$user"]:-0} + up ))
    CURRENT_NFT_DOWN["$user"]=$(( ${CURRENT_NFT_DOWN["$user"]:-0} + down ))
done

# === 7. СЧИТАЕМ ПРИРОСТ И ОБНОВЛЯЕМ ОБЩИЙ ТРАФИК ===
declare -A NEW_TOTAL_UP
declare -A NEW_TOTAL_DOWN
declare -A HAD_ACTIVITY

for user in "${!CURRENT_NFT_UP[@]}"; do
    current_up="${CURRENT_NFT_UP[$user]}"
    current_down="${CURRENT_NFT_DOWN[$user]}"
    
    prev_up="${PREV_NFT_UP[$user]:-0}"
    prev_down="${PREV_NFT_DOWN[$user]:-0}"
    
    delta_up=$((current_up - prev_up))
    delta_down=$((current_down - prev_down))
    
    # Защита от отрицательных значений (перезагрузка счетчиков)
    [[ $delta_up -lt 0 ]] && delta_up=$current_up
    [[ $delta_down -lt 0 ]] && delta_down=$current_down
    
    old_total_up="${TOTAL_UP[$user]:-0}"
    old_total_down="${TOTAL_DOWN[$user]:-0}"
    
    NEW_TOTAL_UP["$user"]=$((old_total_up + delta_up))
    NEW_TOTAL_DOWN["$user"]=$((old_total_down + delta_down))
    
    if [[ $delta_up -gt 0 || $delta_down -gt 0 ]]; then
        HAD_ACTIVITY["$user"]=1
    fi
done

# === 8. СОХРАНЯЕМ СОСТОЯНИЯ NFT ===
# Используем временный файл для атомарной записи
TEMP_NFT_STATE="${NFT_STATE_FILE}.tmp"
> "$TEMP_NFT_STATE"
for user in "${!CURRENT_NFT_UP[@]}"; do
    echo "$user:${CURRENT_NFT_UP[$user]}:${CURRENT_NFT_DOWN[$user]}" >> "$TEMP_NFT_STATE"
done
mv "$TEMP_NFT_STATE" "$NFT_STATE_FILE"

# === 9. СОХРАНЯЕМ ОБЩИЙ ТРАФИК ===
TEMP_TOTAL_STATE="${TOTAL_STATE_FILE}.tmp"
> "$TEMP_TOTAL_STATE"
for user in "${!NEW_TOTAL_UP[@]}"; do
    echo "$user:${NEW_TOTAL_UP[$user]}:${NEW_TOTAL_DOWN[$user]}" >> "$TEMP_TOTAL_STATE"
done
mv "$TEMP_TOTAL_STATE" "$TOTAL_STATE_FILE"

# === 10. ОБНОВЛЯЕМ last_active.txt ===
# Используем flock для безопасной записи
TEMP_LAST="/opt/vlesstgctl/stats/user_last_active.tmp"
> "$TEMP_LAST"

# Копируем старые записи, обновляя активных пользователей
if [[ -f "$LAST_ACTIVE_FILE" ]]; then
    # Используем flock для чтения
    (
        flock -s 200
        while IFS=':' read -r user ts; do
            if [[ -n "${HAD_ACTIVITY[$user]:-}" ]]; then
                # Активный пользователь - обновляем timestamp
                echo "$user:$(date +%s)" >> "$TEMP_LAST"
            else
                # Неактивный - оставляем старый
                echo "$user:$ts" >> "$TEMP_LAST"
            fi
        done < "$LAST_ACTIVE_FILE"
    ) 200>"$LAST_ACTIVE_FILE.lock"
fi

# Добавляем новых пользователей, которых нет в старом файле
for user in "${!NEW_TOTAL_UP[@]}"; do
    if ! grep -q "^$user:" "$TEMP_LAST" 2>/dev/null; then
        echo "$user:$(date +%s)" >> "$TEMP_LAST"
    fi
done

# Атомарно заменяем файл
mv "$TEMP_LAST" "$LAST_ACTIVE_FILE"

# === 11. ВЫВОД JSON ===
{
    echo "["
    first=true
    for user in $(printf "%s\n" "${!NEW_TOTAL_UP[@]}" | sort); do
        if [ "$first" = true ]; then
            first=false
        else
            echo ","
        fi
        # Экранируем спецсимволы в имени пользователя для JSON
        user_escaped=$(printf "%s" "$user" | jq -R -r @json 2>/dev/null || echo "\"$user\"")
        printf '{"user":%s,"upload":%s,"download":%s,"total":%s}' \
            "$user_escaped" \
            "${NEW_TOTAL_UP[$user]}" \
            "${NEW_TOTAL_DOWN[$user]}" \
            "$(( ${NEW_TOTAL_UP[$user]} + ${NEW_TOTAL_DOWN[$user]} ))"
    done
    echo
    echo "]"
} > /opt/vlesstgctl/stats/traffic.json.tmp
mv /opt/vlesstgctl/stats/traffic.json.tmp /opt/vlesstgctl/stats/traffic.json

flock -u 200
rm -f "$LOCK_FILE"
