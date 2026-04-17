import http.server
import socketserver
import json
import os

PORT = 8081
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "..", "logs", "coredns.log")

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

        return super().do_GET()

    def log_message(self, format, *args):
        print(format % args)

os.chdir(BASE_DIR)

with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"Serving at http://127.0.0.1:{PORT}")
    httpd.serve_forever()