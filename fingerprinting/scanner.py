import os
import time
import logging

from .oui_lookup import OUIMapper
from .classifier import DeviceClassifier
from .registry import DeviceRegistry


class DeviceScanner:
    """Orchestrates lease monitoring + identity mapping + persistence."""

    DEFAULT_LEASES_PATH = "/var/lib/misc/dnsmasq.leases"

    def __init__(self, config, leases_path: str | None = None, poll_interval_sec: int = 5):
        self.config = config
        self.leases_path = leases_path or self.DEFAULT_LEASES_PATH
        self.poll_interval_sec = int(poll_interval_sec)

        self.oui = OUIMapper(config)
        self.classifier = DeviceClassifier()
        self.registry = DeviceRegistry(config)

    def _normalize_mac(self, mac: str) -> str:
        return (mac or "").strip().lower().replace("-", ":")

    def _parse_leases(self, content: str):
        devices = []
        for raw in (content or "").splitlines():
            line = raw.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 4:
                continue

            mac = self._normalize_mac(parts[1])
            ip = parts[2].strip()
            hostname = parts[3].strip() if parts[3].strip() != "*" else ""
            if not mac:
                continue

            devices.append((mac, ip, hostname))
        return devices

    def update_registry(self):
        """Poll the dnsmasq leases file every 5 seconds and update the persistent registry.

        This is a blocking loop suitable for running in a background thread.
        """
        logging.info("DeviceScanner watching leases file: %s", self.leases_path)
        logging.info("Identity registry: %s", getattr(self.config, "DEVICES_JSON", "<unset>"))
        logging.info("OUI map: %s", getattr(self.config, "OUI_JSON", "<unset>"))

        while True:
            try:
                if not os.path.exists(self.leases_path):
                    logging.debug("Leases file does not exist yet: %s", self.leases_path)
                    time.sleep(self.poll_interval_sec)
                    continue

                with open(self.leases_path, "r", encoding="utf-8", errors="replace") as fp:
                    content = fp.read()

                for mac, ip, hostname in self._parse_leases(content):
                    was_known = self.registry.has(mac)

                    vendor = self.oui.resolve(mac)
                    classification = self.classifier.classify(vendor, hostname)
                    dev_type = classification["type"]
                    confidence = classification["confidence"]

                    # Persist immediately (and preserve first_seen if already known).
                    self.registry.upsert(
                        mac=mac,
                        ip=ip,
                        hostname=hostname,
                        vendor=vendor,
                        dev_type=dev_type,
                        confidence=confidence,
                    )

                    # Only alert if it did not already exist in persisted registry.
                    if not was_known:
                        print(f"[!] NEW DEVICE IDENTIFIED: {vendor} {dev_type} ({ip})")
                        logging.info("New device: mac=%s vendor=%s type=%s ip=%s", mac, vendor, dev_type, ip)

            except Exception as exc:
                logging.exception("DeviceScanner error: %s", exc)

            time.sleep(self.poll_interval_sec)

    def get_active_devices(self):
        return self.registry.get_all()
