#!/usr/bin/env bash

# === Configuration (RPi5 + network dongle) ===
WIFI_IFACE="wlan0"
TETHER_IFACE="eth0"
GATEWAY_IP="192.168.0.1"
SUBNET_MASK="24"
HOSTAPD_CONF="hostapd-rpi5.conf"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COREDNS_BIN="$SCRIPT_DIR/coredns"

add_iptables_rule_if_missing() {
  local table="$1"
  shift

  if [ "$table" = "nat" ]; then
    if ! sudo iptables -t nat -C "$@" 2>/dev/null; then
      sudo iptables -t nat -A "$@"
    fi
  else
    if ! sudo iptables -C "$@" 2>/dev/null; then
      sudo iptables -A "$@"
    fi
  fi
}

abort_startup() {
  local reason="$1"
  echo "❌ Startup failed: $reason"

  [ -n "$AP_PID" ] && sudo kill "$AP_PID" 2>/dev/null || true
  [ -n "$DNS_PID" ] && sudo kill "$DNS_PID" 2>/dev/null || true
  [ -n "$PY_PID" ] && sudo kill "$PY_PID" 2>/dev/null || true
  [ -n "$DHCP_PID" ] && sudo kill "$DHCP_PID" 2>/dev/null || true
  sudo pkill -f "$COREDNS_BIN" 2>/dev/null || true
  sudo pkill -x hostapd 2>/dev/null || true
  sudo pkill -x dnsmasq 2>/dev/null || true

  sudo nmcli device set "$WIFI_IFACE" managed yes 2>/dev/null || true
  exit 1
}

if [ ! -x "$COREDNS_BIN" ]; then
  echo "❌ Local CoreDNS binary not found or not executable: $COREDNS_BIN"
  echo "   Put the coredns binary in this folder and run: chmod +x ./coredns"
  exit 1
fi

echo "=========================================="
echo " 🛡️ Starting Smart Device Governance Layer"
echo "=========================================="

# 1. Neutralize Interferences
echo "[*] Disabling NetworkManager on $WIFI_IFACE..."

if ! nmcli -t -f DEVICE device status 2>/dev/null | grep -q "^${WIFI_IFACE}$"; then
  abort_startup "Wi-Fi interface ${WIFI_IFACE} not found."
fi

if command -v iw >/dev/null 2>&1; then
  if ! iw list 2>/dev/null | grep -q '^\s*\* AP$'; then
    abort_startup "Wireless driver/firmware does not report AP mode support (iw list)."
  fi
fi

ACTIVE_CONN=$(nmcli -t -f GENERAL.CONNECTION device show "$WIFI_IFACE" 2>/dev/null | cut -d: -f2)
if [ -n "$ACTIVE_CONN" ] && [ "$ACTIVE_CONN" != "--" ]; then
  sudo nmcli connection down "$ACTIVE_CONN" 2>/dev/null || true
fi

sudo nmcli device disconnect "$WIFI_IFACE" 2>/dev/null || true
sleep 1
STATE_AFTER_DISCONNECT=$(nmcli -t -f GENERAL.STATE device show "$WIFI_IFACE" 2>/dev/null | cut -d: -f2)
if echo "$STATE_AFTER_DISCONNECT" | grep -qi '^100'; then
  abort_startup "${WIFI_IFACE} is still connected as a client. Disconnect Wi-Fi before AP mode."
fi

sudo $(which nmcli) device set $WIFI_IFACE managed no
sudo killall wpa_supplicant 2>/dev/null

# Stop/kill conflicting services and old processes from previous runs
sudo systemctl stop hostapd 2>/dev/null || true
sudo systemctl stop dnsmasq 2>/dev/null || true
if systemctl list-unit-files | grep -q '^systemd-resolved\.service'; then
  sudo systemctl stop systemd-resolved 2>/dev/null || true
fi

sudo pkill -f "$COREDNS_BIN" 2>/dev/null || true
sudo pkill -f "python3 ./test/server.py" 2>/dev/null || true
sudo pkill -x hostapd 2>/dev/null || true
sudo pkill -x dnsmasq 2>/dev/null || true

# 2. Reset Network Interface
echo "[*] Resetting $WIFI_IFACE and assigning IP ($GATEWAY_IP)..."
sudo rfkill unblock wlan
sudo $(which ip) link set $WIFI_IFACE down
sudo $(which ip) addr flush dev $WIFI_IFACE
if command -v iw >/dev/null 2>&1; then
  sudo iw dev "$WIFI_IFACE" set type __ap || true
