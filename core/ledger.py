import sqlite3
import hashlib
import json
import time
import nacl.signing
import nacl.exceptions
from datetime import datetime

class VelonautLedger:
    def __init__(self, institution_id, db_path, public_key_hex):
        self.institution_id = institution_id
        # Auditor Fix: Thread-Isolation & Manuelle Transaktionskontrolle
        self.__conn = sqlite3.connect(
            db_path, 
            isolation_level=None, 
            check_same_thread=False 
        )
        self.__verify_key = nacl.signing.VerifyKey(public_key_hex, encoder=nacl.encoding.HexEncoder)
        self._init_db_settings()

    def _init_db_settings(self):
        c = self.__conn.cursor()
        c.execute("PRAGMA journal_mode = WAL")
        c.execute("PRAGMA synchronous = FULL")
        c.execute("PRAGMA locking_mode = NORMAL")
        c.execute("PRAGMA foreign_keys = ON")
        
        # Erstellt die Tabellen, falls sie noch nicht existieren
        c.execute("""
            CREATE TABLE IF NOT EXISTS ledger_entries (
                seq INTEGER PRIMARY KEY,
                institution_id TEXT NOT NULL,
                block_type TEXT NOT NULL,
                reporting_year INTEGER NOT NULL,
                prev_hash TEXT NOT NULL,
                reg_hash TEXT,
                payload_json TEXT NOT NULL,
                block_hash TEXT NOT NULL,
                signature TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS period_closures (
                reporting_year INTEGER PRIMARY KEY,
                institution_id TEXT NOT NULL,
                closure_block_seq INTEGER UNIQUE,
                master_hash TEXT NOT NULL,
                closed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.__conn.commit()
    def _canonical_json(self, data):
        """Garantierter Determinismus für kryptografische Hashes."""
        return json.dumps(data, sort_keys=True, separators=(',', ':')).encode('utf-8')

    def add_entry(self, block_type, payload, reporting_year, signer_func):
        cursor = self.__conn.cursor()
        
        # 1. Härtung: Retry-Mechanismus für Concurrency
        MAX_RETRIES = 15
        for attempt in range(MAX_RETRIES):
            try:
                cursor.execute("BEGIN IMMEDIATE")
                break 
            except sqlite3.OperationalError as e:
                if "locked" in str(e).lower() and attempt < MAX_RETRIES - 1:
                    time.sleep(0.02 * (attempt + 1)) # Exponentieller/Linearer Backoff
                else:
                    raise Exception(f"DATABASE_LOCKED: Timeout after {MAX_RETRIES} attempts. {e}")

        try:
            # 2. Programmatischer Closure-Check (Innerhalb der Transaktion!)
            cursor.execute("SELECT 1 FROM period_closures WHERE reporting_year = ?", (reporting_year,))
            if cursor.fetchone():
                raise Exception(f"BLOCK_REJECTED: Reporting year {reporting_year} is closed.")

            # 3. Sequenz-Ermittlung (Manuell für Integrität)
            cursor.execute("SELECT MAX(seq) FROM ledger_entries")
            last_seq = cursor.fetchone()[0]
            seq = (last_seq + 1) if last_seq is not None else 1

            # 4. Prev_Hash & Genesis-Zwang
            if seq == 1:
                prev_hash = "0" * 64
                if block_type != 'GENESIS':
                    raise Exception("GENESIS_MISSING: First block must be GENESIS.")
            else:
                cursor.execute("SELECT block_hash FROM ledger_entries WHERE seq = ?", (last_seq,))
                prev_hash = cursor.fetchone()[0]

            # 5. Block-Körper Konstruktion
            reg_hash = hashlib.sha256(self._canonical_json(payload)).hexdigest() if block_type == 'EVENT' else None
            payload_json_str = self._canonical_json(payload).decode('utf-8')
            
            block_body = {
                "seq": seq,
                "institution_id": self.institution_id,
                "block_type": block_type,
                "reporting_year": reporting_year,
                "prev_hash": prev_hash,
                "reg_hash": reg_hash,
                "payload": json.loads(payload_json_str)
            }
            
            # 6. Kryptografie (Signer Injection)
            block_hash_bytes = hashlib.sha256(self._canonical_json(block_body)).digest()
            signature_bytes = signer_func(block_hash_bytes)

            # 7. Persistierung
            cursor.execute("""
                INSERT INTO ledger_entries 
                (seq, institution_id, block_type, reporting_year, prev_hash, reg_hash, payload_json, block_hash, signature)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (seq, self.institution_id, block_type, reporting_year, prev_hash, reg_hash, 
                  payload_json_str, block_hash_bytes.hex(), signature_bytes.hex()))
            
            cursor.execute("COMMIT")
            return block_hash_bytes.hex()
        except Exception as e:
            cursor.execute("ROLLBACK")
            raise e

    def verify_integrity(self):
        """Zero-Trust Replay Engine: Überprüft lückenlos die gesamte Kette."""
        cursor = self.__conn.cursor()
        cursor.execute("SELECT * FROM ledger_entries ORDER BY seq ASC")
        rows = cursor.fetchall()
        
        expected_prev_hash = "0" * 64
        for r in rows:
            # Body rekonstruieren
            body = {
                "seq": r[0], "institution_id": r[1], "block_type": r[2],
                "reporting_year": r[3], "prev_hash": r[4], "reg_hash": r[5],
                "payload": json.loads(r[6])
            }
            
            # Hash-Check
            recalc_bytes = hashlib.sha256(self._canonical_json(body)).digest()
            if recalc_bytes.hex() != r[7]:
                raise Exception(f"INTEGRITY_ERR: Hash mismatch at SEQ {r[0]}")

            # Signatur-Check
            sig_bytes = bytes.fromhex(r[8])
            if len(sig_bytes) != 64:
                raise Exception(f"INTEGRITY_ERR: Invalid signature length at SEQ {r[0]}")

            try:
                self.__verify_key.verify(recalc_bytes, sig_bytes)
            except nacl.exceptions.BadSignatureError:
                raise Exception(f"INTEGRITY_ERR: Signature invalid at SEQ {r[0]}")

            # Ketten-Check
            if r[4] != expected_prev_hash:
                raise Exception(f"INTEGRITY_ERR: Chain broken at SEQ {r[0]}")
            
            expected_prev_hash = r[7]
        return True