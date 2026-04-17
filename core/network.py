import subprocess
import logging

class NetworkManager:
    def __init__(self, config):
        self.config = config

    def run_cmd(self, cmd, check=True):
        logging.debug(f"Running: {' '.join(cmd)}")
        return subprocess.run(cmd, capture_output=True, text=True, check=check)

    def setup_interface(self):
        print(f"[*] Resetting {self.config.WIFI_IFACE} and assigning IP ({self.config.GATEWAY_IP})...")
        
        # Neutralize NetworkManager
        self.run_cmd(["sudo", "nmcli", "device", "set", self.config.WIFI_IFACE, "managed", "no"], check=False)
        self.run_cmd(["sudo", "pkill", "-x", "wpa_supplicant"], check=False)

        # Reset Interface
        self.run_cmd(["sudo", "rfkill", "unblock", "wlan"], check=False)
        self.run_cmd(["sudo", "ip", "link", "set", self.config.WIFI_IFACE, "down"], check=False)
        self.run_cmd(["sudo", "ip", "addr", "flush", "dev", self.config.WIFI_IFACE], check=False)
        
        try:
            self.run_cmd(["sudo", "iw", "dev", self.config.WIFI_IFACE, "set", "type", "__ap"])
        except:
            pass

        self.run_cmd(["sudo", "ip", "link", "set", self.config.WIFI_IFACE, "up"])
        self.run_cmd(["sudo", "ip", "addr", "add", f"{self.config.GATEWAY_IP}/{self.config.SUBNET_MASK}", "dev", self.config.WIFI_IFACE])

    def setup_nat(self):
        print(f"[*] Enabling NAT/Masquerade via {self.config.TETHER_IFACE}...")
        self.run_cmd(["sudo", "sysctl", "-w", "net.ipv4.ip_forward=1"])
        
        rules = [
            ["nat", "POSTROUTING", "-o", self.config.TETHER_IFACE, "-j", "MASQUERADE"],
            ["filter", "FORWARD", "-i", self.config.WIFI_IFACE, "-o", self.config.TETHER_IFACE, "-j", "ACCEPT"],
            ["filter", "FORWARD", "-i", self.config.TETHER_IFACE, "-o", self.config.WIFI_IFACE, "-m", "state", "--state", "RELATED,ESTABLISHED", "-j", "ACCEPT"]
        ]
        
        for table, chain, *args in rules:
            # Check if exists first to avoid duplicates
            check_cmd = ["sudo", "iptables", "-t", table, "-C", chain] + args
            if self.run_cmd(check_cmd, check=False).returncode != 0:
                self.run_cmd(["sudo", "iptables", "-t", table, "-A", chain] + args)

    def restore_interface(self):
        print(f"[*] Restoring NetworkManager control over {self.config.WIFI_IFACE}...")
        self.run_cmd(["sudo", "nmcli", "device", "set", self.config.WIFI_IFACE, "managed", "yes"], check=False)
        self.run_cmd(["sudo", "ip", "link", "set", self.config.WIFI_IFACE, "down"], check=False)
        try:
            self.run_cmd(["sudo", "iw", "dev", self.config.WIFI_IFACE, "set", "type", "managed"])
        except:
            pass
        self.run_cmd(["sudo", "ip", "link", "set", self.config.WIFI_IFACE, "up"], check=False)
