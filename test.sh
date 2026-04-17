#!/usr/bin/env bash

# === Configuration ===
WIFI_IFACE="wlp1s0"
TETHER_IFACE="enp3s0f3u2"
GATEWAY_IP="192.168.0.1"
SUBNET_MASK="24"

echo "=========================================="
echo " 🛡️ Starting Smart Device Governance Layer"
echo "=========================================="

# 1. Neutralize Interferences
echo "[*] Disabling NetworkManager on $WIFI_IFACE..."
sudo $(which nmcli) device set $WIFI_IFACE managed no
sudo killall wpa_supplicant 2>/dev/null

# 2. Reset Network Interface
echo "[*] Resetting $WIFI_IFACE and assigning IP ($GATEWAY_IP)..."
sudo rfkill unblock wlan
sudo $(which ip) link set $WIFI_IFACE down
sudo $(which ip) addr flush dev $WIFI_IFACE
sudo $(which ip) link set $WIFI_IFACE up
sudo $(which ip) addr add $GATEWAY_IP/$SUBNET_MASK dev $WIFI_IFACE

sudo systemctl stop systemd-resolved

# 3. Start Background Services
echo "[*] Launching Governance Services..."

sudo python ./test/server.py 2>&1 &
PY_PID=$!
echo "  -> Sinkhole Server started (PID: $PY_PID) on Port 80"


# Start CoreDNS
sudo $(which coredns) -conf Corefile > coredns.log 2>&1 &
DNS_PID=$!
echo "  -> CoreDNS Engine started (PID: $DNS_PID) on Port 53"

# Start HostAPD
sudo $(which hostapd) hostapd.conf > hostapd.log 2>&1 &
AP_PID=$!
echo "  -> Access Point (hostapd) started (PID: $AP_PID)"

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

# Enable NAT/masquerade to route WiFi traffic through USB tether

sudo iptables -t nat -A POSTROUTING -o $TETHER_IFACE -j MASQUERADE
sudo iptables -A FORWARD -i $WIFI_IFACE -o $TETHER_IFACE -j ACCEPT
sudo iptables -A FORWARD -i $TETHER_IFACE -o $WIFI_IFACE -m state --state RELATED,ESTABLISHED -j ACCEPT

echo "=========================================="
echo " ✅ SYSTEM ACTIVE: AP is broadcasting."
echo " Logs: coredns.log | hostapd.log"
echo " Press [CTRL+C] to shut down safely."
echo "=========================================="


# 4. Graceful Teardown (Trap)
# This catches Ctrl+C and kills the background services before exiting
cleanup() {
    echo ""
    echo "🛑 Shutting down Governance Layer..."
    
    # Kill background jobs
    sudo kill $AP_PID 2>/dev/null
    sudo kill $DNS_PID 2>/dev/null
    sudo kill $PY_PID 2>/dev/null

    sudo kill $DHCP_PID 2>/dev/null

    sudo killall dnsmasq 

    # Hand control back to NetworkManager
    echo "[*] Restoring NetworkManager control over $WIFI_IFACE..."
    sudo $(which nmcli) device set $WIFI_IFACE managed yes
    
    echo "✅ Shutdown complete."
    exit 0
}

# Bind the cleanup function to SIGINT (Ctrl+C) and SIGTERM
trap cleanup SIGINT SIGTERM

# Wait indefinitely so the script doesn't exit, keeping the background jobs alive
wait