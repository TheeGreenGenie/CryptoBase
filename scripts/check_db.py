import sqlite3
conn = sqlite3.connect("instance/defi_mvp.db")
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print("Tables:", [t[0] for t in tables])
cols = conn.execute("PRAGMA table_info(agent_suggestions)").fetchall()
print("agent_suggestions columns:", [c[1] for c in cols])
