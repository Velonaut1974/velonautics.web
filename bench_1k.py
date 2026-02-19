import os
import time
from core.ledger import VelonautLedger
import nacl.signing
import nacl.encoding

DB_FILE = "bench_1k.sqlite"
if os.path.exists(DB_FILE): os.remove(DB_FILE)

# Setup
signing_key = nacl.signing.SigningKey.generate()
verify_key_hex = signing_key.verify_key.encode(nacl.encoding.HexEncoder).decode()
def simple_signer(h): return signing_key.sign(h).signature

ledger = VelonautLedger("BENCH_1K", DB_FILE, verify_key_hex)

print(f"🚀 Starte Benchmark: Schreibe 1.000 Blöcke...")
start_write = time.perf_counter()

# Genesis + 999 Events
ledger.add_entry("GENESIS", {"init": True}, 2026, simple_signer)
for i in range(2, 1001):
    ledger.add_entry("EVENT", {"index": i, "data": "Performance-Test"}, 2026, simple_signer)

end_write = time.perf_counter()
write_time = end_write - start_write

print(f"✅ Schreiben beendet: {write_time:.2f} Sekunden.")
print(f"   (Das sind ca. {write_time/1000*1000:.2f} ms pro Eintrag)")

print("\n🔍 Starte Integritäts-Replay (Vollständige Prüfung)...")
start_verify = time.perf_counter()
ledger.verify_integrity()
verify_time = time.perf_counter() - start_verify

print(f"✅ Replay beendet: {verify_time:.4f} Sekunden.")
print(f"   (Geschwindigkeit: {1000/verify_time:.0f} Blöcke/Sekunde)")