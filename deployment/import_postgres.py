"""Optional one-time migration into EMPTY PostgreSQL database.
Requires: pip install 'psycopg[binary]'
Set DATABASE_URL with SSL enabled as required by your provider.
Run postgres_schema.sql first. Takes a JSON file exported by export_sqlite.py.
"""
import json,os,sys
if len(sys.argv)!=2:raise SystemExit('Usage: python deployment/import_postgres.py private-export.json')
url=os.getenv('DATABASE_URL')
if not url:raise SystemExit('Set DATABASE_URL first')
import psycopg
from psycopg import sql
snapshot=json.load(open(sys.argv[1],encoding='utf-8'))
order=['users','events','crews','crew_members','join_requests','tasks','transfers','activity','messages','travel_plans','travel_requests']
with psycopg.connect(url) as conn:
    with conn.cursor() as cur:
        for table in order:
            if cur.execute(sql.SQL('SELECT COUNT(*) FROM {}').format(sql.Identifier(table))).fetchone()[0]:
                raise SystemExit('STOP: PostgreSQL table '+table+' is not empty. This script is create-only.')
        for table in order:
            rows=snapshot.get(table,[])
            if not rows:continue
            cols=list(rows[0]); stmt=sql.SQL('INSERT INTO {} ({}) VALUES ({})').format(sql.Identifier(table),sql.SQL(',').join(map(sql.Identifier,cols)),sql.SQL(',').join(sql.Placeholder() for _ in cols))
            for row in rows:cur.execute(stmt,[row.get(col) for col in cols])
            if 'id' in cols:
                cur.execute('SELECT pg_get_serial_sequence(%s,%s)',(table,'id'))
                seq=cur.fetchone()[0]
                if seq:cur.execute('SELECT setval(%s, %s, true)',(seq,max(int(r['id']) for r in rows)))
print('Snapshot imported into PostgreSQL. This version of the app still uses SQLite at runtime; update its DB adapter before switching production traffic.')
