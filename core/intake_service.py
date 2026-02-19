# ==============================================================================
# VELONAUT | core/intake_service.py
# Module 3: Compliance Data Intake Service
# Extracted from app.py – NO logic changes. Stateless. No Streamlit.
# ==============================================================================

import sqlite3
import hashlib
import json
import uuid
import unicodedata
import csv
import io
import re
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from uuid import uuid4


# ------------------------------------------------------------------------------
# OVD FORMAT DETECTOR
# Extracted from app.py line 899–908. Unchanged.
# ------------------------------------------------------------------------------

class OVDFormatDetector:
    """Strikte Format-Erkennung. Nur 100% Treffer werden akzeptiert."""

    @staticmethod
    def detect(headers: list[str]) -> str:
        h_set = set(headers)
        if {"IMO", "BDN_Number", "Fuel_Type", "Mass"}.issubset(h_set):
            return "BR"
        if {"Date_UTC", "Time_UTC", "Distance", "Event"}.issubset(h_set):
            return "LA"
        raise ValueError(f"OVD_SCHEMA_VIOLATION: Headers {headers} do not match institutional schemas.")


# ------------------------------------------------------------------------------
# OVD PACKAGE PARSER
# Extracted from app.py line 910–1014. Unchanged.
# ------------------------------------------------------------------------------

class OVDPackageParser:
    """
    Final Fortress-Grade Version.
    Strikte IMO-Validierung, Cross-File-Check und Null-Toleranz-Politik.
    """

    @staticmethod
    def sanitize_decimal(value: str) -> Decimal:
        if not value or value.strip() == "":
            raise ValueError("DATA_GAP: Numeric field is empty. Institutional intake requires explicit values (even '0.0').")
        clean_val = value.strip()
        if "," in clean_val:
            raise ValueError(f"LOCALE_ERROR: '{value}' contains a comma. Use international dot format (1234.56).")
        try:
            d_val = Decimal(clean_val)
            return d_val
        except InvalidOperation:
            raise ValueError(f"FORMAT_ERROR: '{value}' is not a valid decimal.")

    @staticmethod
    def parse(uploaded_files) -> dict:
        vessel_imo = ""
        la_fuel_aggregator = {}
        br_fuel_aggregator = {}
        all_dates = []
        total_dist = Decimal("0")

        # 1. Sammel-Phase mit Identitäts-Check
        for file in uploaded_files:
            content = file.getvalue().decode("utf-8-sig")
            reader = csv.DictReader(io.StringIO(content))
            if not reader.fieldnames:
                continue

            f_type = OVDFormatDetector.detect(reader.fieldnames)

            for row in reader:
                # --- STRIKTE IMO VALIDIERUNG ---
                current_imo = row.get("IMO", "").strip()
                if current_imo:
                    if not re.match(r"^\d{7}$", current_imo):
                        raise ValueError(f"IMO_POLICY_VIOLATION: '{current_imo}' is not a valid 7-digit IMO number.")

                    if vessel_imo and current_imo != vessel_imo:
                        raise ValueError(f"IDENTITY_CONFLICT: Package contains multiple IMOs ({vessel_imo} vs {current_imo}).")
                    vessel_imo = current_imo

                if f_type == "LA":
                    if row.get("Date_UTC"):
                        d_str = row["Date_UTC"].strip()
                        datetime.strptime(d_str, "%Y-%m-%d")
                        all_dates.append(d_str)

                    if row.get("Distance"):
                        total_dist += OVDPackageParser.sanitize_decimal(row["Distance"])

                    for key, val in row.items():
                        if key.startswith("Consumption_") and val:
                            f_code = key.replace("Consumption_", "").upper()
                            la_fuel_aggregator[f_code] = la_fuel_aggregator.get(f_code, Decimal("0")) + OVDPackageParser.sanitize_decimal(val)

                if f_type == "BR":
                    if row.get("Fuel_Type") and row.get("Mass"):
                        f_code = row["Fuel_Type"].upper().strip()
                        br_fuel_aggregator[f_code] = br_fuel_aggregator.get(f_code, Decimal("0")) + OVDPackageParser.sanitize_decimal(row["Mass"])

        # 2. Institutional Guards (Die "Letzte Meile")
        if not vessel_imo:
            raise ValueError("VALIDATION_FAILED: No valid 7-digit IMO found in package.")
        if not all_dates:
            raise ValueError("VALIDATION_FAILED: No Date_UTC records found.")

        final_fuel_map = la_fuel_aggregator if la_fuel_aggregator else br_fuel_aggregator

        if not final_fuel_map:
            raise ValueError("MISSING_MATERIAL_DATA: No fuel consumption (LA) or bunker data (BR) found in package.")
        if total_dist <= 0 and la_fuel_aggregator:
            raise ValueError("DISTANCE_POLICY_VIOLATION: Reported voyage distance in LA must be greater than zero.")

        # 3. Deterministisches Sealing
        sorted_dates = sorted(list(set(all_dates)))
        start_date = f"{sorted_dates[0]}T00:00:00Z"
        end_date = f"{sorted_dates[-1]}T23:59:59Z"

        sorted_fuels = []
        for f_code in sorted(final_fuel_map.keys()):
            sorted_fuels.append({
                "code": f_code,
                "mt": str(final_fuel_map[f_code])
            })

        return {
            "vessel": {"imo": vessel_imo},
            "voyage": {
                "start_date": start_date,
                "end_date": end_date,
                "fuel": sorted_fuels,
                "dist_nm": str(total_dist),
                "hours": "0"
            },
            "metadata": {"intake_method": "OVD_PACKAGE_PARSER_V2.3_FORTRESS"}
        }


