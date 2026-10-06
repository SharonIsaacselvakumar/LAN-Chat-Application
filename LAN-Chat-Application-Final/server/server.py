
import base64
import socket
import threading
import time
from datetime import datetime
from pathlib import Path

from shared.protocol import encode, decode
from shared.security import hash_password, verify_password
from server.database import Database

HOST = "0.0.0.0"
PORT = 5000
ROOT = Path(__file__).resolve().parent.parent
DB = Database(ROOT / "data" / "chat_history.db")
DOWNLOADS = ROOT / "data" / "server_files"
DOWNLOADS.mkdir(parents=True, exist_ok=True)

clients = {}
lock = threading.RLock()
stats = {"messages": 0, "files": 0, "bytes": 0, "started": time.time()}

def send(conn, obj):
    try:
        conn.sendall(encode(obj))
        return True
    except OSError:
        return False

def users():
    with lock:
        return sorted(
            [{"username": v["username"], "ip": v["address"][0]}
             for v in clients.values()],
            key=lambda x: x["username"].lower()
        )

def broadcast(obj, exclude=None):
    dead = []
    with lock:
        current = list(clients)
    for c in current:
        if c is exclude:
            continue
        if not send(c, obj):
            dead.append(c)
    for c in dead:
        remove_client(c)

def remove_client(conn):
    with lock:
        info = clients.pop(conn, None)
    if info:
        try: conn.close()
        except OSError: pass
        broadcast({"type": "system", "text": f"{info['username']} left the chat."})
        broadcast({"type": "users", "users": users()})
        print(f"[-] {info['username']} disconnected")

def private_target(name):
    with lock:
        for c, info in clients.items():
            if info["username"].lower() == name.lower():
                return c
    return None

def send_history(conn, username):
    for row in DB.history(username):
        send(conn, {"type": "history", "data": row})
    send(conn, {"type": "file_history", "files": DB.file_history(username)})
    send(conn, {"type": "history_done"})

def handle_file(conn, req):
    sender = clients[conn]["username"]
    receiver = str(req.get("receiver", "*")).strip() or "*"
    filename = Path(str(req.get("filename", "file.bin"))).name
    try:
        raw = base64.b64decode(req.get("data", ""), validate=True)
    except Exception:
        send(conn, {"type": "error", "message": "Invalid file data."})
        return
    if len(raw) > 8 * 1024 * 1024:
        send(conn, {"type": "error", "message": "Maximum file size is 8 MB."})
        return

    if receiver != "*" and private_target(receiver) is None:
        send(conn, {"type": "file_failed", "filename": filename,
                    "message": f"{receiver} is not online."})
        return

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    DB.save_file(sender, receiver, filename, len(raw), ts)
    stats["files"] += 1
    stats["bytes"] += len(raw)

    payload = {
        "type": "file", "sender": sender, "receiver": receiver,
        "filename": filename, "size": len(raw),
        "data": base64.b64encode(raw).decode("ascii"),
        "timestamp": ts
    }

    delivered = 0
    if receiver == "*":
        with lock:
            targets = [(c, info["username"]) for c, info in clients.items() if c is not conn]
    else:
        target = private_target(receiver)
        targets = [(target, receiver)] if target else []

    for target, _ in targets:
        if target and send(target, payload):
            delivered += 1

    send(conn, {"type": "file_sent", "filename": filename, "receiver": receiver,
                "size": len(raw), "timestamp": ts, "delivered": delivered})

