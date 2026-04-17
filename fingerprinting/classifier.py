import logging


class DeviceClassifier:
    """Classifies devices based on vendor + hostname with a confidence score."""

    def classify(self, vendor: str, hostname: str):
        vendor = (vendor or "").strip()
        hostname_raw = (hostname or "").strip()
        hostname_l = hostname_raw.lower()

        # Workstations
        if vendor in {"Intel", "Apple"}:
            host_match = ("macbook" in hostname_l) or ("laptop" in hostname_l)
            if host_match:
                return {"type": "Workstation", "confidence": 100}
            return {"type": "Workstation", "confidence": 50}

        # IoT device families
        if vendor in {"Tuya", "Espressif"}:
            # Optional hostname hints improve confidence.
            host_match = any(tok in hostname_l for tok in ["tuya", "smart", "plug", "light", "esp", "espressif"])
            return {"type": "IoT Device", "confidence": 100 if host_match else 50}

        # Mobile hints (examples)
        if vendor == "Samsung":
            host_match = any(tok in hostname_l for tok in ["android", "galaxy", "samsung"])
            return {"type": "Unknown/Mobile", "confidence": 100 if host_match else 50}

        logging.debug("No strong classification match for vendor=%s hostname=%s", vendor, hostname_raw)
        return {"type": "Unknown/Mobile", "confidence": 0}
