import csv
import os

class Config:
    SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    MAIN_CONF = os.path.join(SCRIPT_DIR, "files", "main.conf")

    def _load_main_conf(MAIN_CONF):
        config = {}
        try:
            with open(MAIN_CONF, "r", encoding="utf-8") as f:
                for row in csv.reader(f, delimiter="=", quotechar='"'):
                    if not row or len(row) < 2:
                        continue
                    key = row[0].strip()
                    value = row[1].strip()
                    if not key or key.startswith("#"):
                        continue
                    config[key] = value
        except FileNotFoundError:
            pass
        return config

    _MAIN_CONF = _load_main_conf(MAIN_CONF)

    WIFI_IFACE = _MAIN_CONF.get("WIFI_IFACE", "wlan0")
    TETHER_IFACE = _MAIN_CONF.get("TETHER_IFACE", "usb0")
    GATEWAY_IP = _MAIN_CONF.get("GATEWAY_IP", "192.168.0.1")
    SUBNET_MASK = _MAIN_CONF.get("SUBNET_MASK", "24")

    COREDNS_BIN = os.path.join(SCRIPT_DIR, "bin", "coredns")
    COREFILE = os.path.join(SCRIPT_DIR, "files", "Corefile")
    HOSTAPD_CONF = os.path.join(SCRIPT_DIR, "files", "hostapd.conf")
    WEB_SERVER_SCRIPT = os.path.join(SCRIPT_DIR, "webserver", "server.py")

    # Fingerprinting / Identity Engine data paths
    DATA_DIR = os.path.join(SCRIPT_DIR, "data")
    OUI_JSON = os.path.join(DATA_DIR, "oui.json")
    DEVICES_JSON = os.path.join(DATA_DIR, "devices.json")

    os.makedirs(DATA_DIR, exist_ok=True)
