import os
import threading
import time
from core.ledger import VelonautLedger
import nacl.signing
import nacl.encoding

DB_FILE = "bench_threads.sqlite"
if os.path.exists(DB_FILE): os.remove(DB_FILE)

signing_key = nacl.signing.SigningKey.generate()
verify_key_hex = signing_key.verify_key.encode(nacl.encoding.HexEncoder).decode()
def simple_signer(h): return signing_key.sign(h).signature

ledger = VelonautLedger("THREAD_TEST", DB_FILE, verify_key_hex)
ledger.add_entry("GENESIS", {"msg": "Initial"}, 2026, simple_signer)

def worker(start_index):
    # Jeder Thread bekommt seine eigene Connection zum selben Ledger-Pfad
    # Das simuliert mehrere App-Instanzen
    local_ledger = VelonautLedger("THREAD_TEST", DB_FILE, verify_key_hex)
    for i in range(50):
        local_ledger.add_entry("EVENT", {"data": f"Thread-Tx {start_index + i}"}, 2026, simple_signer)
        ledger.add_entry("GENESIS", {"msg": "Initial"}, 2026, simple_signer)

print("🚀 Starte Concurrency-Test: 5 Threads schreiben gleichzeitig...")
threads = []
for i in range(5):
    t = threading.Thread(target=worker, args=(i * 100,))
    threads.append(t)

start = time.perf_counter()
for t in threads: t.start()
for t in threads: t.join()
duration = time.perf_counter() - start

print(f"✅ 250 parallele Einträge geschrieben in {duration:.2f} Sekunden.")

print("🔍 Prüfe Ledger-Konsistenz nach dem Stress...")
try:
    ledger.verify_integrity()
    print("✅ INTEGRITÄT GEPRÜFT: Keine Kollisionen, Kette ist lückenlos!")
except Exception as e:
    print(f"❌ FEHLER: Integrität verletzt! {e}")