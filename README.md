# VELONAUTICS: Regulatory Isolation by Design

> **An infrastructure for orchestrating regulatory compliance and voluntary value creation across EU-ETS and FuelEU Maritime.**

---

## 01. The Context: The Regime Collision
The maritime industry is currently facing a "Cognitive Bottleneck." For the first time, operators must navigate two fundamentally different regulatory logics simultaneously:

* **EU-ETS:** A mass-based regime (Absolute Emissions / Cap & Trade).
* **FuelEU Maritime:** An intensity-based regime (GHG intensity per Energy Unit / Pooling & Banking).

Managing these asynchronies manually is not just inefficient—it is a systemic risk. **VELONAUTICS** provides the decision infrastructure to solve this collision through a dedicated isolation architecture.

---

## 02. The Solution: Triple-Layer Architecture (TLA)
At the core of VELONAUTICS is a three-tier logic designed to prevent double counting and ensure regulatory integrity.

### Layer I: Regulatory Compliance (The Safety Net)
* **Function:** Active allocation and simulation of mandatory obligations.
* **EU-ETS:** Precise tracking of absolute emissions ($CO_2$, $CH_4$, $N_2O$) for EUA surrender requirements.
* **FuelEU Maritime:** Dynamic allocation of GHG intensity ($gCO_2e/MJ$) through fleet-wide pooling, banking, and borrowing scenarios.

### Layer II: Eligibility & Isolation Filter (The Firewall)
* **Function:** The architectural safeguard for data integrity.
* **Zero-Double-Counting:** Every Joule of energy is digitally tagged. Any unit used for FuelEU compliance or allocated within a pool is **irreversibly locked**.
* **Integrity Check:** Only emissions reductions that are neither regulatory-bound nor double-counted are **made eligible for voluntary attribution**.

### Layer III: Maritime Carbon Bank (The Value Layer)
* **Function:** Institutional infrastructure for the economic attribution of audited additionality.
* **Insetting-Certificates:** Transformation of isolated, verified reductions into accountable Scope 3 assets for cargo owners.
* **Green Premium Logic:** Proof of decarbonization that remains independent of aggregated fleet compliance balances.

---

## 03. The Agent: Velonaut
**Intelligence within Constraints.**

`Velonaut` is not a pilot; it is an **Orchestrator**. The agent operates as a specialized AI layer that simulates allocation scenarios within the strict boundaries of the Triple-Layer Architecture **without executing irreversible actions autonomously.**

* **Orchestration over Autonomy:** Every recommendation is based on the current regulatory "moat" and audited precedence.
* **Deliberate Friction:** The system prioritizes auditability over speed. 

---

## 04. Governance & Auditability
* **Joule-based Marking:** Every energy unit is tracked from Well-to-Wake, including geographic verification (50/100% logic).
* **Tamper-Evident Logs:** Every allocation decision is recorded in append-only, tamper-evident logs to provide a transparent audit trail for classification societies and regulators.

---

## 05. Documentation & Resources
* **Whitepaper:** [Download PDF](whitepaper.pdf)
* **System Architecture:** See `/docs/architecture.pdf`
* **Contribution:** This repository is open for logic audits by maritime stakeholders.

---

**Our logic is open for audit. Our integrity is by design.**
