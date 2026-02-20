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
        auth_context: dict,
        signer_func
    ) -> dict:
        """
        Führt einen vollständig gesicherten Certification Commit durch.
        Nutzt den AuthService Context für maximale Governance.
        """

        # ==================================================================
        # SCHLOSS 1 – AUTHORITY VALIDATION (DB-Grounded)
        # ==================================================================
        actor = auth_context.get("user")
        role = auth_context.get("role")

        # DER ENTSCHEIDENDE DB-CHECK: Wir rufen die neue Funktion von unten auf
        if not self._is_authority_valid(actor, role):
            return {
                "status": "ERROR",
                "message": f"AUTHORITY_FORGERY_DETECTED: Mandat für '{actor}' als '{role}' nicht in der Registry gefunden."
            }

        allowed_roles = ["OWNER", "AUDITOR"]
        if role not in allowed_roles:
            return {
                "status": "ERROR",
                "message": f"AUTHORITY_DENIED: Rolle '{role}' ist nicht für Commits autorisiert."
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
    def commit_regulatory_snapshot(self, event_type, payload, year, signing_key):
        """
        Service-seitige Ausführung von regulatorischen Snapshots.
        Hier greift die Hard-Whitelist des Lockdowns.
        """
        ALLOWED_SNAPSHOT_TYPES = ["REGULATORY_ATTESTATION", "EVENT"]
        FORBIDDEN_TYPES = ["CERTIFICATION", "PERIOD_SEAL", "TRANSFER"]

        if event_type in FORBIDDEN_TYPES:
            raise Exception(f"CRITICAL GOVERNANCE BREACH: Type '{event_type}' forbidden here.")
        
        if event_type not in ALLOWED_SNAPSHOT_TYPES:
            raise Exception(f"SECURITY ALERT: Unauthorized type '{event_type}' attempted.")

        try:
            # Wir nutzen den gov_ledger, der bereits im Service bekannt ist
            block_hash = self.gov_ledger.add_entry(
                event_type,
                payload,
                year,
                lambda h: signing_key.sign(h).signature
            )
            return block_hash
        except Exception as e:
            return None

    def _is_authority_valid(self, actor, role):
        """
        Interne DB-Validierung: Prüft das Mandat gegen die Authority Registry.
        """
        import sqlite3
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        
        # Wir nutzen den Pfad der Governance-DB
        with sqlite3.connect(self.gov_ledger.db_path) as conn:
            query = '''
                SELECT 1 FROM authority_registry 
                WHERE actor = ? AND role = ? 
                AND valid_from <= ? 
                AND (valid_until IS NULL OR valid_until >= ?)
            '''
            res = conn.execute(query, (actor, role, now, now)).fetchone()
            return res is not None
        
def execute_period_seal(
        self,
        reporting_year: int,
        auth_context: dict,
        signer_func
    ) -> dict:
        """
        Block D – Institutional Period Seal.
        Schließt eine Reporting-Periode endgültig.
        Five-Lock: Authority → Completion → Certification Presence → Freeze Hash → Atomic Write
        """
        # ==================================================================
        # SCHLOSS 1 – AUTHORITY (DB-Grounded)
        # ==================================================================
        actor = auth_context.get("user")
        role = auth_context.get("role")

        if not auth_context.get("authorized"):
            return {"status": "ERROR", "message": "AUTHORITY_DENIED: PIN not valid."}

        if role != "OWNER":
            return {"status": "ERROR", "message": f"AUTHORITY_DENIED: Only OWNER may seal. Got '{role}'."}

        if not self._is_authority_valid(actor, role):
            return {"status": "ERROR", "message": f"AUTHORITY_FORGERY_DETECTED: '{actor}' as '{role}' not in Registry."}

        # ==================================================================
        # SCHLOSS 2 – COMPLETION CHECK (Periodensicher)
        # ==================================================================
        try:
            with sqlite3.connect(self.asset_db_path) as conn:
                # Uncertified Reports: status ELIGIBLE und nicht in certified_receipts
                rows = conn.execute(
                    "SELECT report_id, engine_input, receipt_hash FROM telemetry_reports "
                    "WHERE status = 'ELIGIBLE' "
                    "AND receipt_hash NOT IN (SELECT receipt_hash FROM certified_receipts)"
                ).fetchall()

                year_str = str(reporting_year)
                uncertified_in_year = []

                for r_id, engine_json, r_hash in rows:
                    try:
                        period_start = json.loads(engine_json).get(
                            "reporting_period", {}
                        ).get("start", "")
                        if period_start.startswith(year_str):
                            uncertified_in_year.append(r_id)
                    except Exception:
                        # Im Zweifel (Formatfehler) blockieren wir zur Sicherheit
                        uncertified_in_year.append(r_id)

                if uncertified_in_year:
                    return {
                        "status": "ERROR",
                        "message": (
                            f"SEAL_BLOCKED: {len(uncertified_in_year)} uncertified report(s) "
                            f"for {reporting_year} still ELIGIBLE."
                        )
                    }
        except Exception as e:
            return {"status": "ERROR", "message": f"DB_ERROR in completion check: {str(e)}"}

        # ==================================================================
        # SCHLOSS 3 – CERTIFICATION PRESENCE + IDEMPOTENZ
        # ==================================================================
        try:
            with sqlite3.connect(self.asset_db_path) as conn:
                # Prüfen, ob mindestens eine Zertifizierung existiert
                cert_count = conn.execute(
                    "SELECT COUNT(*) FROM ledger_entries "
                    "WHERE block_type = 'CERTIFICATION' AND reporting_year = ?",
                    (reporting_year,)
                ).fetchone()[0]

                if cert_count == 0:
                    return {
                        "status": "ERROR",
                        "message": f"SEAL_BLOCKED: No CERTIFICATION blocks found for {reporting_year}."
                    }

                # Idempotenz: Ist bereits ein Siegel vorhanden?
                existing_seal = conn.execute(
                    "SELECT current_hash FROM ledger_entries "
                    "WHERE block_type = 'PERIOD_SEAL' AND reporting_year = ?",
                    (reporting_year,)
                ).fetchone()

                if existing_seal:
                    return {
                        "status": "ERROR",
                        "message": f"SEAL_BLOCKED: Period {reporting_year} already sealed. Idempotency guard active."
                    }

                # Den Hash der letzten Zertifizierung für das spätere Freeze-Binding holen
                last_cert_hash = conn.execute(
                    "SELECT current_hash FROM ledger_entries "
                    "WHERE block_type = 'CERTIFICATION' AND reporting_year = ? "
                    "ORDER BY seq DESC LIMIT 1",
                    (reporting_year,)
                ).fetchone()[0]

        except Exception as e:
            return {"status": "ERROR", "message": f"DB_ERROR in certification check: {str(e)}"}

        # ==================================================================
        # SCHLOSS 4 – SEAL FREEZE HASH (Chain Binding)
        # ==================================================================
        try:
            # Wir holen den absolut letzten Hash der Kette (unabhängig vom Jahr)
            # um das Siegel an die aktuelle Kettenposition zu fesseln.
            latest_chain_hash = self.asset_ledger.get_latest_hash()
            
            # Der Freeze Hash kombiniert: Jahr + Letzte Zertifizierung + Anzahl + Kettenzustand
            freeze_input = (
                f"{reporting_year}"
                f"|{last_cert_hash}"
                f"|{cert_count}"
                f"|{latest_chain_hash}"
            )
            seal_freeze_hash = hashlib.sha256(freeze_input.encode("utf-8")).hexdigest()
            
        except AttributeError:
            # Falls get_latest_hash() im Ledger fehlt, nutzen wir eine Fallback-Abfrage
            with sqlite3.connect(self.asset_db_path) as conn:
                latest_chain_hash = conn.execute(
                    "SELECT current_hash FROM ledger_entries ORDER BY seq DESC LIMIT 1"
                ).fetchone()[0]
                
            freeze_input = (f"{reporting_year}|{last_cert_hash}|{cert_count}|{latest_chain_hash}")
            seal_freeze_hash = hashlib.sha256(freeze_input.encode("utf-8")).hexdigest()
        except Exception as e:
            return {"status": "ERROR", "message": f"FREEZE_HASH_ERROR: {str(e)}"}

        # ==================================================================
        # SCHLOSS 5 – ATOMIC WRITE
        # ==================================================================
        payload = {
            "reporting_year": reporting_year,
            "total_certifications": cert_count,
            "last_cert_block_hash": last_cert_hash,
            "seal_freeze_hash": seal_freeze_hash,
            "sealed_by": actor,
            "sealed_at_utc": datetime.now(timezone.utc).isoformat()
        }

        try:
            # Wir schreiben den Siegel-Block in die Asset Chain
            block_seq = self.asset_ledger.add_entry(
                block_type="PERIOD_SEAL",
                payload=payload,
                reporting_year=reporting_year,
                signer_func=signer_func
            )
        except Exception as e:
            return {"status": "ERROR", "message": f"LEDGER_WRITE_FAILED: {str(e)}"}

        # Sofortige forensische Verifizierung beider Chains
        try:
            self.asset_ledger.verify_integrity()
        except Exception as e:
            return {"status": "ERROR", "message": f"ASSET_CHAIN_INTEGRITY_FAILURE after seal: {str(e)}"}

        try:
            self.gov_ledger.verify_integrity()
        except Exception as e:
            return {"status": "ERROR", "message": f"GOV_CHAIN_INTEGRITY_FAILURE after seal: {str(e)}"}

        return {
            "status": "SUCCESS",
            "message": f"Period {reporting_year} sealed and both chains verified.",
            "seal_freeze_hash": seal_freeze_hash,
            "block_seq": block_seq,
            "total_certifications": cert_count
        }