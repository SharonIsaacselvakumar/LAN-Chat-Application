
# LAN Chat Application - FINAL

A complete Python TCP LAN chat mini-project with a modern Tkinter interface.

## Features

- TCP client/server architecture
- Multiple simultaneous LAN clients
- JSON application protocol
- User registration and login
- PBKDF2-HMAC-SHA256 password hashing
- Real-time online user list
- Group chat
- Private one-to-one chat
- Join/leave notifications
- Message timestamps and chat bubbles
- SQLite persistent message history
- Message search
- File sharing up to 8 MB
- Automatic file downloads
- Network dashboard
- Latency measurement
- Session statistics
- Modular server/client/shared structure
- No third-party packages

## Run

From the project root:

Server:
    python -m server.server

Client:
    python -m client.client

Or double-click:
    run_server.bat
    run_client.bat

## First login

Click Register on the client, create a username and password, then log in.

## Two laptops

Laptop A:
    python -m server.server

Run:
    ipconfig

Find the Wi-Fi IPv4 address, for example:
    192.168.1.5

Laptop B:
    python -m client.client

Enter:
    Server IP = 192.168.1.5

Do NOT use 127.0.0.1 on Laptop B.

Both laptops must be on the same LAN/Wi-Fi.

Test from Laptop B:
    Test-NetConnection 192.168.1.5 -Port 5000

Expected:
    TcpTestSucceeded : True

If false, check Windows Firewall and whether the Wi-Fi uses client isolation. A phone hotspot can be used for a clean two-laptop demo.

## Project structure

LAN-Chat-Application-Final/
    server/
        server.py
        database.py
        auth.py
        client_manager.py
        message_handler.py
        file_handler.py
    client/
        client.py
        network.py
        chat.py
        files.py
        notifications.py
        database.py
    shared/
        protocol.py
        security.py
        encryption.py
    data/
    downloads/
    requirements.txt
    README.md

## Notes

SQLite creates data/chat_history.db automatically.

Files received by the client are saved in downloads/.

The final build uses password hashing, but it does not claim production-grade end-to-end encryption. For real deployment, use TLS with managed certificates/keys. The code is structured so TLS can be introduced without changing the application protocol.

## Computer Networks viva points

- TCP provides reliable, ordered delivery.
- The server binds to 0.0.0.0:5000.
- Each client connection is handled by a separate thread.
- JSON is the application-layer protocol.
- The server maintains an active client registry.
- Broadcast sends a message to all connected clients.
- Private messages are routed to a selected client.
- File data is transferred over the TCP application channel.
- SQLite provides persistent application-level storage.
- IP address identifies the host and port 5000 identifies the server service.
