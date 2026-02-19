import os
import time
from core.ledger import VelonautLedger
import nacl.signing
import nacl.encoding

DB_FILE = "bench_10k.sqlite"
if os.path.exists(DB_FILE): os.remove(DB_FILE)

signing_key = nacl.signing.SigningKey.generate()
verify_key_hex = signing_key.verify_key.encode(nacl.encoding.HexEncoder).decode()
def simple_signer(h): return signing_key.sign(h).signature

ledger = VelonautLedger("BENCH_10K", DB_FILE, verify_key_hex)

print(f"🚀 Starte Belastungstest: 10.000 Blöcke...")
start_write = time.perf_counter()

ledger.add_entry("GENESIS", {"init": True}, 2026, simple_signer)
for i in range(2, 10001):
    ledger.add_entry("EVENT", {"index": i}, 2026, simple_signer)

write_time = time.perf_counter() - start_write
print(f"✅ 10.000 Blöcke geschrieben in {write_time:.2f} Sekunden.")

print("🔍 Vollständiges Replay von 10.000 Blöcken...")
start_verify = time.perf_counter()
ledger.verify_integrity()
verify_time = time.perf_counter() - start_verify

print(f"✅ Replay beendet: {verify_time:.4f} Sekunden.")
print(f"   (Geschwindigkeit: {10000/verify_time:.0f} Blöcke/Sekunde)")