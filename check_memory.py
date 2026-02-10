import sqlite3
import os

data_dir = r"C:\Projects\TheDavidProject\data"

print("=" * 50)
print("DEVA MEMORY CHECK")
print("=" * 50)

# 1. DevaMemory
print("\n--- deva_memory.db ---")
db = sqlite3.connect(os.path.join(data_dir, "deva_memory.db"))
db.row_factory = sqlite3.Row

print("\nUser Profile:")
for row in db.execute("SELECT * FROM user_profile"):
    print(f"  {row['key']}: {row['value']}")

print("\nConversations:")
rows = db.execute("SELECT * FROM conversations ORDER BY timestamp DESC LIMIT 10").fetchall()
if rows:
    for row in rows:
        cols = row.keys()
        print(f"  {dict(row)}")
else:
    print("  (none)")

print("\nKnowledge:")
# Check columns first
cols = [c[1] for c in db.execute("PRAGMA table_info(knowledge)").fetchall()]
print(f"  Columns: {cols}")
rows = db.execute("SELECT * FROM knowledge LIMIT 10").fetchall()
if rows:
    for row in rows:
        print(f"  {dict(row)}")
else:
    print("  (none)")

# Check all tables
print("\nAll tables:")
for t in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
    count = db.execute(f"SELECT COUNT(*) FROM [{t[0]}]").fetchone()[0]
    print(f"  {t[0]}: {count} rows")
db.close()

# 2. GameMemory
print("\n--- deva_games.db ---")
db = sqlite3.connect(os.path.join(data_dir, "deva_games.db"))
db.row_factory = sqlite3.Row

print("\nRegistered Games:")
rows = db.execute("SELECT * FROM games").fetchall()
if rows:
    for row in rows:
        print(f"  {dict(row)}")
else:
    print("  (none)")

# Check all tables
print("\nAll tables:")
for t in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
    count = db.execute(f"SELECT COUNT(*) FROM [{t[0]}]").fetchone()[0]
    print(f"  {t[0]}: {count} rows")
db.close()

# 3. GroupMemory
print("\n--- deva_group_knowledge.db ---")
db = sqlite3.connect(os.path.join(data_dir, "deva_group_knowledge.db"))
db.row_factory = sqlite3.Row

print("\nSolutions:")
rows = db.execute("SELECT * FROM solutions LIMIT 5").fetchall()
if rows:
    for row in rows:
        print(f"  {dict(row)}")
else:
    print("  (none)")

print("\nAll tables:")
for t in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
    count = db.execute(f"SELECT COUNT(*) FROM [{t[0]}]").fetchone()[0]
    print(f"  {t[0]}: {count} rows")
db.close()

print("\n" + "=" * 50)
