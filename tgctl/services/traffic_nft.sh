#!/bin/bash
set -euo pipefail

export PATH=$PATH:/usr/sbin:/usr/local/sbin

LOCK_FILE="/tmp/traffic_nft.lock"
exec 200>"$LOCK_FILE"
flock -n 200 || exit 1

MAP_FILE="/opt/vlesstgctl/stats/ip_user_map.txt"
NFT_STATE_FILE="/opt/vlesstgctl/stats/user_nft_state.txt"
TOTAL_STATE_FILE="/opt/vlesstgctl/stats/user_total_state.txt"
LAST_ACTIVE_FILE="/opt/vlesstgctl/stats/user_last_active.txt"
MAP_TTL_SECONDS=1800
CURRENT_TS=$(date +%s)

# === 1. ПОЛУЧАЕМ ЛОГИ И ОЧИЩАЕМ ANSI ===
LOGS=$(docker logs sing-box --since 10m --tail 5000 2>&1 | sed -E 's/\x1b\[[0-9;]*m//g')

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
declare -A IP_TO_SEEN
for id in "${!ID_TO_IP[@]}"; do
    ip="${ID_TO_IP[$id]}"
    # ИСПРАВЛЕНО: проверяем существование ключа с :- синтаксисом
    user="${ID_TO_USER[$id]:-}"
    if [[ -n "$ip" && -n "$user" ]]; then
        IP_TO_USER["$ip"]="$user"
        IP_TO_SEEN["$ip"]="$CURRENT_TS"
    fi
done

if [[ -f "$MAP_FILE" ]]; then
    while IFS=':' read -r ip user seen_at _; do
        seen_at="${seen_at:-0}"
        if [[ "$seen_at" =~ ^[0-9]+$ ]] && (( CURRENT_TS - seen_at <= MAP_TTL_SECONDS )); then
            # ИСПРАВЛЕНО: используем безопасную проверку
            if [[ -z "${IP_TO_USER[$ip]:-}" ]]; then
                IP_TO_USER["$ip"]="$user"
                IP_TO_SEEN["$ip"]="$seen_at"
            fi
        fi
    done < "$MAP_FILE"
fi

> "$MAP_FILE"
for ip in "${!IP_TO_USER[@]}"; do
    echo "$ip:${IP_TO_USER[$ip]}:${IP_TO_SEEN[$ip]:-$CURRENT_TS}" >> "$MAP_FILE"
done

# Старые цепочки не удаляем: их nft-счетчики являются источником данных
# для админки, даже если IP уже выпал из свежих логов или map-файла.

# === 3. NFT: СОЗДАЁМ ТАБЛИЦУ И ЦЕПОЧКИ ===
if ! /usr/sbin/nft list table inet traffic >/dev/null 2>&1; then
    /usr/sbin/nft add table inet traffic
fi

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

# === 6. СБОР ВСЕХ ТЕКУЩИХ ПОКАЗАНИЙ ИЗ NFT ===
declare -A CURRENT_NFT_UP
declare -A CURRENT_NFT_DOWN

NFT_TABLE=$(/usr/sbin/nft list table inet traffic 2>/dev/null || true)
current_chain=""
current_user=""
current_direction=""

while IFS= read -r line; do
    if [[ "$line" =~ ^[[:space:]]*chain[[:space:]]+(traffic_(in|out)_(.+)_([0-9]+_[0-9]+_[0-9]+_[0-9]+))[[:space:]]*\{ ]]; then
        current_chain="${BASH_REMATCH[1]}"
        current_direction="${BASH_REMATCH[2]}"
        current_user="${BASH_REMATCH[3]}"
        continue
    fi

    if [[ "$line" =~ ^[[:space:]]*\} ]]; then
        current_chain=""
        current_user=""
        current_direction=""
        continue
    fi

    if [[ -n "$current_chain" && "$line" =~ counter[[:space:]]+packets[[:space:]]+[0-9]+[[:space:]]+bytes[[:space:]]+([0-9]+) ]]; then
        bytes="${BASH_REMATCH[1]}"
        if [[ "$current_direction" == "in" ]]; then
            CURRENT_NFT_UP["$current_user"]=$(( ${CURRENT_NFT_UP["$current_user"]:-0} + bytes ))
        else
            CURRENT_NFT_DOWN["$current_user"]=$(( ${CURRENT_NFT_DOWN["$current_user"]:-0} + bytes ))
        fi
    fi