def client_thread(conn, address):
    username = None
    reader = None
    try:
        reader = conn.makefile("r", encoding="utf-8", newline="\n")
        send(conn, {"type": "hello", "message": "Server ready"})

        for line in reader:
            try:
                req = decode(line)
            except Exception:
                send(conn, {"type": "error", "message": "Invalid JSON request."})
                continue

            typ = req.get("type")

            if typ == "register":
                name = str(req.get("username", "")).strip()
                password = str(req.get("password", ""))
                if not name or len(name) > 24 or not password:
                    send(conn, {"type": "error", "message": "Enter a valid username and password."})
                    continue
                if DB.user_exists(name):
                    send(conn, {"type": "error", "message": "Username already exists."})
                    continue
                salt, digest = hash_password(password)
                DB.create_user(name, salt, digest, datetime.now().isoformat(timespec="seconds"))
                send(conn, {"type": "register_ok", "message": "Account created. You can now log in."})
                continue

            if typ == "login":
                name = str(req.get("username", "")).strip()
                password = str(req.get("password", ""))
                row = DB.get_user(name)
                if not row or not verify_password(password, row["salt"], row["password_hash"]):
                    send(conn, {"type": "error", "message": "Invalid username or password."})
                    continue
                with lock:
                    if any(v["username"].lower() == name.lower() for v in clients.values()):
                        send(conn, {"type": "error", "message": "That user is already connected."})
                        continue
                    clients[conn] = {"username": name, "address": address}
                username = name
                send(conn, {"type": "login_ok", "username": username, "users": users()})
                send_history(conn, username)
                broadcast({"type": "system", "text": f"{username} joined the chat."}, exclude=conn)
                broadcast({"type": "users", "users": users()})
                print(f"[+] {username} connected from {address[0]}:{address[1]}")
                continue

            if not username:
                send(conn, {"type": "error", "message": "Please log in first."})
                continue

            if typ == "chat":
                text = str(req.get("text", "")).strip()
                if not text: continue
                if len(text) > 2000:
                    send(conn, {"type": "error", "message": "Message limit is 2000 characters."})
                    continue
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                DB.save_message(username, "*", text, ts)
                stats["messages"] += 1
                packet = {"type":"chat","sender":username,"receiver":"*","text":text,"timestamp":ts}
                broadcast(packet)
                continue

            if typ == "private":
                receiver = str(req.get("receiver", "")).strip()
                text = str(req.get("text", "")).strip()
                target = private_target(receiver)
                if not target:
                    send(conn, {"type":"error","message":f"{receiver} is not online."})
                    continue
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                DB.save_message(username, receiver, text, ts)
                stats["messages"] += 1
                packet = {"type":"private","sender":username,"receiver":receiver,"text":text,"timestamp":ts}
                send(target, packet)
                send(conn, packet)
                continue

            if typ == "search":
                send(conn, {"type":"search_results",
                             "results":DB.search(username, str(req.get("query","")))})
                continue

            if typ == "file":
                handle_file(conn, req)
                continue

            if typ == "stats":
                with lock: count = len(clients)
                send(conn, {"type":"stats","connected":count,
                            "messages":stats["messages"],"files":stats["files"],
                            "bytes":stats["bytes"],
                            "uptime":int(time.time()-stats["started"])})
                continue

            if typ == "ping":
                send(conn, {"type":"pong","sent":req.get("sent")})
                continue

            if typ == "logout":
                break

            send(conn, {"type":"error","message":f"Unknown request: {typ}"})

    except (ConnectionResetError, ConnectionAbortedError, OSError):
        pass
    finally:
        try:
            if reader: reader.close()
        except OSError: pass
        if conn in clients:
            remove_client(conn)
        else:
            try: conn.close()
            except OSError: pass

def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(50)
    print("=" * 60)
    print("             LAN CHAT APPLICATION - FINAL")
    print("=" * 60)
    print(f"Server listening on 0.0.0.0:{PORT}")
    print("Use this computer's Wi-Fi IPv4 address on other laptops.")
    print("Press Ctrl+C to stop.")
    print("=" * 60)
    try:
        while True:
            conn, address = server.accept()
            threading.Thread(target=client_thread, args=(conn,address), daemon=True).start()
    except KeyboardInterrupt:
        print("\nStopping server...")
    finally:
        with lock:
            current = list(clients)
            clients.clear()
        for c in current:
            try: c.close()
            except OSError: pass
        server.close()

if __name__ == "__main__":
    main()
