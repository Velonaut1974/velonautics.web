import sqlite3
import hashlib
import json
import nacl.signing
import nacl.encoding
import nacl.exceptions
from datetime import datetime, timezone

# --- PRODUCTION HARDENING ROADMAP (TODO) ---
# 🟡 KEY MANAGEMENT: Currently using session-based keys. Move to HSM/Vault for production.
# 🟡 KEY ROTATION: Implement 'KEY_ROTATION' block type to verify chain across key epochs.
# 🟡 CONCURRENCY: SQLite is file-locked. Migrate to PostgreSQL (Row-Level Locking) for multi-operator usage.

class VelonautLedger:
    def __init__(self, institution_id, db_path, public_key_hex):
        self.institution_id = institution_id
        self.db_path = db_path
        self.__conn = sqlite3.connect(
            db_path, 
            isolation_level=None, 
            check_same_thread=False 
        )
        # Genesis Key Anchor
        self.__initial_verify_key_hex = public_key_hex
        self.__initial_verify_key = nacl.signing.VerifyKey(public_key_hex, encoder=nacl.encoding.HexEncoder)
        self._init_db_settings()

    def _init_db_settings(self):
        c = self.__conn.cursor()
        c.execute("PRAGMA journal_mode = WAL")
        c.execute("PRAGMA synchronous = FULL")
        
        # Schema Definition
        c.execute("""
            CREATE TABLE IF NOT EXISTS ledger_entries (
                seq INTEGER PRIMARY KEY,
                institution_id TEXT NOT NULL,
                block_type TEXT NOT NULL,
                reporting_year INTEGER NOT NULL,
                prev_hash TEXT NOT NULL,
                reg_hash TEXT,
                payload_json TEXT NOT NULL,
                current_hash TEXT NOT NULL,
                signature TEXT NOT NULL,
                timestamp_utc TEXT NOT NULL
            )
        """)

    def _canonical_json(self, data_dict):
        """Ensures deterministic hashing by sorting keys."""
        return json.dumps(data_dict, sort_keys=True, separators=(',', ':')).encode('utf-8')

    def is_initialized(self):
        """Checks if Genesis block exists."""
        c = self.__conn.cursor()
        c.execute("SELECT COUNT(*) FROM ledger_entries")
        return c.fetchone()[0] > 0

    def initialize_genesis(self, signer_func):
        """
        CRITICAL: Mints the Genesis Block (Seq 1).
        Must be called explicitly with a valid signer.
        """
        if self.is_initialized():
            raise Exception("Ledger already initialized.")

        # Hardcoded Anchor
        prev_hash = "0" * 64
        genesis_payload = {
            "message": "VELONAUT INSTITUTIONAL GENESIS",
            "version": "RC1-v0.9",
            "protocol": "Ed25519-SHA256-SQLite",
            "meta": "System Root Anchor"
        }

        # 1. Prepare Body (Seq 1 for SQL compatibility)
        body = {
            "seq": 1,
            "institution_id": self.institution_id,
            "block_type": "GENESIS",
            "reporting_year": 0,
            "prev_hash": prev_hash,
            "reg_hash": None,
            "payload": genesis_payload
        }

        # 2. Hash
        block_hash = hashlib.sha256(self._canonical_json(body)).hexdigest()

        # 3. Sign
        signature = signer_func(block_hash.encode('utf-8'))
        signature_hex = signature.hex()
        ts = datetime.now(timezone.utc).isoformat()

        # 4. Commit
        cursor = self.__conn.cursor()
        cursor.execute("""
            INSERT INTO ledger_entries 
            (institution_id, block_type, reporting_year, prev_hash, reg_hash, payload_json, current_hash, signature, timestamp_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            self.institution_id, "GENESIS", 0, prev_hash, None,
            json.dumps(genesis_payload), block_hash, signature_hex, ts
        ))
        return True

    def add_entry(self, block_type, payload, reporting_year, signer_func=None):
        """
        Core Write Method. Calculates Hash, PrevHash and Signature.
        """
        if not self.is_initialized():
            raise Exception("Ledger not initialized. Genesis block missing.")

        cursor = self.__conn.cursor()
        
        # 1. Get Prev Hash
        cursor.execute("SELECT seq, current_hash FROM ledger_entries ORDER BY seq DESC LIMIT 1")
        last_row = cursor.fetchone()
        
        if not last_row:
            raise Exception("CRITICAL: Integrity Check Failed. No previous block found but Genesis check passed.")
            
        prev_hash = last_row[1]

        # 2. Prepare Body
        body_for_hash = {
            "seq": last_row[0] + 1,
            "institution_id": self.institution_id,
            "block_type": block_type,
            "reporting_year": reporting_year,
            "prev_hash": prev_hash,
            "reg_hash": None, # Null for internal/custody blocks
            "payload": payload
        }
        
        # 3. Hash
        block_hash = hashlib.sha256(self._canonical_json(body_for_hash)).hexdigest()
        
        # 4. Sign
        if not signer_func:
            raise ValueError("Cryptographic Signing Function Required")
        
        signature = signer_func(block_hash.encode('utf-8'))
        signature_hex = signature.hex()
        
        # 5. Commit
        ts = datetime.now(timezone.utc).isoformat()
        
        cursor.execute("""
            INSERT INTO ledger_entries 
            (institution_id, block_type, reporting_year, prev_hash, reg_hash, payload_json, current_hash, signature, timestamp_utc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            self.institution_id, block_type, reporting_year, prev_hash, None,
            json.dumps(payload), block_hash, signature_hex, ts
        ))
        return cursor.lastrowid
    
    def get_genesis_public_key(self):
        """Returns the hex string of the Genesis Verification Key."""
        return self.__initial_verify_key_hex

    # --- MODULE 10 INTERFACE ---
    def add_portfolio_event(self, block_type, payload_dict, signer_func):
        """
        BANK-GRADE WRITE OPS.
        Enforces signer_func and reporting_year=0.
        """
        if not signer_func:
            raise ValueError("SECURITY ALERT: signer_func is mandatory for Portfolio Events.")
            
        return self.add_entry(
            block_type=block_type,
            payload=payload_dict,
            reporting_year=0,
            signer_func=signer_func
        )

    # --- AUDIT CORE ---
    def verify_integrity(self):
        """
        Re-calculates the entire chain from Genesis to Now.
        Verifies Hashes, Links (PrevHash), and Signatures.
        """
        cursor = self.__conn.cursor()
        cursor.execute("SELECT * FROM ledger_entries ORDER BY seq ASC")
        rows = cursor.fetchall()
        
        if not rows:
            return True # Empty is valid state (pre-genesis)
            
        # Genesis Anchor Expectation
        expected_prev_hash = "0" * 64
        
        # In RC1, we assume the initial key is valid for the whole chain.
        # Production TODO: Logic to switch `current_v_key` on 'KEY_ROTATION' block type.
        current_v_key = self.__initial_verify_key 
        
        for r in rows:
            # Columns: 0:seq, 1:inst_id, 2:type, 3:year, 4:prev, 5:reg, 6:payload, 7:curr, 8:sig, 9:ts
            body = {
                "seq": r[0], 
                "institution_id": r[1], 
                "block_type": r[2],
                "reporting_year": r[3], 
                "prev_hash": r[4], 
                "reg_hash": r[5],
                "payload": json.loads(r[6])
            }
            
            # 1. Verify Hash
            recalc_hash = hashlib.sha256(self._canonical_json(body)).hexdigest()
            if recalc_hash != r[7]:
                raise Exception(f"HASH_MISMATCH at SEQ {r[0]}")
            
            # 2. Verify Chain Link
            if r[4] != expected_prev_hash:
                raise Exception(f"CHAIN_BREAK at SEQ {r[0]}: PrevHash mismatch. Expected {expected_prev_hash[:8]}... Got {r[4][:8]}...")
            
            # 3. Verify Signature
            try:
                current_v_key.verify(r[7].encode('utf-8'), bytes.fromhex(r[8]))
            except nacl.exceptions.BadSignatureError:
                raise Exception(f"INVALID_SIGNATURE at SEQ {r[0]}")
            
            # Advance
            expected_prev_hash = r[7]
            
        return True