import sqlite3
import pandas as pd
from datetime import datetime

DB_PATH = "stockapp.db"

def get_conn():
    return sqlite3.connect(DB_PATH)

def init_db():
    """启动时调用一次，建表（如果还没建）"""
    conn = get_conn()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            added_at TEXT NOT NULL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS query_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            queried_at TEXT NOT NULL,
            note TEXT
        )
    ''')
    conn.commit()
    conn.close()

def add_to_watchlist(symbol):
    symbol = symbol.strip().upper()
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO watchlist (symbol, added_at) VALUES (?, ?)",
              (symbol, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def remove_from_watchlist(symbol):
    symbol = symbol.strip().upper()
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM watchlist WHERE symbol = ?", (symbol,))
    conn.commit()
    conn.close()

def get_watchlist():
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM watchlist ORDER BY added_at DESC", conn)
    conn.close()
    return df

def add_query_history(symbol, note=""):
    symbol = symbol.strip().upper()
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO query_history (symbol, queried_at, note) VALUES (?, ?, ?)",
              (symbol, datetime.now().isoformat(), note))
    conn.commit()
    conn.close()

def get_query_history(limit=20):
    conn = get_conn()
    df = pd.read_sql(
        f"SELECT * FROM query_history ORDER BY queried_at DESC LIMIT {int(limit)}",
        conn
    )
    conn.close()
    return df
