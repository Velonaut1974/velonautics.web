import sqlite3
import os
from core.ledger import VelonautLedger
import nacl.signing
import nacl.encoding

# Wir nutzen die Datei aus dem erfolgreichen Test vorhin
DB_FILE = "test_integrity.sqlite"

# 1. Wir brauchen einen gültigen Schlüssel für den Test-Start
signing_key = nacl.signing.SigningKey.generate()
verify_key_hex = signing_key.verify_key.encode(nacl.encoding.HexEncoder).decode()
def simple_signer(h): return signing_key.sign(h).signature

print("🏗️ Vorbereitung: Erstelle saubere Test-Daten...")
if os.path.exists(DB_FILE): os.remove(DB_FILE)
ledger = VelonautLedger("HACK_TEST", DB_FILE, verify_key_hex)
ledger.add_entry("GENESIS", {"msg": "Original"}, 2026, simple_signer)
ledger.add_entry("EVENT", {"data": "Sichere Daten"}, 2026, simple_signer)

print("🕵️ Manipulation: Wir ändern jetzt heimlich die Datenbank-Datei...")
conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()
# Wir ändern den Text von 'Sichere Daten' zu 'GEHACKT' direkt in der SQL-Datei
cursor.execute("UPDATE ledger_entries SET payload_json = '{\"data\":\"GEHACKT\"}' WHERE seq = 2")
conn.commit()
conn.close()

print("🛡️ Prüfung: Erkennt der Ledger den Einbruch?")
try:
    ledger.verify_integrity()
    print("❌ FEHLER: Die Manipulation wurde NICHT erkannt! (Das darf nicht passieren)")
except Exception as e:
    print(f"✅ ERFOLG: Einbruch erkannt! Fehlermeldung: {e}")