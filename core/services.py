import subprocess
import time
import os
import signal
import logging

class ServiceManager:
    def __init__(self, config):
        self.config = config
        self.processes = []
        self.log_dir = os.path.join(self.config.SCRIPT_DIR, "logs")
        os.makedirs(self.log_dir, exist_ok=True)

    def _log_path_for(self, name):
        safe_name = name.lower().replace(" ", "_")
        return os.path.join(self.log_dir, f"{safe_name}.log")

    def _ensure_coredns_listening(self, timeout_sec=4):
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            ss_res = subprocess.run(
                ["sudo", "ss", "-ltnup"],
                capture_output=True,
                text=True,
            )
            ss_out = ss_res.stdout or ""
            if ":53" in ss_out and "coredns" in ss_out.lower():
                return True
            time.sleep(0.4)
        return False

    def start_service(self, cmd, name, cwd=None):
        print(f"  -> Starting {name}...")
        logging.debug("Starting service command: %s", " ".join(cmd))
        log_path = self._log_path_for(name)
        log_fp = open(log_path, "a", encoding="utf-8")
        proc = subprocess.Popen(cmd, cwd=cwd, stdout=log_fp, stderr=subprocess.STDOUT)
        self.processes.append((proc, name, log_path, log_fp))
        time.sleep(0.4)
        if proc.poll() is not None:
            logging.error("%s exited immediately with code %s", name, proc.returncode)
            raise RuntimeError(
                f"{name} failed to start (exit code {proc.returncode}). Check log: {log_path}"
            )
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
        coredns_path = self.config.COREDNS_BIN
        corefile_dir = os.path.dirname(self.config.COREFILE)

        if not os.path.exists(coredns_path):
            raise RuntimeError(f"CoreDNS binary not found: {coredns_path}")

        # Ensure binary is executable (common issue after copying release files).
        if not os.access(coredns_path, os.X_OK):
            try:
                os.chmod(coredns_path, 0o755)
                logging.warning("CoreDNS binary was not executable; applied chmod +x")
            except Exception as exc:
                raise RuntimeError(
                    f"CoreDNS binary is not executable: {coredns_path}. "
                    "Run: chmod +x bin/coredns"
                ) from exc

        self.start_service(
            ["sudo", coredns_path, "-conf", self.config.COREFILE],
            "CoreDNS",
            cwd=corefile_dir,
        )
        if not self._ensure_coredns_listening():
            raise RuntimeError("CoreDNS did not bind to :53. Check logs/coredns.log")

        # 3. HostAPD
        self.start_service(["sudo", "hostapd", self.config.HOSTAPD_CONF], "HostAPD")

        # 4. DHCP (dnsmasq)
        dhcp_cmd = [
            "sudo", "dnsmasq",
            f"--interface={self.config.WIFI_IFACE}",
            "--no-resolv",
            "--no-hosts",
            "--keep-in-foreground",
            "--port=0",
            "--dhcp-range=192.168.0.2,192.168.0.254,24h",
            f"--dhcp-option=option:router,{self.config.GATEWAY_IP}",
            f"--dhcp-option=option:dns-server,{self.config.GATEWAY_IP}"
        ]
        self.start_service(dhcp_cmd, "DHCP Server")

        # Ensure nothing silently died after startup.
        time.sleep(0.6)
        for proc, name, log_path, _ in self.processes:
            if proc.poll() is not None:
                raise RuntimeError(
                    f"{name} stopped unexpectedly (exit code {proc.returncode}). Check log: {log_path}"
                )

    def stop_all(self):
        print("\n[*] Stopping Governance Services...")
        for proc, name, _, log_fp in self.processes:
            try:
                # Use sudo pkill for services started with sudo
                if "CoreDNS" in name:
                    subprocess.run(["sudo", "pkill", "-f", self.config.COREDNS_BIN])
                elif "HostAPD" in name:
                    subprocess.run(["sudo", "pkill", "-x", "hostapd"])
                elif "DHCP" in name:
                    subprocess.run(["sudo", "pkill", "-x", "dnsmasq"])
                elif "Sinkhole" in name:
                    subprocess.run(["sudo", "pkill", "-f", self.config.WEB_SERVER_SCRIPT])
                
                proc.terminate()
            except:
                pass
            finally:
                log_fp.close()
