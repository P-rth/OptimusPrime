import subprocess
import logging
import sys

from .network_utils import iptables_add_rule_if_missing

class NetworkManager:
    def __init__(self, config):
        self.config = config

    def run_cmd(self, cmd, skip_err = False):
        logging.debug(f"Running: {' '.join(cmd)}")
        # Execute the command and capture output so we can always show it for debugging.
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if res.stdout:
            print(res.stdout, end="")
            logging.debug("STDOUT: %s", res.stdout.strip())

        if res.stderr:
            logging.debug("STDERR: %s", res.stderr.strip())
            print(res.stderr, end="", file=sys.stderr)

        logging.debug("Return code: %s", res.returncode)

        if res.returncode == 1 and not skip_err:
            raise subprocess.CalledProcessError(res.returncode, cmd, output=res.stdout, stderr=res.stderr)

        return res

    def setup_interface(self):
        print(f"[*] Resetting {self.config.WIFI_IFACE} and assigning IP ({self.config.GATEWAY_IP})...")
        
        # Neutralize NetworkManager
        self.run_cmd(["sudo", "nmcli", "device", "set", self.config.WIFI_IFACE, "managed", "no"])
        self.run_cmd(["sudo", "pkill", "-x", "wpa_supplicant"], skip_err=True)  # Ignore if not running

        # Reset Interface
        self.run_cmd(["sudo", "rfkill", "unblock", "wlan"])
        self.run_cmd(["sudo", "ip", "link", "set", self.config.WIFI_IFACE, "down"])
        self.run_cmd(["sudo", "ip", "addr", "flush", "dev", self.config.WIFI_IFACE])
        
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
            ["filter", "FORWARD", "-i", self.config.TETHER_IFACE, "-o", self.config.WIFI_IFACE, "-m", "state", "--state", "RELATED,ESTABLISHED", "-j", "ACCEPT"],
        ]

        for table, chain, *args in rules:
            iptables_add_rule_if_missing(self.run_cmd, table, chain, list(args))

    def restore_interface(self):
        print(f"[*] Restoring NetworkManager control over {self.config.WIFI_IFACE}...")
        self.run_cmd(["sudo", "nmcli", "device", "set", self.config.WIFI_IFACE, "managed", "yes"])
        self.run_cmd(["sudo", "ip", "link", "set", self.config.WIFI_IFACE, "down"])
        try:
            self.run_cmd(["sudo", "iw", "dev", self.config.WIFI_IFACE, "set", "type", "managed"])
        except:
            pass
        self.run_cmd(["sudo", "ip", "link", "set", self.config.WIFI_IFACE, "up"])
