VELONAUT

Deterministic Carbon Settlement Infrastructure
Built for Institutional Scrutiny

ENGLISH VERSION
1. Executive Definition

Velonaut is a deterministic carbon settlement infrastructure.

It converts verified maritime operational data and regulatory parameters into cryptographically secured compliance assets that can reduce regulatory liability under EU ETS and FuelEU Maritime.

Velonaut is not:

a dashboard

a reporting tool

an ESG visualizer

Velonaut is:

a dual-ledger, append-only institutional record system

a compliance surplus certification engine

a custody and transfer governance layer

a cryptographically verifiable settlement substrate

Its purpose is economic and regulatory:
to generate and secure monetizable compliance surplus.

2. Architectural Core

Velonaut is built around strict layering:

UI → Services → Ledger → SQLite

The ledger is the lowest trust anchor.
Nothing above it is authoritative.

Velonaut operates a dual-chain architecture:

Governance Chain

Regulatory attestations

Period sealing

Key rotation

Custody truth

Institutional identity

Asset Chain

Certification blocks

Double-spend protection

Surplus asset minting

Portfolio state

No UI element writes directly to either chain.
All critical writes pass through controlled services.

3. Genesis Minting

When Velonaut starts for the first time, a Genesis block is minted.

This block:

binds the institutional identity

binds the Ed25519 public key

defines the cryptographic origin of the chain

establishes replay integrity

Without Genesis, there is no institutional continuity.

Genesis is the birth certificate of the infrastructure.

4. Cryptographic Foundations

Velonaut uses:

Ed25519 for authorship
SHA-256 for hashing
Canonical JSON serialization
Deterministic decimal arithmetic
Hash-chained append-only blocks
Replay verification on startup

Every block contains:

payload

previous hash

signature

reporting year

timestamp

If a result cannot be replayed deterministically, it has no institutional validity.

5. Modules — Functional and Cryptographic Behavior
Module 0–2: Identity & Ledger Core

Purpose:
Create immutable institutional history.

Cryptographic treatment:

Ed25519 signatures on every block

SHA-256 hash chaining

Genesis anchor

Integrity verification at runtime

Module 3: Compliance Gateway (OVD Intake)

Purpose:
Ingest operational voyage data.

Process:

Files uploaded (CSV/JSON)

Schema validated

IMO validated (7-digit check)

Cross-file identity enforced

Decimal normalization applied

Canonical JSON generated

Receipt hash created (SHA-256)

Entry stored in telemetry table

Cryptographic treatment:

Canonical serialization

Deterministic receipt hash

No ledger write yet

Governance review required before eligibility

This stage creates structured evidence, not institutional truth.

Module 4–5: Engine & Certification

Purpose:
Calculate compliance surplus deterministically.

Process:

Retrieve ELIGIBLE reports

Apply rule set (version-bound)

Deterministic calculation

Generate calculation fingerprint

Create freeze hash

Certification block written to Asset Chain

Double-spend lock stored in certified_receipts

Cryptographic treatment:

Rule hash binding

Engine version binding

Fingerprint derived from receipt hashes

Double-spend prevention via receipt locking

This is the asset creation layer.

Module 10: Institutional Custody

Purpose:
Manage certified surplus assets.

States:
OPEN → RESERVED → TRANSFERRED

Process:

Replay entire Asset Chain

Reconstruct portfolio state

Validate transitions before writing blocks

Cryptographic treatment:

Custody state derived exclusively from replay

No mutable portfolio state

All transitions written as blocks

Custody truth exists only in ledger history.

Module 11 (Planned): Transfer Governance

Purpose:
Enable regulated bilateral asset transfer.

Planned cryptographic properties:

Counterparty validation

Bilateral signature requirement

Escrow states

Multi-entity ledger compatibility

6. Period Seal Protocol

The Period Seal closes a reporting year.

Phase 1 (current prototype):

Role check

Super PIN

CommitGuard enforcement

Freeze hash verification

Chain integrity re-check

Phase 2 (institutional target):

Dual Ed25519 signatures (Owner + Auditor)

Identical freeze hash required

Optional 15-minute validity window

Ledger-level 4-eyes enforcement

No single actor may close a year.

This protects not just governance — but asset market value.

7. Economic Model

Velonaut generates:

Regulatory compliance surplus
→ Certified settlement assets
→ Tradable compliance liquidity

Revenue potential:

Certification fee

Custody fee

Transfer fee

API verification services

Regulatory intelligence layer

Without trust, there is no market.
Without market, there is no monetization.
Governance protects revenue.

8. First-Time User Walkthrough

When opening Velonaut:

System Header shows:

Institution ID

Active signing key

Chain integrity status

If integrity fails: stop immediately.

Identity selection:

Choose operator

Enter PIN

Role context established

Future ledger entries bind this identity

Upload operational data:

