import re
import psycopg
from psycopg.rows import dict_row

class HybridRow(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)

class PGResult:
    def __init__(self, cursor, lastrowid=None):
        self.cursor = cursor
        self.lastrowid = lastrowid

    def fetchone(self):
        row = self.cursor.fetchone()
        return HybridRow(row) if row is not None else None

    def fetchall(self):
        return [HybridRow(r) for r in self.cursor.fetchall()]

    def __iter__(self):
        for row in self.cursor:
            yield HybridRow(row)

class PGConnection:
    def __init__(self, url):
        self.conn = psycopg.connect(
            url, row_factory=dict_row, connect_timeout=15
        )

    def execute(self, query, params=()):
        statement = query.strip().replace('?', '%s')

        if re.match(
            r'^INSERT\s+OR\s+IGNORE\s+INTO\s+crew_members\b',
            statement, re.I
        ):
            statement = re.sub(
                r'^INSERT\s+OR\s+IGNORE',
                'INSERT',
                statement,
                count=1,
                flags=re.I
            )
            statement += ' ON CONFLICT DO NOTHING'

        statement = statement.replace(
            '(%s IS NULL OR p.event_id=%s)',
            '(%s::bigint IS NULL OR p.event_id=%s)'
        )

        inserted = re.match(
            r'^INSERT\s+INTO\s+(users|crews|tasks|transfers)\s*\(',
            statement, re.I
        )

        if inserted and 'RETURNING' not in statement.upper():
            statement += ' RETURNING id'

        cursor = self.conn.execute(statement, params)
        lastrowid = cursor.fetchone()['id'] if inserted else None

        return PGResult(cursor, lastrowid)

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        self.conn.close()
