import http.server
import socketserver
import json
import os
import datetime

PORT = 8081
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "..", "logs", "coredns.log")
BLOCKLIST_FILE = os.path.join(BASE_DIR, "..", "files", "blocklist.txt")
DEVICES_FILE = os.path.join(BASE_DIR, "..", "logs", "fingerprinting.csv")

class Handler(http.server.SimpleHTTPRequestHandler):

    def do_GET(self):
        if self.path == "/logs":
            try:
                with open(LOG_FILE, "r") as f:
                    lines = f.readlines()
                last_50 = [line.strip() for line in lines[-50:] if line.strip()]
            except FileNotFoundError:
                last_50 = ["[SYSTEM] coredns.log not found."]

            body = json.dumps(last_50).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path == "/blocklist":
            try:
                items = []
                now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                with open(BLOCKLIST_FILE, "r") as f:
                    for raw in f:
                        line = raw.strip()
                        if not line:
                            continue
                        parts = line.split(maxsplit=1)
                        if len(parts) < 2:
                            continue
                        ip_addr, domain = parts[0], parts[1]
                        items.append(
                            {
                                "timestamp": now_str,
                                "hostname": "Parth's Device",
                                "targetDomain": domain,
                                "reason": "Matched DNS blocklist policy",
                                "ipAddress": ip_addr,
                            }
                        )
            except FileNotFoundError:
                items = [
                    {
                        "hostname": "Error",
                        "targetDomain": "blocklist.txt not found",
                        "reason": "",
                        "timestamp": "",
                        "ipAddress": "",
                    }
                ]

            body = json.dumps(items).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path == "/devices":
            try:
                import csv
                with open(DEVICES_FILE, "r") as f:
                    reader = csv.DictReader(f)
                    devices = []
                    for row in reader:
                        devices.append({
                            "status": "Safe",
                            "hostname": row["hostname"],
                            "macAddress": row["mac"],
                            "ipAddress": row["ip"]
                        })
            except FileNotFoundError:
                devices = [{"status": "Error", "hostname": "fingerprinting.csv not found", "macAddress": "", "ipAddress": ""}]

            body = json.dumps(devices).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
            return

        return super().do_GET()

    def log_message(self, format, *args):
        print(format % args)

os.chdir(BASE_DIR)

with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"Serving at http://127.0.0.1:{PORT}")
    httpd.serve_forever()