done <<< "$NFT_TABLE"

# === 7. СЧИТАЕМ ПРИРОСТ И ОБНОВЛЯЕМ ОБЩИЙ ТРАФИК ===
declare -A NEW_TOTAL_UP
declare -A NEW_TOTAL_DOWN
declare -A HAD_ACTIVITY
declare -A CURRENT_USERS

for user in "${!CURRENT_NFT_UP[@]}"; do
    CURRENT_USERS["$user"]=1
done

for user in "${!CURRENT_NFT_DOWN[@]}"; do
    CURRENT_USERS["$user"]=1
done

for user in "${!CURRENT_USERS[@]}"; do
    current_up="${CURRENT_NFT_UP[$user]:-0}"
    current_down="${CURRENT_NFT_DOWN[$user]:-0}"
    
    prev_up="${PREV_NFT_UP[$user]:-0}"
    prev_down="${PREV_NFT_DOWN[$user]:-0}"
    
    delta_up=$((current_up - prev_up))
    delta_down=$((current_down - prev_down))
    
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

# Сохраняем пользователей без текущих nft-цепочек, чтобы они не пропадали
# из traffic.json и админка могла показать их последний last_seen.
for user in "${!TOTAL_UP[@]}"; do
    if [[ -z "${NEW_TOTAL_UP[$user]:-}" ]]; then
        NEW_TOTAL_UP["$user"]="${TOTAL_UP[$user]:-0}"
        NEW_TOTAL_DOWN["$user"]="${TOTAL_DOWN[$user]:-0}"
    fi
done

for user in "${!TOTAL_DOWN[@]}"; do
    if [[ -z "${NEW_TOTAL_DOWN[$user]:-}" ]]; then
        NEW_TOTAL_UP["$user"]="${TOTAL_UP[$user]:-0}"
        NEW_TOTAL_DOWN["$user"]="${TOTAL_DOWN[$user]:-0}"
    fi
done

# === 8. СОХРАНЯЕМ СОСТОЯНИЯ NFT ===
TEMP_NFT_STATE="${NFT_STATE_FILE}.tmp"
> "$TEMP_NFT_STATE"

declare -A STATE_USERS
for user in "${!CURRENT_USERS[@]}"; do
    STATE_USERS["$user"]=1
done

for user in "${!PREV_NFT_UP[@]}"; do
    STATE_USERS["$user"]=1
done

for user in "${!PREV_NFT_DOWN[@]}"; do
    STATE_USERS["$user"]=1
done

for user in "${!STATE_USERS[@]}"; do
    echo "$user:${CURRENT_NFT_UP[$user]:-${PREV_NFT_UP[$user]:-0}}:${CURRENT_NFT_DOWN[$user]:-${PREV_NFT_DOWN[$user]:-0}}" >> "$TEMP_NFT_STATE"
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
TEMP_LAST="/opt/vlesstgctl/stats/user_last_active.tmp"
> "$TEMP_LAST"

if [[ -f "$LAST_ACTIVE_FILE" ]]; then
    # ИСПРАВЛЕНО: убираем вложенный flock, используем простой подход
    while IFS=':' read -r user ts; do
        if [[ -n "${HAD_ACTIVITY[$user]:-}" ]]; then
            echo "$user:$CURRENT_TS" >> "$TEMP_LAST"
        else
            echo "$user:$ts" >> "$TEMP_LAST"
        fi
    done < "$LAST_ACTIVE_FILE"
fi

for user in "${!NEW_TOTAL_UP[@]}"; do
    if ! grep -q "^$user:" "$TEMP_LAST" 2>/dev/null; then
        if [[ -n "${HAD_ACTIVITY[$user]:-}" ]]; then
            echo "$user:$CURRENT_TS" >> "$TEMP_LAST"
        fi
    fi
done

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
        # Экранируем спецсимволы
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
