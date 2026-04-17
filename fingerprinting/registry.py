import json
import logging
import os
from datetime import datetime, timezone


class DeviceRegistry:
    """Persists device identity state in a JSON file keyed by MAC."""

    def __init__(self, config):
        self.config = config
        self.path = getattr(config, "DEVICES_JSON", None)
        if not self.path:
            raise ValueError("Config missing DEVICES_JSON path")

        # { mac: {ip, hostname, vendor, type, confidence, first_seen} }
        self.devices: dict[str, dict] = {}
        self.load()

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _normalize_mac(self, mac: str) -> str:
        return (mac or "").strip().lower().replace("-", ":")

    def load(self):
        if not os.path.exists(self.path):
            self.devices = {}
            return
        try:
            with open(self.path, "r", encoding="utf-8") as fp:
                data = json.load(fp) or {}
            # normalize keys
            self.devices = {self._normalize_mac(k): (v or {}) for k, v in data.items()}
        except Exception as exc:
            logging.exception("Failed to load devices registry %s: %s", self.path, exc)
            self.devices = {}

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp_path = self.path + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as fp:
                json.dump(self.devices, fp, indent=2, sort_keys=True)
            os.replace(tmp_path, self.path)
        except Exception as exc:
            logging.exception("Failed to save devices registry %s: %s", self.path, exc)
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass

    def has(self, mac: str) -> bool:
        return self._normalize_mac(mac) in self.devices

    def upsert(self, mac: str, ip: str, hostname: str, vendor: str, dev_type: str, confidence: int):
        mac_n = self._normalize_mac(mac)
        if not mac_n:
            return

        if mac_n not in self.devices:
            self.devices[mac_n] = {
                "first_seen": self._now_iso(),
            }

        entry = self.devices[mac_n]
        entry["ip"] = ip
        entry["hostname"] = hostname
        entry["vendor"] = vendor
        entry["type"] = dev_type
        entry["confidence"] = int(confidence)

        # Persist immediately on identification/update.
        self.save()

    def get_all(self):
        return self.devices