fi
sudo $(which ip) link set $WIFI_IFACE up
sudo $(which ip) addr add $GATEWAY_IP/$SUBNET_MASK dev $WIFI_IFACE

# 3. Start Background Services
echo "[*] Launching Governance Services..."

sudo python3 ./test/server.py 2>&1 &
PY_PID=$!
echo "  -> Sinkhole Server started (PID: $PY_PID) on Port 80"

# Start CoreDNS
sudo "$COREDNS_BIN" -conf "$SCRIPT_DIR/Corefile" > coredns.log 2>&1 &
DNS_PID=$!
echo "  -> CoreDNS Engine started (PID: $DNS_PID) on Port 53"
sleep 1
if ! sudo kill -0 "$DNS_PID" 2>/dev/null; then
  tail -n 20 coredns.log 2>/dev/null || true
  abort_startup "CoreDNS did not stay running (port 53 may be in use)."
fi

# Start HostAPD
sudo $(which hostapd) "$HOSTAPD_CONF" > hostapd.log 2>&1 &
AP_PID=$!
echo "  -> Access Point (hostapd) started (PID: $AP_PID)"
sleep 2
if ! sudo kill -0 "$AP_PID" 2>/dev/null; then
  tail -n 30 hostapd.log 2>/dev/null || true
  if command -v iw >/dev/null 2>&1; then
    echo "[*] AP capability check (iw list):"
    iw list 2>/dev/null | sed -n '/Supported interface modes/,+12p' || true
  fi
  abort_startup "hostapd failed. wlan0 likely does not support AP mode with current driver/firmware."
fi

# Start DHCP Server (dnsmasq - DNS disabled, CoreDNS handles DNS)
sudo dnsmasq \
  --interface=$WIFI_IFACE \
  --no-resolv \
  --no-hosts \
  --port=0 \
  --dhcp-range=192.168.0.2,192.168.0.254,24h \
  --dhcp-option=option:router,192.168.0.1 \
  --dhcp-option=option:dns-server,192.168.0.1 \
  > dnsmasq.log 2>&1 &
DHCP_PID=$!
echo "  -> DHCP Server started (PID: $DHCP_PID)"

# Enable IP forwarding
sudo sysctl -w net.ipv4.ip_forward=1

# Enable NAT/masquerade to route WiFi traffic through Ethernet uplink
add_iptables_rule_if_missing nat POSTROUTING -o "$TETHER_IFACE" -j MASQUERADE
add_iptables_rule_if_missing filter FORWARD -i "$WIFI_IFACE" -o "$TETHER_IFACE" -j ACCEPT
add_iptables_rule_if_missing filter FORWARD -i "$TETHER_IFACE" -o "$WIFI_IFACE" -m state --state RELATED,ESTABLISHED -j ACCEPT

echo "=========================================="
echo " ✅ SYSTEM ACTIVE: AP is broadcasting."
echo " Logs: coredns.log | hostapd.log"
echo " Press [CTRL+C] to shut down safely."
echo "=========================================="

# 4. Graceful Teardown (Trap)
cleanup() {
    echo ""
    echo "🛑 Shutting down Governance Layer..."

    # Kill background jobs
    sudo kill $AP_PID 2>/dev/null
    sudo kill $DNS_PID 2>/dev/null
    sudo kill $PY_PID 2>/dev/null
    sudo kill $DHCP_PID 2>/dev/null

    sudo killall dnsmasq
    sudo pkill -f "$COREDNS_BIN" 2>/dev/null || true

    # Hand control back to NetworkManager
    echo "[*] Restoring NetworkManager control over $WIFI_IFACE..."
    sudo $(which nmcli) device set $WIFI_IFACE managed yes
    sudo $(which ip) link set $WIFI_IFACE down 2>/dev/null || true
    if command -v iw >/dev/null 2>&1; then
      sudo iw dev "$WIFI_IFACE" set type managed 2>/dev/null || true
    fi
    sudo $(which ip) link set $WIFI_IFACE up 2>/dev/null || true

    echo "✅ Shutdown complete."
    exit 0
}

trap cleanup SIGINT SIGTERM

# Wait indefinitely so the script doesn't exit, keeping the background jobs alive
wait
