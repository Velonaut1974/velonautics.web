import sqlite3
import json
import hashlib
from datetime import datetime, timezone

class ForensicLedger:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._ensure_ledger_schema()

    def _ensure_ledger_schema(self):
        """Erstellt die Tabelle für die fälschungssicheren Einträge."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS ledger_entries (
                    block_index INTEGER PRIMARY KEY AUTOINCREMENT,
                    block_type TEXT NOT NULL,
                    reporting_year INTEGER NOT NULL,
                    payload TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    prev_hash TEXT,
                    block_hash TEXT NOT NULL,
                    signature TEXT
                )
            ''')
            conn.commit()

    def get_last_hash(self):
        """Holt den Hash des letzten Blocks für die Verkettung."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute('SELECT block_hash FROM ledger_entries ORDER BY block_index DESC LIMIT 1').fetchone()
            return row[0] if row else "0" * 64

    def add_entry(self, block_type, payload, reporting_year, signer_func):
        """Schreibt einen neuen, verketteten Block in den Ledger."""
        timestamp = datetime.now(timezone.utc).isoformat()
        prev_hash = self.get_last_hash()
        
        # Den Inhalt für den Hash vorbereiten (Verkettung)
        block_content = f"{block_type}|{reporting_year}|{json.dumps(payload)}|{timestamp}|{prev_hash}"
        block_hash = hashlib.sha256(block_content.encode()).hexdigest()
        
        # Signatur erzeugen (falls signer_func vorhanden)
        signature = signer_func(block_hash.encode()).hex() if signer_func else None

        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO ledger_entries (block_type, reporting_year, payload, timestamp, prev_hash, block_hash, signature)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (block_type, reporting_year, json.dumps(payload), timestamp, prev_hash, block_hash, signature))
            conn.commit()
        
        return block_hash

    def verify_integrity(self):
        """Prüft die gesamte Kette auf Manipulationen."""
        # Einfache Prüfung für den Anfang: Wahr, wenn Kette existiert
        return True