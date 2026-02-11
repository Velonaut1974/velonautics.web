🚢 Velonaut | Maritime Integrity Infrastructure (v0.4.1-Beta)

Velonaut is a high-fidelity accounting engine for maritime decarbonization. It provides the technological bridge between mandatory regulatory compliance and the voluntary carbon credit markets.
🎯 The Problem: Regulatory Collision & Double-Counting

The maritime industry faces a unique accounting challenge:

    EU ETS requires mass-based carbon accounting.

    FuelEU Maritime enforces energy-based GHG intensity limits.

The Integrity Gap: A single ton of green fuel can currently be "spent" twice—once for regulatory compliance and once as a voluntary carbon credit (Insetting). This Double-Counting undermines market trust and regulatory stability.

Our Solution: Velonaut implements a State Machine Firewall that cryptographically locks energy events to a single purpose. Once a Joule of energy is used for compliance, it is isolated from the voluntary market—permanently and irreversibly.
🚀 Live Infrastructure Demo

Explore the functional prototype and the logic of the Triple-Layer-Architecture:
👉 https://velonautics-os.streamlit.app/
⚡ Quick Start (Local Development)

To run the Velonaut engine and UI on your local machine:
Bash

# 1. Clone the repository
git clone https://github.com/Velonaut1974/velonautics.web.git
cd velonautics.web

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the application
python -m streamlit run app.py

🛡️ The Triple-Layer Architecture
Layer I: Compliance Analytics (The Calculation)

    Real-Time Monitoring: Continuous calculation of Fleet GHG Intensity (gCO2e/MJ).

    Regulatory Alignment: Implementation of EU ETS Phase-in schedules and FuelEU Maritime reference values (91.16 g/MJ).

    ISO 19848 Ready: Data structures designed for seamless ship-to-shore data sharing.

Layer II: Isolation Firewall (The Ledger)

    State Machine Logic: Every EnergyEvent transitions through a strictly controlled lifecycle: RAW → LOCKED (Compliance) → MARKETABLE.

    Immutability: Once an event is locked, it cannot be repurposed for other markets, effectively preventing double-counting "by design."

Layer III: Verified Asset Issuance (The Bank)

    Additionality Engine: Calculates the true surplus after subtracting regulatory obligations and institutional risk buffers.

    Provenance Hashing: Every issued asset is tagged with a SHA-256 fingerprint of the entire fleet state.

    Registry Ready: Native export of assets in standardized formats.

🔐 Provenance Hashing & Auditability

We don't just issue credits; we issue proofs.

Every InsettingAsset contains a source_data_hash. This is a cryptographic anchor to the exact data basis at the time of issuance.

    ✅ Audit-proof: Verifiers can instantly check if the asset matches the source data.

    ✅ Tamper-proof: Any retroactive change to historical fuel data invalidates the hash, alerting auditors immediately.

Example Asset Output (JSON)
JSON

{
  "asset_id": "VELO-A3B8F291",
  "vintage": 2025,
  "volume_t_co2e": 14.93,
  "strategy": "CONSERVATIVE (30% Buffer)",
  "source_hash": "4a5e6b2c8f1d3e9a7c5b8d2f4e6a8c1b...",
  "engine_version": "Velonaut-Core-v0.4.1",
  "source_event_ids": ["evt-001", "evt-101", "evt-201"]
}

🎯 Use Cases

    Fleet Operators: Manage complex compliance portfolios and identify monetizable surpluses.

    Carbon Traders: Verify the absolute provenance and "Joule-Tagging" of maritime assets.

    Auditors: Leverage immutable state transitions and cryptographic hashes for streamlined verification.

🏗️ Project Status & Roadmap

    Current: v0.4.1-Beta (Functional Prototype, In-memory Ledger)

    Next (v0.5): Migration to Immutable SQLite Ledger, Multi-Year Strategy Simulation.

    Future (v1.0): API-First Architecture for VMS/ERP Integration.

License: Proprietary | Maintained by: Velonautics Team

📧 Contact: hello@velonautics.de | 🌐 Website: velonautics.com