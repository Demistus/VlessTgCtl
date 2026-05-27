# VlessTgCtl
curl -sSL https://raw.githubusercontent.com/Demistus/VlessTgCtl/main/install.sh | bash

Есть баг: в /etc/sing-box/config.json в 
"endpoints": [
    {
      "type": "wireguard",
в  "private_key" и  "public_key" в конце потерялся знак =

надо просто добавить и заработает
