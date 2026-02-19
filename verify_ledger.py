import sqlite3
import json
import hashlib
import nacl.signing
import nacl.encoding
import os

# --- CONFIG ---
DB_PATH = "data/velonaut_main.sqlite"
KEY_PATH = "data/velonaut_signing.key"

def verify_ledger():
    print(f"--- Velonaut Public Verifier v0.1 ---")
    
    # 1. Key-Handling: Wir lesen den 'Salat' ein und extrahieren den Public Key
    if not os.path.exists(KEY_PATH):
        print(f"❌ Fehler: {KEY_PATH} nicht gefunden.")
        return
        
    with open(KEY_PATH, "rb") as f:
        signing_key = nacl.signing.SigningKey(f.read())
        verify_key = signing_key.verify_key
        public_key_hex = verify_key.encode(nacl.encoding.HexEncoder).decode()
        print(f"Verwende Public Key: {public_key_hex[:16]}...")

    # 2. Datenbank-Verbindung
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT * FROM ledger_entries ORDER BY seq ASC")
        rows = cursor.fetchall()
        expected_prev_hash = "0" * 64
        
        print(f"Prüfe {len(rows)} Blöcke...")
        
        for r in rows:
            # Body rekonstruieren (exakt wie im Ledger)
            body = {
                "seq": r[0], "institution_id": r[1], "block_type": r[2],
                "reporting_year": r[3], "prev_hash": r[4], "reg_hash": r[5],
                "payload": json.loads(r[6])
            }
            
            # Determinismus sicherstellen (Canonical JSON)
            canonical = json.dumps(body, sort_keys=True, separators=(',', ':')).encode('utf-8')
            
            # A. Hash-Check
            recalc_hash = hashlib.sha256(canonical).hexdigest()
            if recalc_hash != r[7]:
                print(f"❌ HASH ERROR bei SEQ {r[0]}")
                return

            # B. Signatur-Check
            try:
                verify_key.verify(hashlib.sha256(canonical).digest(), bytes.fromhex(r[8]))
            except:
                print(f"❌ SIGNATURE ERROR bei SEQ {r[0]}")
                return

            # C. Chain-Check
            if r[4] != expected_prev_hash:
                print(f"❌ CHAIN BREAK bei SEQ {r[0]}")
                return
            
            expected_prev_hash = r[7]
            print(f"  [OK] Block {r[0]} ({r[2]})")

        print(f"--- ✅ INTEGRITÄT GARANTIERT ---")

    except Exception as e:
        print(f"❌ SYSTEM FEHLER: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    verify_ledger()