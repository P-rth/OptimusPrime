import subprocess
import logging
import sys

class NetworkManager:
    def __init__(self, config):
        self.config = config
        # Stores iptables rule specs (table, chain, args...) so we can remove exactly what we added.
        self.dns_rules = []

    def run_cmd(self, cmd, check=True):
        logging.debug(f"Running: {' '.join(cmd)}")
        # Execute the command and capture output so we can always show it for debugging.
        res = subprocess.run(cmd, capture_output=True, text=True)

        if res.stdout:
            print(res.stdout, end="")
            logging.debug("STDOUT: %s", res.stdout.strip())

        if res.stderr:
                logging.debug("STDERR: %s", res.stderr.strip())
                print(res.stderr, end="", file=sys.stderr)

        logging.debug("Return code: %s", res.returncode)

        if res.returncode == 1:
            raise subprocess.CalledProcessError(res.returncode, cmd, output=res.stdout, stderr=res.stderr)

        return res

    def setup_interface(self):
        print(f"[*] Resetting {self.config.WIFI_IFACE} and assigning IP ({self.config.GATEWAY_IP})...")
        
        # Neutralize NetworkManager
        self.run_cmd(["sudo", "nmcli", "device", "set", self.config.WIFI_IFACE, "managed", "no"])
        self.run_cmd(["sudo", "pkill", "-x", "wpa_supplicant"])

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
            # Check if exists first to avoid duplicates (suppress stderr from iptables -C)
            check_cmd = ["sudo", "iptables", "-t", table, "-C", chain] + args
            if self.run_cmd(check_cmd).returncode != 0:
                self.run_cmd(["sudo", "iptables", "-t", table, "-A", chain] + args)

        # --- God Mode DNS Redirection (DNS Hijack) ---
        # Redirect *all* client DNS queries (even to hardcoded resolvers like 8.8.8.8)
        # entering on the Wi-Fi interface to our local CoreDNS at GATEWAY_IP:53.
        # The -i WIFI_IFACE match prevents looping the Pi's own DNS traffic.
        self.dns_rules = [
            (
                "nat",
                "PREROUTING",
                [
                    "-i",
                    self.config.WIFI_IFACE,
                    "-p",
                    "udp",
                    "--dport",
                    "53",
                    "-j",
                    "DNAT",
                    "--to-destination",
                    f"{self.config.GATEWAY_IP}:53",
                ],
            ),
            (
                "nat",
                "PREROUTING",
                [
                    "-i",
                    self.config.WIFI_IFACE,
                    "-p",
                    "tcp",
                    "--dport",
                    "53",
                    "-j",
                    "DNAT",
                    "--to-destination",
                    f"{self.config.GATEWAY_IP}:53",
                ],
            ),
        ]

        for table, chain, args in self.dns_rules:
            check_cmd = ["sudo", "iptables", "-t", table, "-C", chain] + args
            # suppress stderr from iptables -C when checking existence
            res = self.run_cmd(check_cmd, suppress_stderr=True)
            if res.returncode == 0:
                logging.info("DNS Hijack rule already exists")
                continue

            add_cmd = ["sudo", "iptables", "-t", table, "-A", chain] + args
            add_res = self.run_cmd(add_cmd)
            if add_res.returncode == 0:
                logging.info("DNS Hijack Active")
            else:
                logging.warning(
                    "Failed to add DNS hijack rule (rc=%s): %s",
                    add_res.returncode,
                    " ".join(add_cmd),
                )

    def restore_interface(self):
        # Remove DNS hijack rules we added (best-effort)
        for table, chain, args in getattr(self, "dns_rules", []) or []:
            del_cmd = ["sudo", "iptables", "-t", table, "-D", chain] + args
            del_res = self.run_cmd(del_cmd)
            if del_res.returncode == 0:
                logging.info("DNS Hijack rule removed")
            else:
                logging.debug(
                    "DNS Hijack rule not present or failed to remove (rc=%s): %s",
                    del_res.returncode,
                    " ".join(del_cmd),
                )

        print(f"[*] Restoring NetworkManager control over {self.config.WIFI_IFACE}...")
        self.run_cmd(["sudo", "nmcli", "device", "set", self.config.WIFI_IFACE, "managed", "yes"])
        self.run_cmd(["sudo", "ip", "link", "set", self.config.WIFI_IFACE, "down"])
        try:
            self.run_cmd(["sudo", "iw", "dev", self.config.WIFI_IFACE, "set", "type", "managed"])
        except:
            pass
        self.run_cmd(["sudo", "ip", "link", "set", self.config.WIFI_IFACE, "up"])
