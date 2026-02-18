import sqlite3
import json
from datetime import datetime, timezone
from decimal import Decimal

# --- MODULE 10: INSTITUTIONAL CUSTODY CORE ---
# Status: RC1 (Integration Candidate)
# Architecture: Physical DB Separation (Assets vs. Governance)
# Security: Strict Replay, Core Validation, Payload Whitelisting

class PortfolioCustodian:
    def __init__(self, governance_db_path, asset_db_path, ledger_instance):
        self.gov_db = governance_db_path
        self.asset_db = asset_db_path
        self.ledger = ledger_instance
        
        self._init_cache_storage()

    def _init_cache_storage(self):
        """Creates the disposable cache table in the Governance DB."""
        conn = sqlite3.connect(self.gov_db)
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS portfolio_cache") 
        cursor.execute("""
            CREATE TABLE portfolio_cache (
                asset_root_hash TEXT PRIMARY KEY, 
                volume_mt TEXT,
                current_status TEXT, 
                owner_entity TEXT,
                last_block_type TEXT,
                last_update_ts_utc TEXT
            )
        """)
        conn.commit()
        conn.close()

    def get_current_gov_seq(self):
        """Helper for Optimistic Locking."""
        conn = sqlite3.connect(self.gov_db)
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(seq) FROM ledger_entries")
        row = cursor.fetchone()
        conn.close()
        return row[0] if row and row[0] is not None else 0

    def get_minting_candidates(self):
        """SCANS ASSET DB for valid CERTIFICATION blocks."""
        # 1. Check existing custody
        conn_gov = sqlite3.connect(self.gov_db)
        cursor_gov = conn_gov.cursor()
        cursor_gov.execute("SELECT asset_root_hash FROM portfolio_cache")
        custody_hashes = {row[0] for row in cursor_gov.fetchall()}
        conn_gov.close()

        # 2. Scan Asset Source
        candidates = []
        conn_asset = sqlite3.connect(self.asset_db)
        cursor_asset = conn_asset.cursor()
        
        try:
            cursor_asset.execute("""
                SELECT block_hash, payload, timestamp 
    FROM ledger_entries 
    WHERE block_type = 'CERTIFICATION'
            """)
            rows = cursor_asset.fetchall()
            for b_hash, payload_raw, ts in rows:
                if b_hash in custody_hashes: continue
                try:
                    payload = json.loads(payload_raw)
                    bal = payload.get("metrics", {}).get("balance_t")
                    if bal and Decimal(str(bal)) > 0:
                        candidates.append({"hash": b_hash, "volume": str(bal), "created_at": ts})
                except: continue 
        except: pass
        conn_asset.close()
        return candidates

    def rebuild_state_from_ledger(self):
        """STRICT REPLAY ENGINE. No Soft Forks."""
        conn = sqlite3.connect(self.gov_db)
        cursor = conn.cursor()
        cursor.execute("SELECT seq, block_type, payload_json, current_hash, timestamp_utc FROM ledger_entries ORDER BY seq ASC")
        all_blocks = cursor.fetchall()
        
        assets = {} 

        for seq, b_type, payload_raw, b_hash, ts_utc in all_blocks:
            if not b_type.startswith("PORTFOLIO_"): continue

            try:
                payload = json.loads(payload_raw)
                root_hash = payload.get("asset_root_hash")
                if not root_hash: raise Exception(f"Missing asset_root_hash at SEQ {seq}")

                if b_type == "PORTFOLIO_CREATE":
                    if root_hash in assets: raise Exception(f"DUPLICATE MINTING at SEQ {seq}")
                    if Decimal(payload.get("volume_t", "0")) <= 0: raise Exception(f"INVALID VOLUME at SEQ {seq}")
                    assets[root_hash] = {
                        "volume": payload.get("volume_t"), "status": "OPEN", 
                        "owner": "OWNER", "last_type": b_type, "ts": ts_utc
                    }

                elif root_hash in assets:
                    curr = assets[root_hash]["status"]
                    if b_type == "PORTFOLIO_RESERVE":
                        if curr != "OPEN": raise Exception(f"INVALID TRANSITION (RESERVE from {curr}) at SEQ {seq}")
                        assets[root_hash]["status"] = "RESERVED"
                    elif b_type == "PORTFOLIO_RELEASE":
                        if curr != "RESERVED": raise Exception(f"INVALID TRANSITION (RELEASE from {curr}) at SEQ {seq}")
                        assets[root_hash]["status"] = "OPEN"
                    elif b_type == "PORTFOLIO_TRANSFER":
                        if curr not in ["OPEN", "RESERVED"]: raise Exception(f"INVALID TRANSITION (TRANSFER from {curr}) at SEQ {seq}")
                        assets[root_hash]["status"] = "TRANSFERRED"
                    assets[root_hash]["last_type"] = b_type
                    assets[root_hash]["ts"] = ts_utc
                else:
                    raise Exception(f"UNKNOWN ASSET REFERENCE at SEQ {seq}")

            except Exception as e:
                raise Exception(f"LEDGER CORRUPTION at SEQ {seq}: {str(e)}")

        cursor.execute("DELETE FROM portfolio_cache")
        for h, d in assets.items():
            cursor.execute("INSERT INTO portfolio_cache VALUES (?, ?, ?, ?, ?, ?)", 
                           (h, d["volume"], d["status"], d["owner"], d["last_type"], d["ts"]))
        conn.commit()
        conn.close()
        return len(assets)

    def validate_and_write_block(self, block_type, payload_input, signer_func):
        """ATOMIC WRITE."""
        self.rebuild_state_from_ledger() # Force Replay
        
        target_hash = payload_input.get("asset_root_hash")
        conn = sqlite3.connect(self.gov_db)
        cursor = conn.cursor()
        cursor.execute("SELECT current_status FROM portfolio_cache WHERE asset_root_hash = ?", (target_hash,))
        res = cursor.fetchone()
        current_status = res[0] if res else None
        conn.close()
        
        final_payload = {}
        ts_now = datetime.now(timezone.utc).isoformat()

        if block_type == "PORTFOLIO_CREATE":
            if current_status: raise Exception("Asset already exists.")
            # Cross-DB Check
            conn_asset = sqlite3.connect(self.asset_db)
            cursor_asset = conn_asset.cursor()
            cursor_asset.execute("SELECT payload FROM ledger_entries WHERE block_hash = ? AND block_type = 'CERTIFICATION'", (target_hash,))
            row = cursor_asset.fetchone()
            conn_asset.close()
            if not row: raise Exception("Source Certificate invalid/missing.")
            
            bal = Decimal(str(json.loads(row[0]).get("metrics", {}).get("balance_t", "0")))
            if bal <= 0: raise Exception("Source Balance non-positive.")
            
            final_payload = {"asset_root_hash": target_hash, "volume_t": str(bal), "origin_block_hash": target_hash, "ts_utc": ts_now}

        elif block_type == "PORTFOLIO_RESERVE":
            if current_status != "OPEN": raise Exception(f"Cannot RESERVE from {current_status}")
            final_payload = {"asset_root_hash": target_hash, "previous_status": "OPEN", "new_status": "RESERVED", "reason": payload_input.get("reason"), "ts_utc": ts_now}

        elif block_type == "PORTFOLIO_RELEASE":
            if current_status != "RESERVED": raise Exception(f"Cannot RELEASE from {current_status}")
            final_payload = {"asset_root_hash": target_hash, "previous_status": "RESERVED", "new_status": "OPEN", "reason": payload_input.get("reason"), "ts_utc": ts_now}
        
        elif block_type == "PORTFOLIO_TRANSFER":
             if current_status not in ["OPEN", "RESERVED"]: raise Exception("Invalid Transfer State")
             final_payload = {"asset_root_hash": target_hash, "previous_status": current_status, "new_status": "TRANSFERRED", "counterparty_id": payload_input.get("counterparty_id"), "ts_utc": ts_now}

        self.ledger.add_portfolio_event(block_type, final_payload, signer_func)
        
        # Post-Write Check
        try: self.rebuild_state_from_ledger()
        except Exception as e: raise Exception(f"CRITICAL: State Violation after write: {e}")
        return True

    def get_view_data(self):
        conn = sqlite3.connect(self.gov_db)
        cur = conn.cursor()
        cur.execute("SELECT * FROM portfolio_cache")
        rows = cur.fetchall()
        conn.close()
        return rows