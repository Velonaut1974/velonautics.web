import hashlib
from datetime import datetime, timezone

class CertificationService:
    def __init__(self, ledger_instance, engine_instance):
        self.ledger = ledger_instance
        self.engine = engine_instance

    def create_certification(self, reporting_year: str, signer_func):
        """
        Erzeugt einen CERTIFICATION-Block basierend auf dem Engine-Snapshot.
        Nutzt explizite Separatoren im Freeze-Hash fuer absolute Eindeutigkeit.
        """

        # 1. Re-Calculation Pflicht
        snapshot = self.engine.get_fleet_snapshot(reporting_year)

        if "error" in snapshot:
            return {"status": "ERROR", "message": snapshot["error"]}

        if snapshot["count"] == 0:
            return {"status": "ERROR", "message": "No eligible reports for certification."}

        if not snapshot["calculation_fingerprint"]:
            return {"status": "ERROR", "message": "Snapshot fingerprint missing."}

        # 2. Snapshot Freeze Hash (Schloss 4 Vorbereitung)
        # Explizite Trennung durch '|' verhindert String-Kollisionen
        freeze_input = f"{snapshot['calculation_fingerprint']}|{snapshot['count']}|{reporting_year}"
        freeze_hash = hashlib.sha256(freeze_input.encode("utf-8")).hexdigest()

        # 3. Payload-Normierung
        payload = {
            "reporting_year": reporting_year,
            "fleet_report_count": snapshot["count"],
            "verified_fuel_mt": snapshot["verified_fuel_mt"],
            "co2_emissions_t": snapshot["co2_emissions_t"],
            "calculation_fingerprint": snapshot["calculation_fingerprint"],
            "snapshot_freeze_hash": freeze_hash,
            "involved_reports": snapshot["involved_reports"],
            "certified_at_utc": datetime.now(timezone.utc).isoformat()
        }

        try:
            # 4. Ledger Write
            self.ledger.add_entry(
                block_type="CERTIFICATION",
                payload=payload,
                reporting_year=int(reporting_year),
                signer_func=signer_func
            )

            return {
                "status": "SUCCESS",
                "message": "Certification block written to ledger.",
                "freeze_hash": freeze_hash
            }

        except Exception as e:
            return {"status": "ERROR", "message": str(e)}