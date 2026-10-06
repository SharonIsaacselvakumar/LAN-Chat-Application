import sqlite3
import threading
from pathlib import Path


class Database:
    def __init__(self, path):
        self.path = str(path)
        self.lock = threading.RLock()
        self.initialize()

    def connect(self):
        c = sqlite3.connect(self.path, timeout=10)
        c.row_factory = sqlite3.Row
        return c

    def initialize(self):
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.lock, self.connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS users(
                    username TEXT PRIMARY KEY,
                    salt TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender TEXT NOT NULL,
                    receiver TEXT NOT NULL,
                    text TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS files(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender TEXT NOT NULL,
                    receiver TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    timestamp TEXT NOT NULL
                );
                """
            )

    def user_exists(self, name):
        with self.lock, self.connect() as db:
            return db.execute(
                "SELECT 1 FROM users WHERE lower(username)=lower(?)", (name,)
            ).fetchone() is not None

    def create_user(self, name, salt, digest, created):
        with self.lock, self.connect() as db:
            db.execute(
                "INSERT INTO users VALUES(?,?,?,?)",
                (name, salt, digest, created),
            )

    def get_user(self, name):
        with self.lock, self.connect() as db:
            return db.execute(
                "SELECT * FROM users WHERE lower(username)=lower(?)", (name,)
            ).fetchone()

    def save_message(self, sender, receiver, text, timestamp):
        with self.lock, self.connect() as db:
            db.execute(
                "INSERT INTO messages(sender,receiver,text,timestamp) VALUES(?,?,?,?)",
                (sender, receiver, text, timestamp),
            )

    def history(self, username):
        with self.lock, self.connect() as db:
            rows = db.execute(
                """
                SELECT sender,receiver,text,timestamp FROM messages
                WHERE receiver='*' OR sender=? OR receiver=?
                ORDER BY id ASC LIMIT 500
                """,
                (username, username),
            ).fetchall()
            return [dict(r) for r in rows]

    def search(self, username, query):
        with self.lock, self.connect() as db:
            rows = db.execute(
                """
                SELECT sender,receiver,text,timestamp FROM messages
                WHERE (receiver='*' OR sender=? OR receiver=?)
                AND text LIKE ? ORDER BY id DESC LIMIT 100
                """,
                (username, username, f"%{query}%"),
            ).fetchall()
            return [dict(r) for r in rows]

    def save_file(self, sender, receiver, filename, size, timestamp):
        with self.lock, self.connect() as db:
            cur = db.execute(
                "INSERT INTO files(sender,receiver,filename,size,timestamp) VALUES(?,?,?,?,?)",
                (sender, receiver, filename, size, timestamp),
            )
            return cur.lastrowid

    def file_history(self, username):
        with self.lock, self.connect() as db:
            rows = db.execute(
                """
                SELECT id,sender,receiver,filename,size,timestamp
                FROM files
                WHERE sender=? OR receiver=? OR receiver='*'
                ORDER BY id DESC LIMIT 100
                """,
                (username, username),
            ).fetchall()
            return [dict(r) for r in rows]