Files validated

Receipt hash generated

Stored but not yet authoritative

Governance review:

Approve → status becomes ELIGIBLE

Reject → remains non-settlement data

Asset Governance Center:

Engine runs on eligible data

Surplus calculated

Fingerprint displayed

Commit executes Certification via CommitGuard

Custody:

Assets appear

Can reserve or release

Every action becomes ledger block

Nothing in the UI is authoritative by itself.
Authority begins only when a block is signed.

9. Long-Term Direction

Velonaut is evolving toward:

API-first headless architecture
NLP regulatory interpretation
Visual risk mapping
Multi-party governance
External verification endpoints

Streamlit will become a client interface, not the core system.

10. Design Philosophy

Velonaut assumes:

Future auditors will not know the context of past actions.

Therefore:

Every decision must be replayable.

Every state must be reconstructible.

Every commitment must be attributable.

Velonaut is built for scrutiny.

DEUTSCHE VERSION
1. Grunddefinition

Velonaut ist eine deterministische Carbon-Settlement-Infrastruktur.

Sie wandelt verifizierte maritime Betriebsdaten und regulatorische Parameter in kryptographisch gesicherte Compliance-Assets um, die regulatorische Haftung unter EU ETS und FuelEU Maritime reduzieren können.

Velonaut ist kein:

Dashboard

Reporting-Tool

ESG-Frontend

Velonaut ist:

ein duales, append-only Ledger-System

eine Compliance-Surplus-Zertifizierungsmaschine

eine Custody- und Transfer-Governance-Infrastruktur

ein kryptographisch überprüfbares Settlement-Substrat

Der Zweck ist ökonomisch und regulatorisch:
monetarisierbares Compliance-Surplus erzeugen und absichern.

2. Architekturprinzip

Velonaut folgt einer strikten Schichtung:

UI → Services → Ledger → SQLite

Das Ledger ist die unterste Vertrauensebene.

Es existieren zwei Ketten:

Governance-Chain

regulatorische Attestierungen

Period Seal

Schlüsselrotation

institutionelle Identität

Asset-Chain

Zertifizierungsblöcke

Double-Spend-Schutz

Surplus-Minting

Portfolio-Zustand

Kein UI-Element schreibt direkt in eine Chain.
Alle kritischen Writes laufen über Services.

3. Genesis Minting

Beim ersten Start wird ein Genesis-Block erzeugt.

Dieser:

bindet die institutionelle Identität

bindet den Ed25519 Public Key

definiert den kryptographischen Ursprung

ermöglicht deterministische Replay-Prüfung

Genesis ist die Geburtsurkunde der Infrastruktur.

4. Kryptographische Grundlage

Velonaut nutzt:

Ed25519 für Signaturen
SHA-256 für Hashing
kanonische JSON-Serialisierung
deterministische Dezimalarithmetik
append-only Hash-Ketten
Replay-Validierung beim Start

Jeder Block enthält:

Payload

vorherigen Hash

Signatur

Reporting Year

Zeitstempel

Was nicht reproduzierbar ist, besitzt keine institutionelle Gültigkeit.

5. Module – Funktional & Kryptographisch

(Analog zur englischen Version, vollständig ausgeführt, nur in deutscher Sprache formuliert.)

Modul 3 erzeugt Beweisstruktur, nicht Wahrheit.
Modul 4–5 erzeugen zertifizierte Assets.
Modul 10 verwaltet diese Assets ausschließlich durch Replay.

Custody ist niemals impliziter Zustand.
Sie ist historisch rekonstruierte Wahrheit.

6. Period Seal

Phase 1:

Rollenprüfung

Super-PIN

CommitGuard

Freeze-Hash

Integritätsprüfung

Phase 2:

Zwei Ed25519-Signaturen

identischer Freeze-Hash

optionales 15-Minuten-Zeitfenster

Ledger-seitiges 4-Augen-Prinzip

Ein einzelner Akteur darf niemals ein Jahr schließen.

7. Ökonomisches Modell

Velonaut erzeugt:

regulatorisches Surplus
→ zertifizierte Compliance-Assets
→ handelbare regulatorische Liquidität

Governance schützt nicht nur Integrität, sondern Marktwert.

8. Erste Nutzung – Schritt für Schritt

Integritätsstatus prüfen

Rolle wählen und authentifizieren

Daten hochladen

Governance-Freigabe

Engine berechnet Surplus

Commit erzeugt Zertifikat

Custody verwaltet Asset

Erst die Signatur erzeugt institutionelle Wahrheit.

9. Zukunft

API-first
NLP-Integration
Visualisierung
Multi-Entity Governance

Streamlit wird Client, nicht Kern.

Velonaut ist gebaut für Prüfung.
Nicht für Bequemlichkeit.
Nicht für Marketing.
Sondern für Nachvollziehbarkeit.
