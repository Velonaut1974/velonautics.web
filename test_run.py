import os
import time
import sqlite3
import nacl.signing
import nacl.encoding
# Hier sagen wir Python: Schau im Ordner 'core' in die Datei 'ledger'
from core.ledger import VelonautLedger

# Vorbereitung
TEST_DB = "test_integrity.sqlite"
if os.path.exists(TEST_DB):
    os.remove(TEST_DB)

# Keys erzeugen
signing_key = nacl.signing.SigningKey.generate()
verify_key_hex = signing_key.verify_key.encode(nacl.encoding.HexEncoder).decode()

def simple_signer(hash_bytes):
    return signing_key.sign(hash_bytes).signature

# Start
print("🚀 Starte Sicherheits-Check...")

try:
    # 1. Ledger initialisieren
    ledger = VelonautLedger("TEST_INST", TEST_DB, verify_key_hex)

    # 2. Genesis Block schreiben
    ledger.add_entry("GENESIS", {"status": "start"}, 2026, simple_signer)
    print("✅ Genesis Block erstellt.")

    # 3. Test Daten schreiben
    ledger.add_entry("EVENT", {"data": "Test-Eintrag"}, 2026, simple_signer)
    print("✅ Test-Daten geschrieben.")

    # 4. Integrität prüfen
    if ledger.verify_integrity():
        print("✅ INTEGRITÄT GEPRÜFT: Alles sicher!")

except Exception as e:
    print(f"❌ Fehler aufgetreten: {e}")