import sqlite3
import hashlib
import json
import time
import nacl.signing
import nacl.encoding
import nacl.exceptions
from datetime import datetime, timezone

class VelonautLedger:
    def __init__(self, institution_id, db_path, public_key_hex):
        self.institution_id = institution_id
        self.db_path = db_path
        self.__conn = sqlite3.connect(
            db_path, 
            isolation_level=None, 
            check_same_thread=False 
        )
        # Fix: Wir merken uns den Genesis-Key als initialen Anker
        self.__initial_verify_key_hex = public_key_hex
        self.__initial_verify_key = nacl.signing.VerifyKey(public_key_hex, encoder=nacl.encoding.HexEncoder)
        self._init_db_settings()

    def _init_db_settings(self):
        c = self.__conn.cursor()
        c.execute("PRAGMA journal_mode = WAL")
        c.execute("PRAGMA synchronous = FULL")
        # Wichtig: Tabelle heißt ledger_entries
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
                timestamp_utc TEXT
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
        return json.dumps(data, sort_keys=True, separators=(',', ':')).encode('utf-8')

    def has_entries(self):
        cursor = self.__conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM ledger_entries")
        return cursor.fetchone()[0] > 0

    def get_genesis_public_key(self):
        """Fix: Ermöglicht der App den Abgleich beim Start."""
        cursor = self.__conn.cursor()
        cursor.execute("SELECT payload_json FROM ledger_entries WHERE seq = 1 AND block_type = 'GENESIS'")
        row = cursor.fetchone()
        if not row: return None
        return json.loads(row[0]).get("public_key")

    def get_all_entries(self):
        cursor = self.__conn.cursor()
        cursor.execute("""
            SELECT seq, institution_id, block_type, reporting_year, 
                   payload_json, block_hash, prev_hash, signature 
            FROM ledger_entries 
            ORDER BY seq DESC
        """)
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def add_entry(self, block_type, payload, reporting_year, signer_func):
        cursor = self.__conn.cursor()
        MAX_RETRIES = 15
        for attempt in range(MAX_RETRIES):
            try:
                cursor.execute("BEGIN IMMEDIATE")
                break 
            except sqlite3.OperationalError as e:
                if "locked" in str(e).lower() and attempt < MAX_RETRIES - 1:
                    time.sleep(0.02 * (attempt + 1))
                else: raise Exception(f"DATABASE_LOCKED: {e}")

        try:
            # Check ob Jahr bereits versiegelt
            cursor.execute("SELECT 1 FROM period_closures WHERE reporting_year = ?", (reporting_year,))
            if cursor.fetchone():
                raise Exception(f"BLOCK_REJECTED: Year {reporting_year} is closed.")

            cursor.execute("SELECT MAX(seq) FROM ledger_entries")
            last_seq = cursor.fetchone()[0]
            seq = (last_seq + 1) if last_seq is not None else 1

            prev_hash = "0" * 64 if seq == 1 else None
            if seq > 1:
                cursor.execute("SELECT block_hash FROM ledger_entries WHERE seq = ?", (last_seq,))
                prev_hash = cursor.fetchone()[0]

            reg_hash = hashlib.sha256(self._canonical_json(payload)).hexdigest() if block_type == 'EVENT' else "N/A"
            
            block_body = {
                "seq": seq, "institution_id": self.institution_id,
                "block_type": block_type, "reporting_year": reporting_year,
                "prev_hash": prev_hash, "reg_hash": reg_hash,
                "payload": payload
            }
            
            canonical = self._canonical_json(block_body)
            block_hash = hashlib.sha256(canonical).hexdigest()
            signature = signer_func(hashlib.sha256(canonical).digest()).hex()

            cursor.execute("""
                INSERT INTO ledger_entries 
                (seq, institution_id, block_type, reporting_year, prev_hash, reg_hash, payload_json, block_hash, signature, timestamp_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (seq, self.institution_id, block_type, reporting_year, prev_hash, reg_hash, 
                  json.dumps(payload), block_hash, signature, datetime.now(timezone.utc).isoformat()))
            
            cursor.execute("COMMIT")
            return block_hash
        except Exception as e:
            cursor.execute("ROLLBACK")
            raise e

    def seal_period(self, reporting_year, signer_func):
        """Institutional Grade Seal: Versiegelt ein Jahr revisionssicher."""
        cursor = self.__conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        try:
            # 1. Dublettenprüfung
            cursor.execute("SELECT 1 FROM period_closures WHERE reporting_year = ?", (reporting_year,))
            if cursor.fetchone(): 
                raise Exception("PERIOD_ALREADY_SEALED")

            # 2. Existenzprüfung (Keine leeren Jahre versiegeln)
            cursor.execute("SELECT COUNT(*) FROM ledger_entries WHERE reporting_year = ? AND block_type != 'CLOSURE'", (reporting_year,))
            if cursor.fetchone()[0] == 0:
                raise Exception("EMPTY_PERIOD_CANNOT_BE_SEALED")

            # 3. Integritäts-Check vorab
            self.verify_integrity()

            # 4. Master-Hash Bildung (Alle Blöcke außer Closures)
            cursor.execute("""
                SELECT block_hash FROM ledger_entries 
                WHERE reporting_year = ? AND block_type != 'CLOSURE' 
                ORDER BY seq ASC
            """, (reporting_year,))
            
            hashes = [row[0] for row in cursor.fetchall()]
            # Wir nutzen einen deterministischen JSON-Array-Hash für den Auditor
            master_material = json.dumps(hashes, separators=(",", ":")).encode("utf-8")
            master_hash = hashlib.sha256(master_material).hexdigest()

            # 5. Den Versiegelungs-Block selbst in die Kette schreiben
            closure_payload = {
                "reporting_year": reporting_year,
                "master_hash": master_hash,
                "sealed_at_utc": datetime.now(timezone.utc).isoformat(),
                "audit_note": "Institutional Final Seal"
            }
            self.add_entry("CLOSURE", closure_payload, reporting_year, signer_func)

            # 6. Abschluss in die Index-Tabelle schreiben
            cursor.execute("SELECT MAX(seq) FROM ledger_entries")
            latest_seq = cursor.fetchone()[0]
            
            cursor.execute("""
                INSERT INTO period_closures (reporting_year, institution_id, closure_block_seq, master_hash)
                VALUES (?, ?, ?, ?)
            """, (reporting_year, self.institution_id, latest_seq, master_hash))

            cursor.execute("COMMIT")
            return master_hash
        except Exception as e:
            cursor.execute("ROLLBACK")
            raise e

    def rotate_key(self, old_signer_func, new_public_key_hex):
        payload = {
            "msg": "KEY_ROTATION_PROTOCOL_ACTIVE",
            "new_public_key": new_public_key_hex,
            "ts_utc": datetime.now(timezone.utc).isoformat()
        }
        return self.add_entry("KEY_ROTATION", payload, 0, old_signer_func)

    def verify_integrity(self):
        cursor = self.__conn.cursor()
        cursor.execute("SELECT * FROM ledger_entries ORDER BY seq ASC")
        rows = cursor.fetchall()
        expected_prev_hash = "0" * 64
        
        current_v_key = self.__initial_verify_key
        
        for r in rows:
            body = {
                "seq": r[0], "institution_id": r[1], "block_type": r[2],
                "reporting_year": r[3], "prev_hash": r[4], "reg_hash": r[5],
                "payload": json.loads(r[6])
            }
            recalc_bytes = hashlib.sha256(self._canonical_json(body)).digest()
            if recalc_bytes.hex() != r[7]: raise Exception(f"HASH_MISMATCH at SEQ {r[0]}")
            
            current_v_key.verify(recalc_bytes, bytes.fromhex(r[8]))
            if r[4] != expected_prev_hash: raise Exception(f"CHAIN_BREAK at SEQ {r[0]}")
            
            if r[2] == 'KEY_ROTATION':
                new_key_hex = body['payload']['new_public_key']
                current_v_key = nacl.signing.VerifyKey(new_key_hex, encoder=nacl.encoding.HexEncoder)
                
            expected_prev_hash = r[7]
        return True