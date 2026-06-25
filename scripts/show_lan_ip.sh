#!/usr/bin/env bash
set -euo pipefail

echo "Likely LAN IP addresses:"
if command -v ipconfig >/dev/null 2>&1; then
  for iface in en0 en1 en2; do
    ipconfig getifaddr "$iface" 2>/dev/null || true
  done | awk 'NF && !seen[$0]++ { print "  " $0 }'
elif command -v ip >/dev/null 2>&1; then
  ip -4 addr show scope global | awk '/inet / {print "  " $2}' | cut -d/ -f1
elif command -v ifconfig >/dev/null 2>&1; then
  ifconfig | awk '/inet / && $2 !~ /^127\\./ { print "  " $2 }'
else
  echo "  Could not detect automatically. Check your Wi-Fi network settings."
fi

echo
echo "Use this in frontend/.env.android.local:"
echo "VITE_API_BASE_URL=http://<LAPTOP_LAN_IP>:8000"
echo "VITE_ALLOW_LOCAL_HTTP=true"