# ------------------------------------------------------------------------------
# COMPLIANCE GATEWAY
# Extracted from app.py line 1016–1145. Unchanged.
# ------------------------------------------------------------------------------

class ComplianceGateway:
    """
    Modul 3: Compliance Data Gateway (v0.7.4 - Institutional Grade)
    Implementiert die finale ProtocolDecimal-Formel und erzwingt
    Cross-Language-Determinismus.
    """

    TIMESTAMP_REGEX = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
    HASH_64_REGEX = r"^[a-f0-9]{64}$"
    ALLOWED_FUELS = {"HFO", "LFO", "MGO", "LNG", "LPG", "AMMONIA", "METHANOL", "HYDROGEN", "BIO_FUEL", "OTHER"}

    @staticmethod
    def protocol_decimal_string(value, precision=3):
        try:
            d = Decimal(str(value))
            q = Decimal("0." + "0" * (precision - 1) + "1")
            d_q = d.quantize(q, rounding=ROUND_HALF_UP)
            s = format(d_q, 'f')
            if "." in s:
                s = s.rstrip("0").rstrip(".")
            return s
        except (InvalidOperation, TypeError, ValueError):
            raise ValueError(f"Protocol-Decimal-Error: '{value}' is not a valid number.")

    @staticmethod
    def validate_timestamp(ts_string):
        if not re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", ts_string):
            raise ValueError(f"Format-Error: {ts_string}. Expected YYYY-MM-DDTHH:MM:SSZ")
        try:
            datetime.strptime(ts_string, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except ValueError as e:
            raise ValueError(f"Logical Time-Error: {str(e)}")
        return ts_string

    def process_intake(self, raw_payload, dataset_type="OVD_VOYAGE"):
        if dataset_type not in ["OVD_VOYAGE", "DCS_ANNUAL"]:
            raise ValueError(f"Unsupported Dataset Type: {dataset_type}")

        vessel_imo = str(raw_payload.get('vessel', {}).get('imo', ''))
        if not re.match(r"^\d{7}$", vessel_imo):
            raise ValueError(f"IMO-Policy-Violation: '{vessel_imo}' must be exactly 7 digits.")

        start_date = self.validate_timestamp(raw_payload.get('voyage', {}).get('start_date', ''))
        end_date = self.validate_timestamp(raw_payload.get('voyage', {}).get('end_date', ''))

        raw_fuels = raw_payload.get('voyage', {}).get('fuel', [])
        if not raw_fuels:
            raise ValueError("Data-Error: No fuel entries found.")

        fuels_map = {}
        for fuel in raw_fuels:
            f_type = str(fuel.get('code', '')).upper().strip()
            if f_type not in self.ALLOWED_FUELS:
                raise ValueError(f"Fuel-Error: Unauthorized type '{f_type}'.")

            f_mt = Decimal(str(fuel.get('mt')))
            f_desc = str(fuel.get('fuel_other_description', '')).strip() if f_type == "OTHER" else ""

            if f_type == "OTHER" and len(f_desc) < 5:
                raise ValueError("Governance-Error: 'OTHER' requires fuel_other_description.")

            agg_key = (f_type, f_desc)
            fuels_map[agg_key] = fuels_map.get(agg_key, Decimal('0')) + f_mt

        fuels_sorted = []
        for (f_type, f_desc), total_mt in sorted(fuels_map.items()):
            fuels_sorted.append({
                "t": f_type,
                "m": self.protocol_decimal_string(total_mt),
                "d": f_desc
            })

        dist_str = self.protocol_decimal_string(raw_payload.get('voyage', {}).get('dist_nm'))
        time_str = self.protocol_decimal_string(raw_payload.get('voyage', {}).get('hours'))

        verification_ctx = None
        if dataset_type == "DCS_ANNUAL":
            ctx = raw_payload.get('verification_context', {})
            v_soc_date = self.validate_timestamp(ctx.get('soc_issue_date', ''))
            v_flag = str(ctx.get('flag_state', '')).strip().upper()
            v_ref = str(ctx.get('verification_reference', '')).strip()
            v_name = str(ctx.get('verifier', '')).strip()

            if not all([v_ref, v_name, len(v_flag) == 2]):
                raise ValueError("DCS-Error: Incomplete Verification Context.")

            ext_hash = ctx.get('external_cert_hash', '').lower().strip() if ctx.get('external_cert_hash') else None
            if ext_hash and not re.match(self.HASH_64_REGEX, ext_hash):
                raise ValueError("DCS-Hash-Error: External hash must be 64-char hex.")

            verification_ctx = {
                "verifier_name": v_name, "verification_reference": v_ref,
                "flag_state": v_flag, "soc_issue_date": v_soc_date, "external_cert_hash": ext_hash
            }

        canonical_base = {
            "vessel_imo": vessel_imo,
            "period": {"start": start_date, "end": end_date},
            "fuels": fuels_sorted,
            "metrics": {"dist": dist_str, "time": time_str},
            "type": dataset_type
        }
        if verification_ctx:
            canonical_base["verification"] = verification_ctx

        canonical_json = json.dumps(canonical_base, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
        normalized_json = unicodedata.normalize('NFC', canonical_json)
        receipt_hash = hashlib.sha256(normalized_json.encode('utf-8')).hexdigest().lower()

        engine_input = {
            "vessel_imo": vessel_imo,
            "reporting_period": {"start": start_date, "end": end_date},
            "fuels": [{"fuel_type": f["t"], "fuel_mt": Decimal(f["m"])} for f in fuels_sorted],
            "distance_nm": Decimal(dist_str),
            "hours_underway": Decimal(time_str)
        }

        return {
            "dataset_metadata": {
                "dataset_type": dataset_type,
                "receipt_hash": receipt_hash,
                "schema_version": "1.1.4",
                "intake_timestamp": datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                "dataset_id": str(uuid4())
            },
            "engine_input": engine_input,
            "full_audit_payload": {
                "raw_data": raw_payload,
                "hash_input": canonical_base
            }
        }


# ------------------------------------------------------------------------------
# FORENSIC HELPERS
# Extracted from app.py line 1185–1193. Unchanged.
# ------------------------------------------------------------------------------

def get_canonical_representation(data_dict):
    """Erzeugt eine deterministische JSON-Zeichenfolge (sortiert, kompakt)."""
    return json.dumps(data_dict, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def generate_forensic_receipt_hash(imo, ts, canonical_payload):
    """Erzeugt den fälschungssicheren Eingangsstempel nach Fortress-Standard."""
    forensic_string = f"IMO:{imo}|TS:{ts}|DATA:{canonical_payload}"
    return hashlib.sha256(forensic_string.encode('utf-8')).hexdigest()


# ------------------------------------------------------------------------------
# INTAKE SERVICE
# Stateless wrapper. No Streamlit. No session_state.
# Returns structured dicts. UI layer decides what to render.
# ------------------------------------------------------------------------------

class IntakeService:
    """
    Zustandsloser Service für OVD-Intake, Telemetry-DB-Operationen
    und Status-Management.

    Kein st.*. Kein session_state. Nur Return-Values.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._ensure_schema()

    def _ensure_schema(self):
        """
        Idempotentes Schema-Setup.
        Extracted from app.py line 1147–1183. Unchanged.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS telemetry_reports (
                    report_id TEXT PRIMARY KEY,
                    imo TEXT,
                    vessel_name TEXT,
                    raw_json TEXT,
                    canonical_base TEXT,
                    engine_input TEXT,
                    received_at TEXT,
                    receipt_hash TEXT,
                    status TEXT,
                    reviewed_by TEXT,
                    reviewed_role TEXT,
                    reviewed_at TEXT,
                    governance_comment TEXT
                )
            ''')

            columns = [info[1] for info in cursor.execute("PRAGMA table_info(telemetry_reports)").fetchall()]
            if "canonical_base" not in columns:
                cursor.execute("ALTER TABLE telemetry_reports ADD COLUMN canonical_base TEXT")
            if "engine_input" not in columns:
                cursor.execute("ALTER TABLE telemetry_reports ADD COLUMN engine_input TEXT")

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS certified_receipts (
                    receipt_hash TEXT PRIMARY KEY,
                    certificate_block_hash TEXT NOT NULL
                )
            ''')
            conn.commit()

    def process_upload(self, uploaded_files) -> dict:
        """
        Zustandsloser Intake-Prozess mit Idempotenz-Check.
        Verhindert Double-Spending durch Hash-Verifikation vor dem Schreibvorgang.
        """
        try:
            # --- TEIL A: PARSING (KEINE ÄNDERUNG AN DER LOGIK) ---
            if len(uploaded_files) == 1 and uploaded_files[0].name.endswith('.json'):
                uploaded_files[0].seek(0)
                raw_content = uploaded_files[0].getvalue().decode("utf-8")
                if not raw_content.strip():
                    raise ValueError("The uploaded JSON file is empty.")
                raw_data = json.loads(raw_content)
            else:
                for f in uploaded_files:
                    f.seek(0)
                raw_data = OVDPackageParser.parse(uploaded_files)

            # --- TEIL B: HASH-GENERIERUNG (IDENTISCH ZUM GATEWAY) ---
            gateway = ComplianceGateway()
            processed_record = gateway.process_intake(raw_data, "OVD_VOYAGE")
            new_hash = processed_record['dataset_metadata']['receipt_hash']

            # --- TEIL C: IDEMPOTENZ-CHECK (DER GATEKEEPER) ---
            with sqlite3.connect(self.db_path) as conn:
                # Wir prüfen ID und STATUS des existierenden Eintrags
                existing = conn.execute(
                    "SELECT report_id, status FROM telemetry_reports WHERE receipt_hash = ?", 
                    (new_hash,)
                ).fetchone()
                
                if existing:
                    # Rückgabe eines speziellen Status für die UI
                    return {
                        "status": "ALREADY_EXISTS",
                        "message": f"DUPLICATE_HASH: This package is already sealed (ID: {existing[0][:8]}... | STATUS: {existing[1]}).",
                        "dataset_id": existing[0],
                        "receipt_hash": new_hash
                    }

                # --- TEIL D: PERSISTIERUNG (NUR BEI NEUEM HASH) ---
                conn.execute('''
                    INSERT INTO telemetry_reports 
                    (report_id, imo, vessel_name, raw_json, canonical_base, engine_input, received_at, receipt_hash, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    processed_record['dataset_metadata']['dataset_id'],
                    processed_record['engine_input']['vessel_imo'],
                    f"OVD-Package-{processed_record['engine_input']['vessel_imo']}",
                    json.dumps(raw_data),
                    json.dumps(processed_record['full_audit_payload']['hash_input'], default=str),
                    json.dumps(processed_record['engine_input'], default=str),
                    processed_record['dataset_metadata']['intake_timestamp'],
                    new_hash,
                    "ELIGIBLE"
                ))
                conn.commit()

            return {
                "status": "SUCCESS",
                "message": f"OVD Package successfully imported. Receipt Hash: {new_hash[:12]}...",
                "dataset_id": processed_record['dataset_metadata']['dataset_id'],
                "receipt_hash": new_hash
            }

        except Exception as e:
            return {
                "status": "ERROR",
                "message": str(e),
                "dataset_id": None,
                "receipt_hash": None
            }

    def get_pending_reports(self) -> list:
        """
        Gibt alle Reports mit Status RECEIVED | FLAGGED | UNDER_REVIEW zurück.
        Extracted from app.py line 1299–1302.
        """
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.cursor().execute(
                'SELECT * FROM telemetry_reports WHERE status IN ("RECEIVED", "FLAGGED", "UNDER_REVIEW") ORDER BY received_at DESC'
            ).fetchall()
        return rows

    def get_report_status(self, report_id: str) -> str | None:
        """Gibt den aktuellen Status eines Reports zurück."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.cursor().execute(
                'SELECT status FROM telemetry_reports WHERE report_id=?', (report_id,)
            ).fetchone()
        return row[0] if row else None

    def set_under_review(self, report_id: str) -> bool:
        """
        RECEIVED → UNDER_REVIEW.
        Extracted from app.py line 1310–1316.
        """
        with sqlite3.connect(self.db_path) as conn:
            res = conn.cursor().execute(
                'UPDATE telemetry_reports SET status="UNDER_REVIEW" WHERE report_id=? AND status="RECEIVED"',
                (report_id,)
            )
            conn.commit()
        return res.rowcount > 0

    def update_status(self, report_id: str, new_status: str, user: str, role: str, comment: str) -> bool:
        """
        Status-Update mit Governance-Metadaten.
        Extracted from app.py line 1349–1383.

        new_status: "ELIGIBLE" | "REJECTED"
        Returns True on success, False on race condition or invalid transition.
        """
        if new_status not in ("ELIGIBLE", "REJECTED"):
            return False

        decision_time = datetime.now(timezone.utc).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            res = conn.cursor().execute('''
                UPDATE telemetry_reports
                SET status=?, reviewed_by=?, reviewed_role=?, reviewed_at=?, governance_comment=?
                WHERE report_id=? AND status IN ("RECEIVED", "UNDER_REVIEW", "FLAGGED")
            ''', (new_status, user, role, decision_time, comment, report_id))
            conn.commit()

        return res.rowcount > 0

    def get_recent_reports(self, limit: int = 5) -> list:
        """Gibt die letzten N Reports zurück (für Activity Log)."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.cursor().execute(
                'SELECT * FROM telemetry_reports ORDER BY received_at DESC LIMIT ?', (limit,)
            ).fetchall()
        return rows

    def get_eligible_reports(self) -> list:
        """Gibt alle ELIGIBLE Reports mit klaren Spalten für die UI zurück."""
        with sqlite3.connect(self.db_path) as conn:
            # Wir fragen exakt 5 Spalten ab, inklusive des Receipt Hash
            rows = conn.cursor().execute('''
                SELECT 
                    report_id, 
                    receipt_hash, 
                    vessel_name, 
                    reviewed_at, 
                    reviewed_by
                FROM telemetry_reports 
                WHERE status="ELIGIBLE"
                ORDER BY reviewed_at DESC
            ''').fetchall()
        return rows
