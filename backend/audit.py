import sqlite3
import hashlib
import json
from datetime import datetime

DB_NAME = "audit_trail.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS audit_log
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  timestamp TEXT,
                  event_id TEXT,
                  agent_action TEXT,
                  details TEXT,
                  prev_hash TEXT,
                  current_hash TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS received_webhooks
                 (event_id TEXT PRIMARY KEY, received_at TEXT, event_type TEXT)''')
    conn.commit()
    conn.close()

def log_event(event_id: str, agent_action: str, details: dict):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Get previous hash
    c.execute("SELECT current_hash FROM audit_log ORDER BY id DESC LIMIT 1")
    row = c.fetchone()
    prev_hash = row[0] if row else "GENESIS_HASH"
    
    timestamp = datetime.utcnow().isoformat()
    details_str = json.dumps(details)
    
    # Create current hash
    hash_string = f"{timestamp}{event_id}{agent_action}{details_str}{prev_hash}"
    current_hash = hashlib.sha256(hash_string.encode()).hexdigest()
    
    c.execute("INSERT INTO audit_log (timestamp, event_id, agent_action, details, prev_hash, current_hash) VALUES (?, ?, ?, ?, ?, ?)",
              (timestamp, event_id, agent_action, details_str, prev_hash, current_hash))
    conn.commit()
    conn.close()
    
    print(f"📝 Audit Logged: {agent_action} for {event_id} | Hash: {current_hash[:10]}...")

def get_audit_trail():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT timestamp, event_id, agent_action, details, current_hash FROM audit_log ORDER BY id DESC LIMIT 10")
    rows = c.fetchall()
    conn.close()
    return rows

def webhook_seen(event_id: str):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT 1 FROM received_webhooks WHERE event_id = ?", (event_id,))
    seen = c.fetchone() is not None
    conn.close()
    return seen

def record_webhook(event_id: str, event_type: str):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO received_webhooks (event_id, received_at, event_type) VALUES (?, ?, ?)", (event_id, datetime.utcnow().isoformat(), event_type))
    conn.commit()
    conn.close()
