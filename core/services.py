import subprocess
import time
import os
import signal

class ServiceManager:
    def __init__(self, config):
        self.config = config
        self.processes = []

    def start_service(self, cmd, name):
        print(f"  -> Starting {name}...")
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.processes.append((proc, name))
        return proc

    def start_all(self):
        # Stop existing
        subprocess.run(["sudo", "pkill", "-f", self.config.COREDNS_BIN], stderr=subprocess.DEVNULL)
        subprocess.run(["sudo", "pkill", "-x", "hostapd"], stderr=subprocess.DEVNULL)
        subprocess.run(["sudo", "pkill", "-x", "dnsmasq"], stderr=subprocess.DEVNULL)
        subprocess.run(["sudo", "pkill", "-f", self.config.WEB_SERVER_SCRIPT], stderr=subprocess.DEVNULL)

        # 1. Sinkhole Web Server
        self.start_service(["sudo", "python3", self.config.WEB_SERVER_SCRIPT], "Sinkhole Server")

        # 2. CoreDNS
        self.start_service(["sudo", self.config.COREDNS_BIN, "-conf", self.config.COREFILE], "CoreDNS")

        # 3. HostAPD
        self.start_service(["sudo", "hostapd", self.config.HOSTAPD_CONF], "HostAPD")

        # 4. DHCP (dnsmasq)
        dhcp_cmd = [
            "sudo", "dnsmasq",
            f"--interface={self.config.WIFI_IFACE}",
            "--no-resolv",
            "--no-hosts",
            "--port=0",
            "--dhcp-range=192.168.0.2,192.168.0.254,24h",
            f"--dhcp-option=option:router,{self.config.GATEWAY_IP}",
            f"--dhcp-option=option:dns-server,{self.config.GATEWAY_IP}"
        ]
        self.start_service(dhcp_cmd, "DHCP Server")

    def stop_all(self):
        print("\n[*] Stopping Governance Services...")
        for proc, name in self.processes:
            try:
                # Use sudo pkill for services started with sudo
                if "CoreDNS" in name:
                    subprocess.run(["sudo", "pkill", "-f", self.config.COREDNS_BIN], stderr=subprocess.DEVNULL)
                elif "HostAPD" in name:
                    subprocess.run(["sudo", "pkill", "-x", "hostapd"], stderr=subprocess.DEVNULL)
                elif "DHCP" in name:
                    subprocess.run(["sudo", "pkill", "-x", "dnsmasq"], stderr=subprocess.DEVNULL)
                elif "Sinkhole" in name:
                    subprocess.run(["sudo", "pkill", "-f", self.config.WEB_SERVER_SCRIPT], stderr=subprocess.DEVNULL)
                
                proc.terminate()
            except:
                pass
