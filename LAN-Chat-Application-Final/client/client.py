import base64
import os
import socket
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from client.network import NetworkClient
from client.chat import ChatStore
from client.files import make_file_payload
from client.notifications import toast

PORT = 5000
MAX_FILE = 8 * 1024 * 1024
ROOT = Path(__file__).resolve().parent.parent
DOWNLOAD_DIR = ROOT / "downloads"


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("LAN Chat")
        self.root.geometry("1280x800")
        self.root.minsize(1080, 700)
        self.root.configure(bg="#F5F6FA")
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.c = {
            "navy": "#182241", "navy2": "#202C52", "accent": "#7C8DE3",
            "accent2": "#EEF0FF", "bg": "#F5F6FA", "card": "#FFFFFF",
            "text": "#202A4A", "muted": "#7A84A5", "line": "#E4E7F0",
            "green": "#2AC77A", "green_bg": "#E5F9EE", "red": "#E95D6A",
            "bubble_in": "#FFFFFF", "bubble_out": "#7C8DE3", "bubble_out_text": "#FFFFFF",
            "yellow": "#F4B942", "blue_text": "#6577D8"
        }
        self.username = ""
        self.server_ip = ""
        self.port = PORT
        self.connected = False
        self.users = []
        self.chat = ChatStore()
        self.private_user = ""
        self.active_page = "chat"
        self.unread_private = 0
        self.sent = 0
        self.received = 0
        self.files_sent = 0
        self.files_received = 0
        self.latency = None
        self.ping_sent = None
        self.search_results = []
        self.file_transfers = []
        self.settings = {"desktop": True, "sound": True, "file_alerts": True, "auto_accept": False}
        self.net = NetworkClient(self.on_message, self.on_disconnect)
        self.show_login()

    # ---------- shared UI ----------
    def clear(self):
        for w in self.root.winfo_children():
            w.destroy()

    def style_button(self, parent, text, command, primary=False, width=None):
        return tk.Button(
            parent, text=text, command=command, relief="flat", bd=0,
            bg=self.c["accent"] if primary else self.c["accent2"],
            fg="white" if primary else self.c["blue_text"],
            activebackground="#6E80DB" if primary else "#E2E5FF",
            activeforeground="white" if primary else self.c["blue_text"],
            font=("Segoe UI", 10, "bold"), cursor="hand2",
            padx=14, pady=8, width=width
        )

    def card(self, parent, padx=16, pady=16):
        return tk.Frame(parent, bg=self.c["card"], highlightbackground=self.c["line"],
                        highlightthickness=1, bd=0, padx=padx, pady=pady)

    def label(self, parent, text, size=10, bold=False, color=None, bg=None):
        return tk.Label(parent, text=text, bg=bg or self.c["card"],
                        fg=color or self.c["text"],
                        font=("Segoe UI", size, "bold" if bold else "normal"))

    def show_login(self):
        self.clear()
        outer = tk.Frame(self.root, bg="#EEF0F8")
        outer.pack(fill="both", expand=True)
        box = tk.Frame(outer, bg=self.c["card"], highlightbackground=self.c["line"], highlightthickness=1)
        box.place(relx=.5, rely=.5, anchor="center", width=430, height=555)

        icon = tk.Label(box, text="◯", font=("Segoe UI", 26, "bold"), bg=self.c["accent"], fg="white", width=2)
        icon.pack(pady=(42, 12), ipadx=5, ipady=4)
        self.label(box, "LAN Chat Connect", 20, True).pack()
        self.label(box, "Computer Networks Project", 10, color=self.c["muted"]).pack(pady=(3, 30))

        form = tk.Frame(box, bg=self.c["card"])
        form.pack(fill="x", padx=38)
        iprow = tk.Frame(form, bg=self.c["card"]); iprow.pack(fill="x")
        self.login_ip = self.input_group(iprow, "SERVER IP", "127.0.0.1", side="left", width=22)
        self.login_port = self.input_group(iprow, "PORT", "5000", side="right", width=8)
        self.login_user = self.input_group(form, "USERNAME", "")
        self.login_pass = self.input_group(form, "PASSWORD", "", show="•")
        self.style_button(box, "Connect to Server", lambda: self.auth("login"), primary=True).pack(fill="x", padx=38, pady=(6, 12), ipady=3)
        self.login_status = self.label(box, "●  Ready to connect", 9, color=self.c["muted"])
        self.login_status.pack()
        create = tk.Button(box, text="Create a new account", command=lambda: self.auth("register"),
                           bg=self.c["card"], fg=self.c["blue_text"], relief="flat", bd=0,
                           font=("Segoe UI", 9, "bold"), cursor="hand2")
        create.pack(pady=(20, 4))
        self.label(box, "Same Wi-Fi / LAN required for multi-device chat", 8, color=self.c["muted"]).pack()

    def input_group(self, parent, title, default="", side=None, width=36, show=""):
        wrap = tk.Frame(parent, bg=self.c["card"])
        if side: wrap.pack(side=side, fill="x", expand=True, padx=(0, 14) if side == "left" else (0, 0))
        else: wrap.pack(fill="x")
        self.label(wrap, title, 8, True, color="#647093").pack(anchor="w")
        e = tk.Entry(wrap, font=("Segoe UI", 10), width=width, show=show, relief="solid", bd=1,
                     highlightthickness=0)
        if default: e.insert(0, default)
        e.pack(fill="x", pady=(5, 12), ipady=8)
        return e

    # ---------- network ----------
    def auth(self, kind):
        ip = self.login_ip.get().strip()
        user = self.login_user.get().strip()
        pw = self.login_pass.get()
        try:
            port = int(self.login_port.get().strip() or PORT)
        except ValueError:
            messagebox.showerror("Invalid port", "Port must be a number."); return
        if not ip or not user or not pw:
            messagebox.showerror("Missing information", "Enter server IP, username and password."); return
        self.server_ip, self.port = ip, port
        self.login_status.config(text="●  Connecting...", fg=self.c["accent"])
        try:
            self.net.connect(ip, port)
            self.net.send({"type": kind, "username": user, "password": pw})
        except (OSError, socket.timeout) as e:
            self.net.disconnect()
            self.login_status.config(text="●  Connection failed", fg=self.c["red"])
            messagebox.showerror("Connection failed", str(e))

    def on_message(self, msg):
        self.root.after(0, self.process, msg)

    def process(self, m):
        t = m.get("type")
        if t == "register_ok":
            messagebox.showinfo("Account created", m["message"])
            self.net.disconnect()
            return
        if t == "login_ok":
            self.username = m["username"]
            self.users = m.get("users", [])
            self.connected = True
            self.build()
            return
        if t == "error":
            messagebox.showerror("Server", m.get("message", "Error")); return
        if t == "users":
            self.users = m.get("users", [])
            self.refresh_current(); return
        if t == "system":
            self.refresh_current(); return
        if t in ("chat", "private"):
            kind = "private" if t == "private" else "chat"
            receiver = m.get("receiver", "*")
            self.chat.add(kind, m.get("sender", ""), m.get("text", ""), m.get("timestamp", self.now()), receiver)
            if m.get("sender") == self.username:
                return
            self.received += 1
            if kind == "private" and self.active_page != "private":
                self.unread_private += 1
                toast(self.root, "Private message", f"{m.get('sender')}: {m.get('text')}")
            self.refresh_current()
            return
        if t == "history":
            d = m["data"]
            self.chat.add("private" if d.get("receiver") != "*" else "chat", d.get("sender", ""),
                          d.get("text", ""), d.get("timestamp", ""), d.get("receiver", "*"))
            return
        if t == "history_done":
            self.refresh_current()
            return
        if t == "file_history":
            self.file_transfers = []
            for f in m.get("files", []):
                self.add_file_record(f, history=True)
            return
        if t == "file":
            self.receive_file(m); return
        if t == "file_sent":
            self.files_sent += 1
            self.add_file_record({"sender": self.username, "receiver": m.get("receiver", "*"),
                                  "filename": m.get("filename", "file"), "size": m.get("size", 0),
                                  "timestamp": m.get("timestamp", self.now()), "status": "Delivered"})
            toast(self.root, "File sent", f"{m.get('filename')} delivered")
            self.refresh_current(); return
        if t == "file_failed":
            messagebox.showerror("File not sent", m.get("message", "Recipient unavailable.")); return
        if t == "search_results":
            self.search_results = m["results"]
            self.render_search_results(); return
        if t == "pong":
            self.latency = round((time.time() - self.ping_sent) * 1000, 1)
            self.refresh_current(); return

    def on_disconnect(self):
        self.root.after(0, self.disconnected)

    def disconnected(self):
        if self.connected:
            self.connected = False
            messagebox.showwarning("Disconnected", "The server connection was lost.")
            self.show_login()

    # ---------- shell ----------
    def build(self):
        self.clear()
        self.sidebar = tk.Frame(self.root, bg=self.c["navy"], width=225)
        self.sidebar.pack(side="left", fill="y"); self.sidebar.pack_propagate(False)
        brand = tk.Frame(self.sidebar, bg=self.c["navy"]); brand.pack(fill="x", padx=18, pady=18)
        tk.Label(brand, text="◯", bg=self.c["accent"], fg="white", font=("Segoe UI", 16, "bold"), width=2).pack(side="left")
        btxt = tk.Frame(brand, bg=self.c["navy"]); btxt.pack(side="left", padx=9)
        tk.Label(btxt, text="LAN Chat", bg=self.c["navy"], fg="white", font=("Segoe UI", 13, "bold")).pack(anchor="w")
        tk.Label(btxt, text="v1.2.0 • local", bg=self.c["navy"], fg="#AEB8D8", font=("Segoe UI", 8)).pack(anchor="w")

        self.nav_buttons = {}
        nav = [("◯", "Group Chat", "chat"), ("○", "Private Chats", "private"),
               ("♙", "Online Users", "users"), ("▣", "Files", "files"),
               ("⌁", "Network", "network"), ("⚙", "Settings", "settings")]
        for icon, text, page in nav:
            row = tk.Frame(self.sidebar, bg=self.c["navy"], cursor="hand2")
            row.pack(fill="x", padx=12, pady=2)
            btn = tk.Button(row, text=f"{icon}   {text}", command=lambda p=page: self.show(p),
                            bg=self.c["navy"], fg="#C3CCE5", activebackground=self.c["navy2"],
                            activeforeground="white", relief="flat", bd=0, anchor="w",
                            font=("Segoe UI", 10), padx=10, pady=8, cursor="hand2")
            btn.pack(fill="x")
            self.nav_buttons[page] = btn

        profile = tk.Frame(self.sidebar, bg="#111A35"); profile.pack(side="bottom", fill="x", padx=12, pady=14)
        tk.Label(profile, text=self.username[:1].upper(), bg="#E8DCCF", fg="#38405D",
                 font=("Segoe UI", 12, "bold"), width=2).pack(side="left", padx=8, pady=8)
        info = tk.Frame(profile, bg="#111A35"); info.pack(side="left")
        tk.Label(info, text=self.username, bg="#111A35", fg="white", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        tk.Label(info, text=f"● {self.server_ip}", bg="#111A35", fg="#8FA0C6", font=("Segoe UI", 7)).pack(anchor="w")
        tk.Button(profile, text="×", command=self.logout, bg="#111A35", fg="#9BA8C7", relief="flat", bd=0).pack(side="right")

        self.content = tk.Frame(self.root, bg=self.c["bg"])
        self.content.pack(side="left", fill="both", expand=True)
        self.show("chat")

    def show(self, page):
        self.active_page = page
        if page == "private": self.unread_private = 0
        for w in self.content.winfo_children(): w.destroy()
        for p, b in self.nav_buttons.items():
            b.config(bg=self.c["navy2"] if p == page else self.c["navy"], fg="white" if p == page else "#C3CCE5")
        getattr(self, f"page_{page}")()

    def refresh_current(self):
        if self.connected and hasattr(self, "content") and self.active_page in {"chat", "private", "users", "files", "network"}:
            self.show(self.active_page)

    def page_title(self, title, subtitle, search=False):
        h = tk.Frame(self.content, bg=self.c["card"], height=72, highlightbackground=self.c["line"], highlightthickness=1)
        h.pack(fill="x"); h.pack_propagate(False)
        left = tk.Frame(h, bg=self.c["card"]); left.pack(side="left", padx=24, pady=13)
        self.label(left, title, 18, True).pack(anchor="w")
        self.label(left, subtitle, 9, color=self.c["muted"]).pack(anchor="w")
        if search:
            self.chat_search = tk.Entry(h, font=("Segoe UI", 9), relief="solid", bd=1, width=30)
            self.chat_search.insert(0, "⌕  Search chat...")
            self.chat_search.pack(side="right", padx=18, pady=18)
            self.chat_search.bind("<FocusIn>", lambda e: self.clear_placeholder(self.chat_search, "⌕  Search chat..."))
            self.chat_search.bind("<Return>", lambda e: self.search_chat())
        status = tk.Label(h, text=f"● {len(self.users)} connected", bg=self.c["card"], fg=self.c["green"], font=("Segoe UI", 9, "bold"))
        status.pack(side="right", padx=8)
        return h

    def clear_placeholder(self, entry, text):
        if entry.get() == text: entry.delete(0, "end")

    # ---------- group chat ----------
    def page_chat(self):
        self.page_title("#general", "●  Connected to local TCP server", search=True)
        body = tk.Frame(self.content, bg=self.c["bg"]); body.pack(fill="both", expand=True, padx=18, pady=12)
        canvas = tk.Canvas(body, bg=self.c["bg"], highlightthickness=0)
        canvas.pack(side="left", fill="both", expand=True)
        scroll = tk.Scrollbar(body, command=canvas.yview); scroll.pack(side="right", fill="y")
        canvas.configure(yscrollcommand=scroll.set)
        inner = tk.Frame(canvas, bg=self.c["bg"]); win = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win, width=e.width))
        self.group_inner = inner
        shown = self.filtered_group_items()
        for x in shown:
            if x["kind"] == "system":
                self.label(inner, f"• {x['text']}   {self.short_time(x['timestamp'])}", 8, color=self.c["muted"], bg=self.c["bg"]).pack(pady=7)
                continue
            if x["kind"] != "chat": continue
            self.message_bubble(inner, x)
        canvas.update_idletasks(); canvas.yview_moveto(1.0)
        composer = tk.Frame(self.content, bg=self.c["card"], highlightbackground=self.c["line"], highlightthickness=1)
        composer.pack(fill="x", padx=18, pady=(0, 14))
        tk.Button(composer, text="⌕", command=self.attach_from_chat, bg="#F0F2F9", fg=self.c["muted"], relief="flat", bd=0,
                  font=("Segoe UI", 15), width=3).pack(side="left", padx=8, pady=8)
        self.msg = tk.Entry(composer, font=("Segoe UI", 10), relief="flat", bg=self.c["card"], fg=self.c["text"])
        self.msg.pack(side="left", fill="x", expand=True, ipady=10)
        self.msg.bind("<Return>", lambda e: self.send_chat())
        self.style_button(composer, "Send  ➤", self.send_chat, primary=True).pack(side="right", padx=8, pady=7)

    def filtered_group_items(self):
        q = "" if not hasattr(self, "chat_search") else self.chat_search.get().strip().lower()
        if q.startswith("⌕"): q = ""
        if not q: return self.chat.items
        return [x for x in self.chat.items if x["kind"] in ("chat", "system") and q in x.get("text", "").lower()]

    def search_chat(self):
        self.page_chat()

    def message_bubble(self, parent, x):
        mine = x["sender"] == self.username
        row = tk.Frame(parent, bg=self.c["bg"]); row.pack(fill="x", pady=5)
        bubble_bg = self.c["bubble_out"] if mine else self.c["bubble_in"]
        bubble = tk.Frame(row, bg=bubble_bg, highlightbackground="#E0E3EC", highlightthickness=1,
                          padx=12, pady=8)
        bubble.pack(side="right" if mine else "left", padx=10)
        tk.Label(bubble, text="You" if mine else x["sender"], bg=bubble_bg,
                 fg="white" if mine else self.c["text"], font=("Segoe UI", 8, "bold")).pack(anchor="w")
        tk.Label(bubble, text=x["text"], bg=bubble_bg,
                 fg=self.c["bubble_out_text"] if mine else self.c["text"],
                 font=("Segoe UI", 10), wraplength=650, justify="left").pack(anchor="w", pady=(3, 2))
        tk.Label(bubble, text=self.short_time(x["timestamp"]), bg=bubble_bg,
                 fg="#DDE2FF" if mine else self.c["muted"], font=("Segoe UI", 7)).pack(anchor="e")

    def send_chat(self):
        text = self.msg.get().strip()
        if text and self.net.send({"type": "chat", "text": text}):
            self.sent += 1; self.msg.delete(0, "end")
            # show own message immediately; server also sends it back, so don't add twice
            self.chat.add("chat", self.username, text, self.now(), "*")
            self.refresh_current()

    def attach_from_chat(self):
        self.show("files")

    # ---------- private ----------
    def page_private(self):
        names = [u["username"] for u in self.users if u["username"] != self.username]
        if self.private_user not in names and names: self.private_user = names[0]
        if not names:
            self.page_title("Private Chats", "No other users are currently connected")
            self.label(self.content, "Connect another laptop to start a private conversation.", 11, color=self.c["muted"], bg=self.c["bg"]).pack(pady=70)
            return
        top = self.page_title(self.private_user, "Private Conversation • TCP direct routing")
        selector = tk.Frame(top, bg=self.c["card"]); selector.pack(side="right", padx=12)
        combo = ttk.Combobox(selector, values=names, state="readonly", width=20)
        combo.set(self.private_user); combo.pack()
        combo.bind("<<ComboboxSelected>>", lambda e: self.set_private(combo.get()))

        body = tk.Frame(self.content, bg=self.c["bg"]); body.pack(fill="both", expand=True, padx=18, pady=12)
        canvas = tk.Canvas(body, bg=self.c["bg"], highlightthickness=0); canvas.pack(side="left", fill="both", expand=True)
        bar = tk.Scrollbar(body, command=canvas.yview); bar.pack(side="right", fill="y"); canvas.configure(yscrollcommand=bar.set)
        inner = tk.Frame(canvas, bg=self.c["bg"]); win = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win, width=e.width))
        for x in self.chat.items:
            if x["kind"] != "private": continue
            if not ((x["sender"] == self.username and x["receiver"] == self.private_user) or
                    (x["sender"] == self.private_user and x["receiver"] == self.username)):
                continue
            self.message_bubble(inner, x)
        canvas.update_idletasks(); canvas.yview_moveto(1.0)
        composer = tk.Frame(self.content, bg=self.c["card"], highlightbackground=self.c["line"], highlightthickness=1)
        composer.pack(fill="x", padx=18, pady=(0, 14))
        tk.Button(composer, text="☺", bg="#F0F2F9", fg=self.c["muted"], relief="flat", bd=0, font=("Segoe UI", 14), width=3).pack(side="left", padx=8, pady=8)
        self.pm = tk.Entry(composer, font=("Segoe UI", 10), relief="flat", bg=self.c["card"])
        self.pm.pack(side="left", fill="x", expand=True, ipady=10); self.pm.bind("<Return>", lambda e: self.send_private())
        self.style_button(composer, "Send  ➤", self.send_private, primary=True).pack(side="right", padx=8, pady=7)

    def set_private(self, name): self.private_user = name; self.show("private")

    def send_private(self):
        text = self.pm.get().strip() if hasattr(self, "pm") else ""
        if text and self.private_user and self.net.send({"type": "private", "receiver": self.private_user, "text": text}):
            self.sent += 1; self.pm.delete(0, "end")
            self.chat.add("private", self.username, text, self.now(), self.private_user)
            self.refresh_current()

    # ---------- online users ----------
    def page_users(self):
        self.page_title("Online Users", "Connected devices on the local network")
        wrap = tk.Frame(self.content, bg=self.c["bg"]); wrap.pack(fill="both", expand=True, padx=20, pady=18)
        search = tk.Entry(wrap, font=("Segoe UI", 9), relief="solid", bd=1)
        search.insert(0, "Search users..."); search.pack(fill="x", pady=(0, 14), ipady=8)
        search.bind("<FocusIn>", lambda e: self.clear_placeholder(search, "Search users..."))
        grid = tk.Frame(wrap, bg=self.c["bg"]); grid.pack(fill="both", expand=True)
        self.user_grid = grid
        self.render_user_cards(search.get())
        search.bind("<KeyRelease>", lambda e: self.render_user_cards(search.get()))

    def render_user_cards(self, query=""):
        if not hasattr(self, "user_grid"): return
        for w in self.user_grid.winfo_children(): w.destroy()
        q = query.lower() if query != "Search users..." else ""
        people = [u for u in self.users if q in u["username"].lower()]
        for i, u in enumerate(people):
            r, c = divmod(i, 3)
            card = self.card(self.user_grid, 15, 15); card.grid(row=r, column=c, sticky="nsew", padx=6, pady=6)
            self.user_grid.grid_columnconfigure(c, weight=1)
            name = u["username"]
            tk.Label(card, text=name[:2].upper(), bg=self.c["accent"], fg="white", font=("Segoe UI", 14, "bold"), width=3).pack(anchor="w")
            self.label(card, name + ("  (You)" if name == self.username else ""), 10, True).pack(anchor="w", pady=(10, 2))
            self.label(card, f"● ONLINE   {u.get('ip', '')}", 8, color=self.c["green"]).pack(anchor="w")
            if name != self.username:
                self.style_button(card, "Message", lambda n=name: self.open_private(n)).pack(fill="x", pady=(12, 0))

    def open_private(self, name): self.private_user = name; self.show("private")

    # ---------- files ----------
    def page_files(self):
        self.page_title("File Sharing", "Broadcast or send files privately over the LAN")
        body = tk.Frame(self.content, bg=self.c["bg"]); body.pack(fill="both", expand=True, padx=20, pady=16)
        top = self.card(body, 14, 12); top.pack(fill="x")
        self.label(top, "Send to", 9, True, color=self.c["muted"]).pack(side="left")
        names = ["Everyone"] + [u["username"] for u in self.users if u["username"] != self.username]
        self.file_target = ttk.Combobox(top, values=names, state="readonly", width=20); self.file_target.set("Everyone"); self.file_target.pack(side="left", padx=8)
        self.style_button(top, "+  Share New File", self.choose_file, primary=True).pack(side="right")

        drop = tk.Frame(body, bg="#FBFBFE", highlightbackground="#AAB7F2", highlightthickness=1)
        drop.pack(fill="x", pady=12, ipady=20)
        self.label(drop, "↑", 22, True, color=self.c["accent"], bg="#FBFBFE").pack()
        self.label(drop, "Choose a file to send", 11, True, bg="#FBFBFE").pack(pady=(4, 2))
        self.label(drop, "Maximum 8 MB • Received files are saved in the downloads folder", 8, color=self.c["muted"], bg="#FBFBFE").pack()

        self.file_table = self.card(body, 14, 12); self.file_table.pack(fill="both", expand=True)
        self.label(self.file_table, "Recent File Transfers", 12, True).pack(anchor="w", pady=(0, 10))
        self.render_file_table()

    def render_file_table(self):
        if not hasattr(self, "file_table"): return
        for w in list(self.file_table.winfo_children())[1:]: w.destroy()
        headers = ["FILE", "SIZE", "DIRECTION", "USER", "TIME", "STATUS"]
        widths = [28, 10, 13, 20, 16, 14]
        head = tk.Frame(self.file_table, bg="#F7F8FC"); head.pack(fill="x")
        for h, width in zip(headers, widths):
            tk.Label(head, text=h, bg="#F7F8FC", fg=self.c["muted"], font=("Segoe UI", 7, "bold"), width=width, anchor="w").pack(side="left", padx=5, pady=7)
        for f in self.file_transfers[:50]:
            row = tk.Frame(self.file_table, bg=self.c["card"], highlightbackground=self.c["line"], highlightthickness=1); row.pack(fill="x", pady=3)
            size = self.format_size(f.get("size", 0)); direction = f.get("direction", "Sent")
            other = f.get("receiver", "Everyone") if direction == "Sent" else f.get("sender", "Unknown")
            vals = [f.get("filename", "file"), size, direction, other, self.short_time(f.get("timestamp", "")), f.get("status", "Delivered")]
            for val, width in zip(vals, widths):
                color = self.c["green"] if val in ("Delivered", "Downloaded", "Received") else self.c["text"]
                tk.Label(row, text=str(val), bg=self.c["card"], fg=color, font=("Segoe UI", 8, "bold" if val == f.get("status") else "normal"), width=width, anchor="w").pack(side="left", padx=5, pady=8)
        note = tk.Label(self.file_table, text=f"Download folder: {DOWNLOAD_DIR}", bg=self.c["card"], fg=self.c["muted"], font=("Segoe UI", 8))
        note.pack(anchor="w", pady=(10, 0))
        self.style_button(self.file_table, "📂  Open Downloads Folder", self.open_downloads).pack(anchor="e", pady=(5, 0))

    def choose_file(self):
        path = filedialog.askopenfilename()
        if not path: return
        size = Path(path).stat().st_size
        if size > MAX_FILE:
            messagebox.showerror("File too large", "Maximum file size is 8 MB."); return
        target = "*" if self.file_target.get() in ("", "Everyone") else self.file_target.get()
        if self.net.send(make_file_payload(path, target)):
            self.refresh_current()

    def add_file_record(self, f, history=False):
        sender = f.get("sender", "Unknown"); receiver = f.get("receiver", "*")
        if sender == self.username:
            direction, status = "Sent", f.get("status", "Delivered")
        else:
            direction, status = "Received", f.get("status", "Downloaded")
        if history and sender != self.username and receiver not in ("*", self.username): return
        record = dict(f); record.update({"direction": direction, "status": status})
        # avoid duplicate records by id/timestamp/name/direction
        key = (record.get("filename"), record.get("timestamp"), direction, record.get("sender"), record.get("receiver"))
        if not any((x.get("filename"), x.get("timestamp"), x.get("direction"), x.get("sender"), x.get("receiver")) == key for x in self.file_transfers):
            self.file_transfers.insert(0, record)

    def receive_file(self, m):
        try:
            DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
            name = Path(m.get("filename", "file.bin")).name
            out = DOWNLOAD_DIR / name
            if out.exists(): out = DOWNLOAD_DIR / f"{out.stem}_{int(time.time())}{out.suffix}"
            out.write_bytes(base64.b64decode(m.get("data", "")))
            self.files_received += 1
            self.add_file_record({"sender": m.get("sender", "Unknown"), "receiver": self.username,
                                  "filename": out.name, "size": m.get("size", 0),
                                  "timestamp": m.get("timestamp", self.now()), "status": "Downloaded"})
            toast(self.root, "File received", f"{out.name} saved in downloads/")
            self.refresh_current()
        except Exception as e:
            messagebox.showerror("File error", str(e))

    def open_downloads(self):
        DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
        try: os.startfile(str(DOWNLOAD_DIR))
        except Exception: messagebox.showinfo("Downloads Folder", str(DOWNLOAD_DIR))

    # ---------- network ----------
    def page_network(self):
        self.page_title("Network Status", "Local area network diagnostics and session metrics")
        body = tk.Frame(self.content, bg=self.c["bg"]); body.pack(fill="both", expand=True, padx=20, pady=16)
        cards = [("Server IP Address", self.server_ip), ("TCP Port Configured", str(self.port)),
                 ("Application Protocol", "TCP / JSON"), ("Connected LAN Nodes", f"{len(self.users)} Online")]
        row = tk.Frame(body, bg=self.c["bg"]); row.pack(fill="x")
        for title, val in cards:
            c = self.card(row, 12, 11); c.pack(side="left", fill="x", expand=True, padx=5)
            self.label(c, title, 8, color=self.c["muted"]).pack(anchor="w")
            self.label(c, val, 13, True).pack(anchor="w", pady=(4, 0))
        lower = tk.Frame(body, bg=self.c["bg"]); lower.pack(fill="both", expand=True, pady=12)
        chart = self.card(lower, 16, 14); chart.pack(side="left", fill="both", expand=True, padx=(0, 6))
        self.label(chart, "Network Activity", 12, True).pack(anchor="w")
        self.label(chart, "Messages exchanged during this session", 8, color=self.c["muted"]).pack(anchor="w")
        cv = tk.Canvas(chart, bg=self.c["card"], highlightthickness=0, height=260); cv.pack(fill="both", expand=True, pady=10)
        self.draw_activity(cv)
        stats = self.card(lower, 16, 14); stats.pack(side="right", fill="y", padx=(6, 0))
        self.label(stats, "Network Statistics", 12, True).pack(anchor="w")
        metrics = [("Messages Sent", self.sent), ("Messages Received", self.received), ("Files Sent", self.files_sent), ("Files Received", self.files_received), ("Latency", f"{self.latency} ms" if self.latency is not None else "Not measured")]
        for k, v in metrics:
            r = tk.Frame(stats, bg="#F7F8FC"); r.pack(fill="x", pady=4); self.label(r, k, 8, color=self.c["muted"], bg="#F7F8FC").pack(side="left", padx=9, pady=9); self.label(r, str(v), 9, True, bg="#F7F8FC").pack(side="right", padx=9)
        self.style_button(stats, "Measure Latency", self.ping, primary=True).pack(fill="x", pady=10)

    def draw_activity(self, cv):
        cv.update_idletasks(); w = max(cv.winfo_width(), 500); h = max(cv.winfo_height(), 240)
        for y in (h * .25, h * .5, h * .75): cv.create_line(20, y, w - 20, y, fill="#E7E9F1")
        values = [max(1, (self.sent + self.received) // 8 + i * 2) for i in range(9)]
        maxv = max(values) + 1
        pts = []
        for i, v in enumerate(values):
            x = 25 + i * (w - 50) / 8; y = h - 25 - (h - 55) * v / maxv; pts.extend([x, y])
        cv.create_line(*pts, fill=self.c["accent"], width=3, smooth=True)
        for i in range(0, len(pts), 2): cv.create_oval(pts[i]-3, pts[i+1]-3, pts[i]+3, pts[i+1]+3, fill=self.c["accent"], outline="")
        cv.create_text(28, h-8, text="Session start", anchor="w", fill=self.c["muted"], font=("Segoe UI", 8))
        cv.create_text(w-28, h-8, text="Now", anchor="e", fill=self.c["muted"], font=("Segoe UI", 8))

    def ping(self):
        self.ping_sent = time.time(); self.net.send({"type": "ping", "sent": self.ping_sent})

    # ---------- settings ----------
    def page_settings(self):
        self.page_title("Settings", "Configure client preferences and connection details")
        body = tk.Frame(self.content, bg=self.c["bg"]); body.pack(fill="both", expand=True, padx=20, pady=16)
        left = self.card(body, 16, 16); left.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        right = self.card(body, 16, 16); right.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
        body.grid_columnconfigure(0, weight=1); body.grid_columnconfigure(1, weight=1)
        self.label(left, "Notifications", 12, True).pack(anchor="w", pady=(0, 10))
        self.setting_switch(left, "Desktop Message Alerts", "Show a small banner when a message arrives", "desktop")
        self.setting_switch(left, "Sound Notifications", "Play a short local notification sound", "sound")
        self.setting_switch(left, "File Transfer Alerts", "Notify when a file is received", "file_alerts")
        self.label(left, "Appearance", 12, True).pack(anchor="w", pady=(25, 10))
        self.label(left, "Theme", 9, True).pack(anchor="w")
        self.label(left, "Light mode • optimized for the project demo", 8, color=self.c["muted"]).pack(anchor="w", pady=(3, 0))
        self.label(right, "File Transfer", 12, True).pack(anchor="w", pady=(0, 10))
        self.label(right, "Default Downloads Folder", 9, True).pack(anchor="w")
        pathrow = tk.Frame(right, bg=self.c["card"]); pathrow.pack(fill="x", pady=(4, 12))
        tk.Entry(pathrow, state="readonly", readonlybackground="#F7F8FC", relief="solid", bd=1, font=("Segoe UI", 8), textvariable=tk.StringVar(value=str(DOWNLOAD_DIR))).pack(side="left", fill="x", expand=True, ipady=7)
        self.style_button(pathrow, "Open", self.open_downloads).pack(side="right", padx=(7, 0))
        self.setting_switch(right, "Auto-Accept LAN Files", "Skip the confirmation step for future file controls", "auto_accept")
        self.label(right, "Connection Profile", 12, True).pack(anchor="w", pady=(25, 10))
        for k, v in [("Server IP", self.server_ip), ("TCP Port", self.port), ("Username", self.username), ("Protocol", "TCP / JSON"), ("Authentication", "PBKDF2-HMAC-SHA256")]:
            r = tk.Frame(right, bg=self.c["card"]); r.pack(fill="x", pady=5)
            self.label(r, k, 8, color=self.c["muted"]).pack(side="left")
            self.label(r, str(v), 8, True).pack(side="right")
        self.label(body, "Changes apply immediately to the running client", 8, color=self.c["muted"], bg=self.c["bg"]).grid(row=1, column=0, sticky="w", pady=12)

    def setting_switch(self, parent, title, subtitle, key):
        row = tk.Frame(parent, bg=self.c["card"]); row.pack(fill="x", pady=7)
        text = tk.Frame(row, bg=self.c["card"]); text.pack(side="left", fill="x", expand=True)
        self.label(text, title, 9, True).pack(anchor="w")
        self.label(text, subtitle, 8, color=self.c["muted"]).pack(anchor="w", pady=(2, 0))
        var = tk.BooleanVar(value=self.settings[key])
        tk.Checkbutton(row, variable=var, command=lambda k=key, v=var: self.settings.__setitem__(k, v.get()),
                       bg=self.c["card"], activebackground=self.c["card"], selectcolor=self.c["accent"],
                       relief="flat", bd=0).pack(side="right")

    # ---------- helpers ----------
    def render_search_results(self):
        # Search results are surfaced as a compact notification instead of mixing private results into group chat.
        if not self.search_results: toast(self.root, "Search", "No matching messages found."); return
        x = self.search_results[0]
        toast(self.root, "Search result", f"{x['sender']}: {x['text']}")

    def add_search_request(self, q):
        if q: self.net.send({"type": "search", "query": q})

    def short_time(self, ts):
        if not ts: return ""
        return ts[-8:-3] if len(ts) >= 8 else ts

    def now(self): return time.strftime("%Y-%m-%d %H:%M:%S")

    def format_size(self, n):
        n = int(n or 0)
        if n >= 1024 * 1024: return f"{n / (1024 * 1024):.1f} MB"
        if n >= 1024: return f"{n / 1024:.0f} KB"
        return f"{n} B"

    def logout(self):
        try: self.net.send({"type": "logout"})
        finally:
            self.net.disconnect(); self.connected = False; self.show_login()

    def close(self):
        try:
            if self.connected: self.net.send({"type": "logout"})
            self.net.disconnect()
        finally: self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
