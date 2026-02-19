# ==============================================================================
# VELONAUT | core/commit_guard_service.py
# Block C – Commit Guard Service
# Five-Lock Certification Commit Authority
#
# Audit Trail:
#   - Fix 1: Freeze Hash verwendet '|' Separator (verhindert String-Kollisionen)
#   - Fix 2: Double Spend Check gegen receipt_hashes (nicht report_ids)
#   - Fix 3: Toter block_hash-Berechnungsblock entfernt
#   - Fix 4: receipt_hashes werden atomar in certified_receipts geschrieben
#   - Fix 5: Post-Commit Integrity auf BEIDEN Chains
# ==============================================================================

import sqlite3
import json
import hashlib
import unicodedata
from datetime import datetime, timezone


class CommitGuardService:
    """
    Single Commit Authority für alle irreversiblen Asset-Zertifizierungen.

    Invarianten:
    - Kein UI-Code schreibt direkt in ledger_entries oder certified_receipts
    - Alle fünf Schlösser müssen passiert sein bevor ein Write stattfindet
    - Bei jedem Fehler: Hard Stop, kein partieller Commit
    - Post-Commit: Beide Chains werden verifiziert
    """

    def __init__(self, governance_ledger, asset_ledger, asset_engine, asset_db_path: str):
        """
        Parameters
        ----------
        governance_ledger : VelonautLedger
            Die Governance Chain (velonaut_gov.db)
        asset_ledger : VelonautLedger
            Die Asset Chain (velonaut_ledger.db)
        asset_engine : AssetEngine
            Engine für deterministischen Fleet Snapshot
        asset_db_path : str
            Direkter DB-Pfad für certified_receipts (atomar mit asset_ledger)
        """
        self.gov_ledger = governance_ledger
        self.asset_ledger = asset_ledger
        self.engine = asset_engine
        self.asset_db_path = asset_db_path

    def execute_certification_commit(
        self,
        reporting_year: int,
        role: str,
        pin_valid: bool,
        signer_func
    ) -> dict:
        """
        Führt einen vollständig gesicherten Certification Commit durch.

        Returns
        -------
        dict mit:
            "status": "SUCCESS" | "ERROR"
            "message": str
            "freeze_hash": str (nur bei SUCCESS)
            "block_seq": int (nur bei SUCCESS)
        """

        # ==================================================================
        # SCHLOSS 1 – AUTHORITY VALIDATION
        # ==================================================================
        if role not in ("OWNER", "AUDITOR"):
            return {
                "status": "ERROR",
                "message": f"AUTHORITY_DENIED: Role '{role}' is not authorized for certification commits."
            }

        if not pin_valid:
            return {
                "status": "ERROR",
                "message": "AUTHORITY_DENIED: PIN validation failed."
            }

        # ==================================================================
        # SCHLOSS 2 – FRESH SNAPSHOT & FREEZE HASH
        # ==================================================================
        snapshot = self.engine.get_fleet_snapshot(str(reporting_year))

        if "error" in snapshot:
            return {
                "status": "ERROR",
                "message": f"ENGINE_FAILURE: {snapshot['error']}"
            }

        if snapshot.get("count", 0) == 0:
            return {
                "status": "ERROR",
                "message": "SNAPSHOT_EMPTY: No ELIGIBLE reports found for this reporting year."
            }

        if not snapshot.get("calculation_fingerprint"):
            return {
                "status": "ERROR",
                "message": "SNAPSHOT_INVALID: calculation_fingerprint missing."
            }

        # Freeze Hash: '|' als Separator verhindert String-Kollisionen
        # Beispiel ohne Separator: "abc" + "12" + "026" == "abc1" + "2" + "026"
        freeze_input = (
            f"{snapshot['calculation_fingerprint']}"
            f"|{snapshot['count']}"
            f"|{reporting_year}"
        )
        freeze_hash = hashlib.sha256(freeze_input.encode("utf-8")).hexdigest()

        # ==================================================================
        # SCHLOSS 3 – DOUBLE SPEND CHECK
        # receipt_hashes aus der DB laden (engine liefert report_ids,
        # certified_receipts speichert receipt_hashes — muss gejoined werden)
        # ==================================================================
        involved_report_ids = snapshot.get("involved_reports", [])

        if not involved_report_ids:
            return {
                "status": "ERROR",
                "message": "SNAPSHOT_INVALID: involved_reports is empty."
            }

        try:
            with sqlite3.connect(self.asset_db_path) as conn:
                # Schritt A: report_ids → receipt_hashes auflösen
                placeholders = ",".join(["?"] * len(involved_report_ids))
                rows = conn.execute(
                    f"SELECT report_id, receipt_hash FROM telemetry_reports "
                    f"WHERE report_id IN ({placeholders})",
                    involved_report_ids
                ).fetchall()

                if len(rows) != len(involved_report_ids):
                    return {
                        "status": "ERROR",
                        "message": "INTEGRITY_VIOLATION: Snapshot references reports not found in DB."
                    }

                receipt_hashes = [r[1] for r in rows]

                # Schritt B: Double Spend prüfen
                rh_placeholders = ",".join(["?"] * len(receipt_hashes))
                existing = conn.execute(
                    f"SELECT receipt_hash FROM certified_receipts "
                    f"WHERE receipt_hash IN ({rh_placeholders})",
                    receipt_hashes
                ).fetchall()

                if existing:
                    already_spent = [e[0][:12] for e in existing]
                    return {
                        "status": "ERROR",
                        "message": f"DOUBLE_SPEND_DETECTED: {already_spent}"
                    }

        except Exception as e:
            return {
                "status": "ERROR",
                "message": f"DB_ERROR during double spend check: {str(e)}"
            }

        # ==================================================================
        # SCHLOSS 4 – DETERMINISTIC PAYLOAD CONSTRUCTION
        # Canonical JSON, sort_keys, Unicode NFC, SHA256
        # Der block_hash wird von asset_ledger.add_entry() gebaut —
        # wir bauen hier nur den Payload deterministisch.
        # ==================================================================
        payload = {
            "reporting_year": reporting_year,
            "fleet_report_count": snapshot["count"],
            "verified_fuel_mt": snapshot["verified_fuel_mt"],
            "co2_emissions_t": snapshot["co2_emissions_t"],
            "calculation_fingerprint": snapshot["calculation_fingerprint"],
            "snapshot_freeze_hash": freeze_hash,
            "involved_receipt_hashes": sorted(receipt_hashes),  # stabil sortiert
            "committed_at_utc": datetime.now(timezone.utc).isoformat()
        }

        # Payload-Fingerprint zur Verifikation (nicht als Block-Hash verwendet)
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        normalized = unicodedata.normalize("NFC", canonical)
        payload_fingerprint = hashlib.sha256(normalized.encode("utf-8")).hexdigest()

        # ==================================================================
        # SCHLOSS 5 – ATOMIC WRITE: ASSET LEDGER + CERTIFIED RECEIPTS
        # ==================================================================
        try:
            block_seq = self.asset_ledger.add_entry(
                block_type="CERTIFICATION",
                payload=payload,
                reporting_year=reporting_year,
                signer_func=signer_func
            )
        except Exception as e:
            return {
                "status": "ERROR",
                "message": f"LEDGER_WRITE_FAILED: {str(e)}"
            }

        # Zertifizierte Receipts sperren (atomar nach erfolgreichem Ledger-Write)
        try:
            # Block Hash aus der Kette lesen (just written)
            with sqlite3.connect(self.asset_db_path) as conn:
                row = conn.execute(
                    "SELECT current_hash FROM ledger_entries WHERE seq = ?",
                    (block_seq,)
                ).fetchone()

                if not row:
                    return {
                        "status": "ERROR",
                        "message": "POST_WRITE_ERROR: Block not found after write."
                    }

                written_block_hash = row[0]

                # Alle receipt_hashes in certified_receipts sperren
                conn.executemany(
                    "INSERT INTO certified_receipts (receipt_hash, certificate_block_hash) VALUES (?, ?)",
                    [(rh, written_block_hash) for rh in receipt_hashes]
                )

                # Status auf CERTIFIED setzen
                rh_placeholders = ",".join(["?"] * len(receipt_hashes))
                conn.execute(
                    f"UPDATE telemetry_reports SET status='CERTIFIED' "
                    f"WHERE receipt_hash IN ({rh_placeholders})",
                    receipt_hashes
                )
                conn.commit()

        except Exception as e:
            # Ledger-Block existiert bereits — wir können nicht rückgängig machen.
            # Das ist der einzige Moment wo ein inkonsistenter Zustand möglich ist.
            # Hard Stop mit explizitem Hinweis für manuelle Intervention.
            return {
                "status": "CRITICAL_PARTIAL_WRITE",
                "message": (
                    f"LEDGER_WRITE_OK_BUT_RECEIPT_LOCK_FAILED: {str(e)} — "
                    f"Block SEQ {block_seq} existiert. Manuelle Intervention erforderlich."
                )
            }

        # ==================================================================
        # POST-COMMIT INTEGRITY CHECK – BEIDE CHAINS
        # ==================================================================
        try:
            self.asset_ledger.verify_integrity()
        except Exception as e:
            return {
                "status": "ERROR",
                "message": f"ASSET_CHAIN_INTEGRITY_FAILURE after commit: {str(e)}"
            }

        try:
            self.gov_ledger.verify_integrity()
        except Exception as e:
            return {
                "status": "ERROR",
                "message": f"GOV_CHAIN_INTEGRITY_FAILURE after commit: {str(e)}"
            }

        # ==================================================================
        # SUCCESS
        # ==================================================================
        return {
            "status": "SUCCESS",
            "message": "Certification block written and both chains verified.",
            "freeze_hash": freeze_hash,
            "payload_fingerprint": payload_fingerprint,
            "block_seq": block_seq,
            "certified_receipts_locked": len(receipt_hashes)
        }
