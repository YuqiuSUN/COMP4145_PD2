from contextlib import closing
import os
import sqlite3
import pandas as pd
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stockapp.db")

def get_conn():
    return sqlite3.connect(DB_PATH)

def init_db():
    """Call once at startup to create tables if they do not already exist."""
    with closing(get_conn()) as conn:
        with conn:
            c = conn.cursor()
            c.execute('''
                CREATE TABLE IF NOT EXISTS watchlist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL UNIQUE,
                    added_at TEXT NOT NULL
                )
            ''')
            c.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "idx_watchlist_symbol ON watchlist(symbol)"
            )
            c.execute('''
                CREATE TABLE IF NOT EXISTS query_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    queried_at TEXT NOT NULL,
                    note TEXT
                )
            ''')

def add_to_watchlist(symbol):
    symbol = symbol.strip().upper()
    with closing(get_conn()) as conn:
        try:
            with conn:
                conn.execute(
                    "INSERT INTO watchlist (symbol, added_at) VALUES (?, ?)",
                    (symbol, datetime.now().isoformat()),
                )
        except sqlite3.IntegrityError:
            return False
        return True

def remove_from_watchlist(symbol):
    symbol = symbol.strip().upper()
    with closing(get_conn()) as conn:
        with conn:
            conn.execute("DELETE FROM watchlist WHERE symbol = ?", (symbol,))

def get_watchlist():
    with closing(get_conn()) as conn:
        with conn:
            return pd.read_sql(
                "SELECT * FROM watchlist ORDER BY added_at DESC", conn
            )

def add_query_history(symbol, note=""):
    symbol = symbol.strip().upper()
    with closing(get_conn()) as conn:
        with conn:
            conn.execute(
                "INSERT INTO query_history (symbol, queried_at, note) VALUES (?, ?, ?)",
                (symbol, datetime.now().isoformat(), note),
            )

def get_query_history(limit=20):
    with closing(get_conn()) as conn:
        with conn:
            return pd.read_sql(
                f"SELECT * FROM query_history ORDER BY queried_at DESC LIMIT {int(limit)}",
                conn,
            )
