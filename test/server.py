from http.server import HTTPServer, BaseHTTPRequestHandler
import os

class Serv(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.path = '/test/main.html'
        try:
            with open(self.path[1:]) as f:
                file_to_open = f.read()
            self.send_response(200)
        except FileNotFoundError:
            file_to_open = "File not found"
            self.send_response(404)
        except Exception as e:
            print(f"Error handling request: {e}")
            file_to_open = "Server error"
            self.send_response(500)
        
        self.end_headers()
        self.wfile.write(bytes(file_to_open, 'utf-8'))

    def log_message(self, format, *args):
        print(format % args)

httpd = HTTPServer(('0.0.0.0', 80), Serv)
httpd.serve_forever()
