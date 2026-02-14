VELONAUT
Institutional Forensic Ledger
Auditor & Operator Documentation
1. Institutional Positioning

VELONAUT provides a controlled environment for transforming operational maritime data into cryptographically verifiable compliance records.

The system is designed to support review, reconstruction and third-party assurance processes under regulatory regimes such as EU ETS and FuelEU Maritime.

VELONAUT does not replace institutional judgement.
It provides deterministic evidence infrastructure.

2. What the System Guarantees Today

At the current release stage, the platform provides:

✔ sequential block integrity
✔ cryptographic authorship
✔ deterministic recalculation
✔ historic reconstruction
✔ independent verification outside the software

The system intentionally requires human initiation for legally relevant actions.

3. Architectural Overview
Ledger Model

VELONAUT operates a private, SQLite-backed append-only ledger.

Each block contains:

sequence number

institution identifier

block type

reporting year

previous block hash

regulatory payload hash (for events)

canonical payload

block hash

Ed25519 signature

UTC timestamp

Hashes are derived from canonical JSON serialization to guarantee reproducibility.

Any modification would invalidate:

the block hash

the signature

the forward chain

Signature Framework

All entries are signed using Ed25519.

Verification during integrity checks automatically:

re-computes each block hash

verifies signatures

validates hash continuity

applies key succession rules after rotation

Auditors can reproduce this without access to proprietary components.

Genesis Binding

At initialization, the first block embeds the institutional public key.

If the locally active key deviates from the Genesis declaration, system operation halts.

This prevents silent takeover of an existing ledger.

Period Closure

A reporting year can be sealed.

During sealing:

chain integrity is verified

all hashes of the period are aggregated

a deterministic master hash is created

the closure block is signed and appended

the year becomes append-locked

Further entries for the period are rejected.

Arithmetic Discipline

Financial and volumetric computations are executed using fixed precision decimal arithmetic (28 digits).

This ensures reproducible institutional results across environments.

4. Operational Workflow
Phase I – Raw Data Presence

Operational energy events enter the system in RAW state.

At this stage they remain comparable to external documentation.

Phase II – Compliance Securing

When an operator confirms an event, it is moved into a protected state.

The original information remains visible.
Any later correction would require a new ledger entry rather than alteration.

Phase III – Regulatory Asset Formation

If a compliance surplus exists:

parameters (year, strategy) are chosen

a market price input is declared

a market snapshot is generated

event references are frozen

a signed ledger block is created

The snapshot includes:

price

source declaration

confidence classification

timestamp

snapshot hash

Snapshots are additionally written to a separate historic table for traceability.

5. Market Data Interpretation

Market Snapshot v2 provides contextual valuation.

It is not an execution venue and does not represent guaranteed liquidity.

Responsibility for price correctness remains with the operator.

The ledger guarantees only that the declared input is preserved.

6. Governance Mechanisms
Key Rotation

A new public key can be introduced.

The currently trusted key must sign the transition.

During verification, trust automatically migrates along the chain.

Database Reliability

SQLite operates in:

WAL mode

FULL synchronous setting

This prioritizes durability over speed.

Failure Behaviour

If inconsistencies are detected, the system switches from operational mode to protective halt.

7. Independent Audit Capability

Each block can be exported including:

payload

hash

signature

chain reference

A third party can verify authenticity using standard Ed25519 libraries.

No internal APIs are required.

8. Current Maturity Assessment

The system is suitable for:

✔ supervised institutional environments
✔ internal control frameworks
✔ preparation for external audits
✔ pilot operations

The system is not yet positioned for:

✖ autonomous market interaction
✖ unsupervised regulatory submission

9. Roadmap
Automated Provenance Layer

Planned integration of signed external price feeds.

Regulatory Rule Versioning

Machine-readable updates of tightening factors.

Multi-Party Attestation

Optional co-signatures by verifiers or authorities.

10. Closing Statement

VELONAUT focuses on making statements provable, not impressive.

The system prefers explicit operator responsibility over hidden automation.

For institutional environments, this is a feature.