{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  name = "iot-governance-env";

  buildInputs = with pkgs; [
    networkmanager # Provides 'nmcli' to create the laptop Wi-Fi hotspot
    iptables       # Firewall for network isolation and routing 
    nftables       # Modern alternative to iptables, included for flexibility 
    iproute2       # Core network utilities (ip link, ip route)
    hostapd
    dnsmasq
    lsof
    killall
    
    # --- Core Governance Services ---
    coredns        # DNS Server / Context-Aware Sinkhole 
    sqlite         # Database for storing device profiles and logs 

    # --- Backend Development Languages  ---
    python3
    python3Packages.requests # For API interactions
    python3Packages.scapy    # Essential for network scanning, MAC detection, and traffic anomaly detection
     
    # --- Testing & Debugging Tools ---
    curl           # To simulate HTTP traffic
    bind           # Provides 'dig' to test DNS resolution and sinkhole blocks
    tshark         # Wireshark CLI for deep packet inspection (Behavioral Monitoring)
  ];
}