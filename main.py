#!/usr/bin/env python3
import sys
import signal
import time
from core import Config, NetworkManager, ServiceManager

def main():
    config = Config()
    network = NetworkManager(config)
    services = ServiceManager(config)

    def signal_handler(sig, frame):
        services.stop_all()
        network.restore_interface()
        print("✅ Shutdown complete.")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print("==========================================")
    print(" 🛡️  Smart Device Governance Layer (Python)")
    print("==========================================")

    network.setup_interface()
    network.setup_nat()
    
    print("[*] Launching Governance Services...")
    services.start_all()

    print("==========================================")
    print(" ✅ SYSTEM ACTIVE: AP is broadcasting.")
    print(" Press [CTRL+C] to shut down safely.")
    print("==========================================")
    
    # Keep main thread alive
    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
