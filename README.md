# 🚢 VELONAUTICS | Institutional Forensic Ledger v0.5.6

**The Sovereignty Protocol for Maritime Carbon Insetting**

---

## 🏗️ The Triple-Layer Architecture
VELONAUTICS is built on a non-linear data integrity model designed to bridge the gap between physical bunker operations and institutional carbon markets.

### 📡 Layer I: Physical Data Proof (Sovereignty)
The foundation of the system. Layer I ensures that raw physical data (IoT sensors, Bunker Delivery Notes) is cryptographically anchored. 
* **Forensic Replay:** Every time the system boots, it re-calculates the entire fleet history to ensure zero data tampering.
* **Deterministic Arithmetik:** Using IEEE-754 error-free `Decimal` math.

### 🛡️ Layer II: Isolation Firewall (Compliance)
This layer transforms physical raw data into regulatory "Compliance Events". 
* **State Locking:** Once an event is moved to Layer II and locked, it is isolated from further modification.
* **Audit Readiness:** This creates a frozen evidence base for FuelEU Maritime and EU ETS verification.

### 💎 Layer III: Additionality Assets (Tokenization)
The issuance layer where "Net Surplus" is converted into tradeable assets.
* **Chained Assets:** Every asset is linked to its predecessor, forming an immutable chain of custody.
* **HMAC Signatures:** Each entry is cryptographically signed to prevent database manipulation.

---

## 🛠️ Technical Specification (The "Nerd" Section)

### 1. Cryptographic Primitives
* **Hashing Algorithm:** SHA-256 for all anchors.
* **Signature Algorithm:** HMAC-SHA256 (Hash-based Message Authentication Code).
* **Canonicalization:** All JSON structures are serialized using `sort_keys=True` and `separators=(',',':')` to ensure cross-platform hash consistency.

### 2. Forensic Security Model
* **Arithmetic Sovereignty:** We utilize 28-point precision `Decimal` math to eliminate floating-point rounding errors (e.g., $0.1 + 0.2 \neq 0.3$).
* **Regulatory Anchor:** The `reg_hash` separates physical truth from market strategy. If rules change (Engine Versioning), the physical proof remains valid.
* **Timestamp Monotony:** The ledger rejects any entry with a timestamp earlier than the preceding entry, preventing "backdating fraud".

### 3. Ledger Structure
Each Asset Entry follows a strict forensic schema:
- `seq`: Monotonic sequence counter.
- `prev_hash`: Link to the preceding block.
- `reg_hash`: Deterministic hash of physicals + rules + engine version.
- `payload`: The actual asset data and volume.
- `asset_hash`: The unique identifier of the block.
- `signature`: The HMAC-SHA256 seal protecting the entire entry.

### 4. Mathematical Replay Logic
The system does not "trust" the stored volume (`vol`). During validation, it executes a **Deterministic Replay**:
$$Total\_Balance = \sum ( (Target - Actual) \times Energy \times Scope )$$
If the re-calculated balance deviates by even $10^{-7}$ from the stored volume, the Ledger triggers a **Critical Breach Alarm**.

---

## 🚀 Deployment & Demo Guide
1. **Initialize:** The system starts with the `VELO-GENESIS` block (SEQ 0).
2. **Locking:** Use the Isolation Firewall (Layer II) to freeze raw events.
3. **Issuance:** Tokenize the resulting surplus in Layer III.
4. **Audit:** Download the "Audit Export" JSON and verify it against the local hash engine.

---
*Disclaimer: VELONAUTICS is a conceptual infrastructure project. No commercial services are offered at this stage.*