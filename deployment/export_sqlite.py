"""Export a private SQLite snapshot to JSON for reviewed database migration.
Contains password hashes and potentially sensitive user data. Never commit output to Git.
Usage: python deployment/export_sqlite.py backend/crewup.db PRIVATE_PATH.json
"""
import json, sqlite3, sys
from pathlib import Path
if len(sys.argv)!=3:raise SystemExit('Usage: python deployment/export_sqlite.py database.sqlite private-export.json')
src=Path(sys.argv[1]);out=Path(sys.argv[2]);
if not src.is_file():raise SystemExit('Database does not exist')
if out.exists():raise SystemExit('Refusing to overwrite existing export')
tables=['users','events','crews','crew_members','join_requests','tasks','transfers','activity','messages','travel_plans','travel_requests']
with sqlite3.connect(str(src)) as c:
    c.row_factory=sqlite3.Row
    snapshot={t:[dict(r) for r in c.execute('SELECT * FROM '+t)] for t in tables}
out.write_text(json.dumps(snapshot,indent=2),encoding='utf-8')
try:out.chmod(0o600)
except OSError:pass
print(f'Private snapshot created at {out}. DO NOT share or commit this file.')
