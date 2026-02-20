import sqlite3
import json
import hashlib
from decimal import Decimal

class AssetEngine:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_fleet_snapshot(self, reporting_year: str) -> dict:
        """
        Aggregiert alle ELIGIBLE Reports eines Jahres zu einem deterministischen Snapshot.
        Stabile Sortierung via receipt_hash COLLATE BINARY garantiert identische Fingerprints.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                # ORDER BY COLLATE BINARY stellt sicher, dass die Sortierung unabhängig vom System-Locale ist
                cursor = conn.execute('''
                    SELECT report_id, engine_input, receipt_hash 
                    FROM telemetry_reports 
                    WHERE status = 'ELIGIBLE' 
                    AND received_at LIKE ?
                    ORDER BY receipt_hash COLLATE BINARY ASC
                ''', (f"{reporting_year}%",))
                
                rows = cursor.fetchall()

            if not rows:
                return {
                    "count": 0,
                    "verified_fuel_mt": 0.0,
                    "co2_emissions_t": 0.0,
                    "compliance_balance_t": None,
                    "calculation_fingerprint": None
                }

            total_fuel = Decimal('0.0')
            total_co2 = Decimal('0.0')
            report_ids = []
            hash_accumulator = hashlib.sha256()

            for r_id, engine_json, r_hash in rows:
                data = json.loads(engine_json)
                
                # Aggregation via Decimal zur Vermeidung von Float-Leaks
                total_fuel += Decimal(str(data.get('fuel_mt', 0)))
                total_co2 += Decimal(str(data.get('co2_emissions_t', 0)))
                
                # Deterministische Hash-Verkettung basierend auf receipt_hash
                hash_accumulator.update(r_hash.encode('utf-8'))
                report_ids.append(r_id)

            return {
                "reporting_year": reporting_year,
                "count": len(rows),
                "verified_fuel_mt": float(total_fuel),
                "co2_emissions_t": float(total_co2),
                "compliance_balance_t": None,
                "calculation_fingerprint": hash_accumulator.hexdigest(),
                "involved_reports": report_ids
            }

        except Exception as e:
            return {"error": str(e)}
        
    @staticmethod
    def log_market_price(db_path, price_data): # Hier db_path hinzufügen
        """
        Archiviert Marktdaten in der market_prices Tabelle.
        """
        import sqlite3
        with sqlite3.connect(db_path) as conn:
            
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO market_prices 
                (source, price, currency, confidence_level, timestamp_utc, retrieval_hash)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                price_data['source'],
                price_data['price'],
                price_data['currency'],
                price_data['confidence_level'],
                price_data['timestamp_utc'],
                price_data['retrieval_hash']
            ))
            conn.commit()