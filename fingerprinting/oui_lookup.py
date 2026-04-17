import json
import logging
import os
import time

import requests


class OUIMapper:
    """Resolves MAC addresses to vendor strings using a live API with local fallback."""

    API_BASE = "https://api.macvendors.com"

    def __init__(self, config):
        self.config = config
        self.oui_path = getattr(config, "OUI_JSON", None)
        if not self.oui_path:
            raise ValueError("Config missing OUI_JSON path")

        # In-memory cache for API results
        self.api_cache: dict[str, str] = {}

        # Local OUI map fallback (keys are AA:BB:CC)
        self._map: dict[str, str] = {}
        self._load()

    def _normalize_mac(self, mac: str) -> str:
        # normalize common MAC formats to lower xx:xx:xx:xx:xx:xx
        return (mac or "").strip().lower().replace("-", ":").replace(".", "")

    def _mac_pretty(self, mac: str) -> str:
        """Normalize to XX:XX:XX:XX:XX:XX for outbound API call / cache key."""
        raw = (mac or "").strip().lower().replace("-", "").replace(":", "").replace(".", "")
        if len(raw) != 12 or any(c not in "0123456789abcdef" for c in raw):
            # best-effort: return original trimmed value
            return (mac or "").strip()
        pairs = [raw[i : i + 2] for i in range(0, 12, 2)]
        return ":".join(pairs).upper()

    def _mac_to_oui(self, mac: str) -> str:
        pretty = self._mac_pretty(mac)
        parts = pretty.split(":")
        if len(parts) < 3:
            return ""
        return ":".join(parts[:3]).upper()

    def _load(self):
        if not os.path.exists(self.oui_path):
            logging.warning("OUI map not found at %s; local fallback will be empty", self.oui_path)
            self._map = {}
            return

        try:
            with open(self.oui_path, "r", encoding="utf-8") as fp:
                data = json.load(fp) or {}
        except Exception as exc:
            logging.exception("Failed loading OUI JSON %s: %s", self.oui_path, exc)
            data = {}

        normalized: dict[str, str] = {}
        for k, v in data.items():
            key = (k or "").strip().replace("-", ":").upper()
            if not key:
                continue
            normalized[key] = (v or "Unknown").strip() or "Unknown"

        self._map = normalized
        logging.debug("Loaded %d OUIs from %s", len(self._map), self.oui_path)

    def _fetch_from_api(self, mac: str) -> str | None:
        """Fetch vendor from api.macvendors.com.

        Returns vendor string on success, None on failure / not found.
        """
        mac_str = self._mac_pretty(mac)
        if not mac_str:
            return None

        url = f"{self.API_BASE}/{requests.utils.quote(mac_str, safe='') }"
        try:
            resp = requests.get(url, timeout=2)
            # Respect rate limits only after an actual API call.
            time.sleep(1)

            if resp.status_code == 200:
                vendor = (resp.text or "").strip()
                return vendor or None

            if resp.status_code == 404:
                return None

            logging.debug("MAC vendor API non-200 response: %s %s", resp.status_code, resp.text)
            return None
        except requests.RequestException as exc:
            # Respect rate limits only after an actual API call.
            time.sleep(1)
            logging.debug("MAC vendor API request failed: %s", exc)
            return None

    def resolve(self, mac: str) -> str:
        """Resolve MAC to vendor with cache -> API -> local OUI fallback."""
        pretty = self._mac_pretty(mac)
        if not pretty:
            return "Unknown"

        # Cache hit (no sleep)
        cached = self.api_cache.get(pretty)
        if cached is not None:
            return cached

        # Live lookup
        vendor = self._fetch_from_api(pretty)
        if vendor:
            self.api_cache[pretty] = vendor
            return vendor

        # Fallback: local OUI mapping
        oui = self._mac_to_oui(pretty)
        local_vendor = self._map.get(oui, "Unknown") if oui else "Unknown"
        # cache fallback too to avoid hammering API on unknowns
        self.api_cache[pretty] = local_vendor
        return local_vendor
