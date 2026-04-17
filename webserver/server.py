from http.server import HTTPServer, BaseHTTPRequestHandler
import os

# Get the directory where server.py lives
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class Serv(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.path = '/index.html'

        # Resolve path relative to the script's own directory
        file_path = os.path.join(BASE_DIR, self.path.lstrip('/'))

        try:
            with open(file_path) as f:
                file_to_open = f.read()
            self.send_response(200)
            self.send_header('Content-type', 'text/html')

        except FileNotFoundError:
            file_to_open = "<h1>404 File not found</h1>"
            self.send_response(404)
            self.send_header('Content-type', 'text/html')

        except Exception as e:
            print(f"Error handling request: {e}")
            file_to_open = "<h1>500 Server error</h1>"
            self.send_response(500)
            self.send_header('Content-type', 'text/html')

        self.end_headers()
        self.wfile.write(bytes(file_to_open, 'utf-8'))

    def log_message(self, format, *args):
        print(format % args)

httpd = HTTPServer(('0.0.0.0', 8080), Serv)
print("Server running on http://localhost:8080")
httpd.serve_forever()