import sqlite3
import os

DB_FILE = "tradingbot.db"

def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS checked_messages (
                message_id INTEGER PRIMARY KEY,
                checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                direction INTEGER, -- 1 for long, 0 for short
                entry_price REAL,
                take_profit REAL, -- NEW
                stop_loss REAL,   -- NEW
                status TEXT DEFAULT 'PENDING',
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
    print("Database initialized successfully (SQLite).")

def is_message_checked(message_id):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM checked_messages WHERE message_id = ?", (message_id,))
        return cur.fetchone() is not None

def mark_message_checked(message_id):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("INSERT OR IGNORE INTO checked_messages (message_id) VALUES (?)", (message_id,))
        conn.commit()

def timeout_old_orders():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE orders
            SET status = 'UNEXPECTEDLY_CLOSED'
            WHERE status = 'PENDING'
            AND last_updated < datetime('now', '-10 minutes')
        """)
        conn.commit()

def process_extracted_data(extracted_data):
    symbol = extracted_data.get("symbol")
    direction = extracted_data.get("direction")
    entry_price = extracted_data.get("entry_price")
    take_profit = extracted_data.get("take_profit")
    stop_loss = extracted_data.get("stop_loss")

    # If the LLM returned absolutely nothing useful, skip
    if not symbol and direction is None and not entry_price and not take_profit and not stop_loss:
        return False

    with get_connection() as conn:
        cur = conn.cursor()

        # Find the most recent PENDING order within the last 10 minutes
        cur.execute("""
            SELECT * FROM orders
            WHERE status = 'PENDING' AND last_updated >= datetime('now', '-10 minutes')
            ORDER BY id DESC LIMIT 1
        """)
        pending_order = cur.fetchone()

        if pending_order:
            # Merge existing data with new data
            new_symbol = symbol if symbol else pending_order['symbol']
            new_direction = direction if direction is not None else pending_order['direction']
            new_entry_price = entry_price if entry_price else pending_order['entry_price']
            new_take_profit = take_profit if take_profit else pending_order['take_profit']
            new_stop_loss = stop_loss if stop_loss else pending_order['stop_loss']

            # REQUIRED FOR TRADING: We now need TP and SL too!
            if new_symbol and new_direction is not None and new_entry_price and new_take_profit and new_stop_loss:
                status = 'READY_TO_PLACE'
            else:
                status = 'PENDING'

            cur.execute("""
                UPDATE orders
                SET symbol = ?, direction = ?, entry_price = ?, take_profit = ?, stop_loss = ?, status = ?, last_updated = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (new_symbol, new_direction, new_entry_price, new_take_profit, new_stop_loss, status, pending_order['id']))
            print(f"Updated pending order #{pending_order['id']}. Status -> {status}")
        else:
            if symbol and direction is not None and entry_price and take_profit and stop_loss:
                status = 'READY_TO_PLACE'
            else:
                status = 'PENDING'

            cur.execute("""
                INSERT INTO orders (symbol, direction, entry_price, take_profit, stop_loss, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (symbol, direction, entry_price, take_profit, stop_loss, status))
            print(f"Created new order. Status -> {status}")

        conn.commit()
    return True

def get_ready_orders():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM orders WHERE status = 'READY_TO_PLACE'")
        return [dict(row) for row in cur.fetchall()]

def mark_order_placed(order_id):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE orders SET status = 'PLACED' WHERE id = ?", (order_id,))
        conn.commit()
