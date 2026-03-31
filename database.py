import sqlite3
import os
from datetime import date

DB_PATH = os.environ.get("DB_PATH", "lunch_bot.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE TABLE IF NOT EXISTS menu (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            item_name TEXT NOT NULL,
            price INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            username TEXT,
            full_name TEXT,
            menu_item_id INTEGER,
            item_name TEXT NOT NULL,
            price INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'ordered',
            -- status: ordered | pending_confirm | confirmed
            receipt_file_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        conn.commit()


# ── Settings ──────────────────────────────────────────────────────────────────

def get_setting(key: str) -> str | None:
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None


def set_setting(key: str, value: str):
    with get_conn() as conn:
        conn.execute("INSERT OR REPLACE INTO settings(key, value) VALUES(?,?)", (key, value))
        conn.commit()


# ── Admins ─────────────────────────────────────────────────────────────────────

def is_admin(user_id: int) -> bool:
    # First admin ever — stored in settings as FIRST_ADMIN_ID env var
    first_admin = os.environ.get("ADMIN_ID")
    if first_admin and str(user_id) == str(first_admin):
        return True
    with get_conn() as conn:
        row = conn.execute("SELECT 1 FROM admins WHERE user_id=?", (user_id,)).fetchone()
        return row is not None


def add_admin(user_id: int, username: str = None):
    with get_conn() as conn:
        conn.execute("INSERT OR IGNORE INTO admins(user_id, username) VALUES(?,?)", (user_id, username))
        conn.commit()


# ── Menu ───────────────────────────────────────────────────────────────────────

def set_menu(items: list[dict], day: str = None):
    """items = [{'name': str, 'price': int}]"""
    day = day or date.today().isoformat()
    with get_conn() as conn:
        conn.execute("DELETE FROM menu WHERE date=?", (day,))
        conn.executemany(
            "INSERT INTO menu(date, item_name, price) VALUES(?,?,?)",
            [(day, i["name"], i["price"]) for i in items]
        )
        conn.commit()


def get_menu(day: str = None) -> list:
    day = day or date.today().isoformat()
    with get_conn() as conn:
        return conn.execute("SELECT * FROM menu WHERE date=? ORDER BY id", (day,)).fetchall()


# ── Orders ─────────────────────────────────────────────────────────────────────

def create_order(user_id: int, username: str, full_name: str,
                 menu_item_id: int, item_name: str, price: int, day: str = None) -> int:
    day = day or date.today().isoformat()
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO orders(date, user_id, username, full_name, menu_item_id, item_name, price, status)
               VALUES(?,?,?,?,?,?,?,'ordered')""",
            (day, user_id, username, full_name, menu_item_id, item_name, price)
        )
        conn.commit()
        return cur.lastrowid


def get_user_order_today(user_id: int, day: str = None):
    day = day or date.today().isoformat()
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM orders WHERE date=? AND user_id=? ORDER BY id DESC LIMIT 1",
            (day, user_id)
        ).fetchone()


def update_order_status(order_id: int, status: str, receipt_file_id: str = None):
    with get_conn() as conn:
        if receipt_file_id:
            conn.execute(
                "UPDATE orders SET status=?, receipt_file_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (status, receipt_file_id, order_id)
            )
        else:
            conn.execute(
                "UPDATE orders SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (status, order_id)
            )
        conn.commit()


def get_orders_today(day: str = None) -> list:
    day = day or date.today().isoformat()
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM orders WHERE date=? ORDER BY status, full_name",
            (day,)
        ).fetchall()


def get_unpaid_orders_today(day: str = None) -> list:
    day = day or date.today().isoformat()
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM orders WHERE date=? AND status='ordered'",
            (day,)
        ).fetchall()


def get_pending_orders_today(day: str = None) -> list:
    day = day or date.today().isoformat()
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM orders WHERE date=? AND status='pending_confirm'",
            (day,)
        ).fetchall()


def get_order_by_id(order_id: int):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
