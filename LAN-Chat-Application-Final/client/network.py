
import json
import socket
import threading

class NetworkClient:
    def __init__(self, on_message, on_disconnect):
        self.sock = None
        self.reader = None
        self.running = False
        self.lock = threading.Lock()
        self.on_message = on_message
        self.on_disconnect = on_disconnect

    def connect(self, host, port):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(6)
        self.sock.connect((host, port))
        self.sock.settimeout(None)
        self.reader = self.sock.makefile("r", encoding="utf-8", newline="\n")
        self.running = True
        threading.Thread(target=self.receive_loop, daemon=True).start()

    def send(self, obj):
        if not self.running: return False
        data = (json.dumps(obj, ensure_ascii=False, separators=(",",":")) + "\n").encode()
        try:
            with self.lock:
                self.sock.sendall(data)
            return True
        except OSError:
            self.disconnect()
            return False

    def receive_loop(self):
        try:
            while self.running:
                line = self.reader.readline()
                if not line: break
                try:
                    self.on_message(json.loads(line))
                except json.JSONDecodeError:
                    pass
        except OSError:
            pass
        finally:
            if self.running:
                self.running = False
                self.on_disconnect()

    def disconnect(self):
        self.running = False
        if self.sock:
            try: self.sock.shutdown(socket.SHUT_RDWR)
            except OSError: pass
            try: self.sock.close()
            except OSError: pass
        self.sock = None
        self.reader = None
