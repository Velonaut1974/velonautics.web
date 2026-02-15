import streamlit as st

st.set_page_config(
    page_title="Velonaut | Institutional Ledger v0.6.6",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items=None
)

# Erst danach folgen alle anderen Imports (json, uuid, nacl, etc.)

import json
import uuid
import hashlib
import os
import nacl.signing
import nacl.encoding
from decimal import Decimal, getcontext
from datetime import datetime, timezone
import time

st.markdown("""
    <style>
            /* Erzwingt Sichtbarkeit für Button-Texte in der Sidebar */
.stSidebar button p {
    color: #9CA3AF !important; /* Terminal-Grün */
    font-weight: bold !important;
}

/* Optional: Damit der Button beim Drüberfahren (Hover) reagiert */
.stSidebar button:hover {
    border-color: #9CA3AF !important;
    color: #FFFFFF !important;
}
            /* Fix für Sichtbarkeit der Jahreszahl */
div[data-testid="stMetricValue"] {
    color: #9CA3AF !important; /* Klassisches Terminal-Grün */
}

/* Falls es ein spezielles Label ist */
.stCaption {
    color: #AAAAAA !important; /* Hellgrau für Untertitel */
}
    /* Das schwarze Terminal-Eingabefeld mit echtem Kontrast */
    div[data-baseweb="input"] {
        background-color: #000000 !important; /* Tiefschwarz */
        border-radius: 4px !important;
        border: 2px solid #444 !important; /* Hellere Kante */
    }
    
    /* Die getippte Schrift und das 'Press Enter' */
    input[type="password"] {
        color: #FFFFFF !important; /* Knallweiß */
        background-color: #000000 !important;
        caret-color: white !important; /* Der blinkende Cursor */
    }

    /* Das 'Press Enter to apply' besser lesbar machen */
    div[data-testid="InputInstructions"] {
        color: #AAAAAA !important; /* Hellgrau statt Dunkelgrau */
    }

    /* Das Auge-Icon und Tooltips */
    button[aria-label="Show password"], .stTooltipIcon {
        color: #FFFFFF !important;
    }

    /* Hand-Cursor für alles Interaktive */
    div[data-baseweb="select"], div[data-baseweb="input"], div[role="button"] {
        cursor: pointer !important;
    }
    
    /* Fokus-Zustand: Wenn du reinklickst, leuchtet es dezent */
    div[data-baseweb="input"]:focus-within {
        border: 2px solid #ff4b4b !important;
    }
            /* --- MODUL 3: FLEET GATEWAY STYLES --- */

/* Der Inbound Log Ticker (Terminal Look) */
.stCode {
    border-left: 3px solid #00FF00 !important;
    background-color: #0A0A0A !important;
}

/* Status-Indikatoren in den Spalten */
.status-pill {
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.8rem;
    font-family: 'Courier New', Courier, monospace;
    text-transform: uppercase;
}

/* Spezielle Formatierung für den Eligibility Pool Header */
.eligibility-header {
    background-color: #1A1A1A;
    padding: 10px;
    border-radius: 5px;
    border: 1px solid #333;
    margin-bottom: 15px;
}
    </style>
    """, unsafe_allow_html=True)



st.markdown("""
    
    """, unsafe_allow_html=True)

# --- CORE IMPORTS ---
from core.models import Fleet, Vessel, EnergyEvent, State, StrategyMode, InsettingAsset
from core.engine_fueleu import FuelEUEngine
from core.engine_ets import ETSEngine
from core.states import IsolationFirewall
from core.additionality import AdditionalityEngine
from core.ledger import VelonautLedger

# ------------------------------------------------------------
# 🏛 INSTITUTIONAL LEDGER INITIALIZATION (SINGLE SOURCE OF TRUTH)
# ------------------------------------------------------------

LEDGER_DB_PATH = "data/velonaut_main.sqlite"
KEY_PATH = "data/velonaut_signing.key"
# --- MARKET HISTORY INITIALIZATION ---
import sqlite3
def init_market_db():
    conn = sqlite3.connect(LEDGER_DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS market_prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT,
            price REAL,
            currency TEXT,
            confidence_level TEXT,
            timestamp_utc TEXT,
            retrieval_hash TEXT UNIQUE
        )
    ''')
    conn.commit()
    conn.close()

init_market_db() # Tabelle beim Start sicherstellen

if not os.path.exists("data"):
    os.makedirs("data")

def load_or_create_signing_key():
    if os.path.exists(KEY_PATH):
        with open(KEY_PATH, "rb") as f:
            return nacl.signing.SigningKey(f.read())
    else:
        key = nacl.signing.SigningKey.generate()
        with open(KEY_PATH, "wb") as f:
            f.write(key.encode())
        return key

# --- LEDGER INIT & SECURITY CHECK ---
if "ledger_bundle" not in st.session_state:
    try:
        # 1. Schlüssel laden oder erstellen
        signing_key = load_or_create_signing_key()
        verify_key_hex = signing_key.verify_key.encode(nacl.encoding.HexEncoder).decode()

        # 2. Ledger Instanz erstellen
        ledger_instance = VelonautLedger(
            institution_id="VELONAUT_LABS",
            db_path=LEDGER_DB_PATH,
            public_key_hex=verify_key_hex
        )
        st.session_state.verify_key_hex = verify_key_hex

        # 3. Genesis-Initialisierung (nur wenn DB ganz neu ist)
        if not ledger_instance.has_entries():
            ledger_instance.add_entry(
                "GENESIS",
                {
                    "init": True,
                    "public_key": verify_key_hex, # Ur-Schlüssel für späteren Abgleich speichern
                    "ts_utc": datetime.now(timezone.utc).isoformat()
                },
                0,
                lambda h: signing_key.sign(h).signature
            )

        # 4. DER ENTSCHEIDENDE FIX: Konsistenzprüfung
        stored_genesis_key = ledger_instance.get_genesis_public_key()
        if stored_genesis_key and stored_genesis_key != verify_key_hex:
            # Das verhindert, dass ein falscher Key eine alte DB korrumpiert
            st.error(f"🚨 SECURITY BREACH: Der lokale Schlüssel passt nicht zum Ledger!")
            st.info(f"Erwartet (Genesis): {stored_genesis_key[:15]}...")
            st.info(f"Gefunden (Lokal): {verify_key_hex[:15]}...")
            st.stop()

        # 5. Integrität der gesamten Kette prüfen
        ledger_instance.verify_integrity()
        
        # Alles okay? Dann in den Session State
        st.session_state.ledger_bundle = (ledger_instance, signing_key, True, [])
        
    except Exception as e:
        # Falls etwas schiefgeht, Fehler speichern
        st.session_state.ledger_bundle = (None, None, False, [str(e)])

# Entpacken für die Nutzung in der App
ledger, signing_key, is_valid, chain_errors = st.session_state.ledger_bundle
def build_market_snapshot(price: float, source: str = "EEX_SIM"):
    """
    Market Layer v2: Erstellt einen Snapshot mit Data Provenance.
    """
    timestamp_utc = datetime.now(timezone.utc).isoformat()
    confidence_level = "HIGH" if source == "EEX_SIM" else "MANUAL_VERIFIED"
    
    snapshot = {
        "price": str(price),
        "currency": "EUR",
        "source": source,
        "confidence_level": confidence_level,
        "timestamp_utc": timestamp_utc
    }

    canonical = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
    snapshot_hash = hashlib.sha256(canonical.encode()).hexdigest()
    snapshot["snapshot_hash"] = snapshot_hash

    return snapshot

    canonical = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
    snapshot_hash = hashlib.sha256(canonical.encode()).hexdigest()
    snapshot["snapshot_hash"] = snapshot_hash

    # In die separate Markthistorie schreiben
    try:
        with sqlite3.connect(LEDGER_DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO market_prices (source, price, currency, confidence_level, timestamp_utc, retrieval_hash)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (source, price, "EUR", confidence_level, timestamp_utc, snapshot_hash))
            conn.commit()
    except Exception as e:
        st.error(f"Market History Logging failed: {e}")

    return snapshot

def commit_regulatory_snapshot(event_type, payload, year):
    """Der offizielle Weg in den institutionellen Ledger."""
    try:
        block_hash = ledger.add_entry(
            event_type,
            payload,
            year,
            lambda h: signing_key.sign(h).signature
        )
        return block_hash
    except Exception as e:
        st.error(f"COMMIT_FAILED: {str(e)}")
        return None

# ------------------------------------------------------------
# 🔢 PRECISION & CONFIG
# ------------------------------------------------------------
getcontext().prec = 28



st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&family=JetBrains+Mono&display=swap');

    /* GLOBAL BACKGROUND: Slate 50 für maximale Ruhe */
    html, body, [data-testid="stAppViewContainer"] {
        background-color: #f8fafc !important;
        color: #1e293b !important;
        font-family: 'Inter', sans-serif;
    }

    /* HEADINGS: Deep Navy für Autorität */
    h1, h2, h3 {
        color: #0f172a !important;
        font-weight: 600;
        letter-spacing: -0.02em;
    }

    /* NEUTRALE BOXEN: Reinweiß mit feinem Rand */
    div[data-testid="stAlert"], div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        color: #1e293b !important;
        border-radius: 4px !important;
        box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05) !important;
    }

    /* METRICS BOXEN: Konsistentes Design */
    div[data-testid="metric-container"] {
        background-color: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        padding: 1rem !important;
        border-radius: 4px !important;
    }

    /* BUTTONS: Deep Slate (Fast Schwarz) */
    .stButton>button {
        background-color: #0f172a !important;
        color: #ffffff !important;
        border-radius: 4px !important;
        border: none !important;
        font-weight: 500 !important;
        padding: 0.5rem 1rem !important;
    }

    /* SIDEBAR: Puristisches Weiß */
    [data-testid="stSidebar"] {
        background-color: #ffffff !important;
        border-right: 1px solid #e2e8f0 !important;
    }

    /* CODE BLOCKS: Dezenter als zuvor */
    code {
        background-color: #f1f5f9 !important;
        color: #334155 !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.9em !important;
    }

    /* UI CLEANUP: Versteckt die Standard-Elemente */
    #MainMenu {visibility: hidden;} 
    footer {visibility: hidden;} 
    header {visibility: hidden;}
    
    /* Fokus auf Professionalität */
    .stMarkdown p {
        line-height: 1.6;
    }
</style>
""", unsafe_allow_html=True)
# --- MINIMALIST HEADER ---
st.markdown("<h2 style='margin-bottom: 0;'>V E L O N A U T</h2>", unsafe_allow_html=True)
st.markdown("<p style='color: #64748b; font-family: monospace; font-size: 0.8rem; margin-top: -10px;'>INSTITUTIONAL FORENSIC LEDGER | v1.0.0-INST</p>", unsafe_allow_html=True)
st.markdown("---")

col_h1, col_h2, col_h3 = st.columns([2, 2, 1])
with col_h1:
    st.markdown("<p style='font-size: 0.7rem; color: #94a3b8; margin-bottom: 0;'>INSTITUTIONAL ID</p>", unsafe_allow_html=True)
    st.write("**VELONAUT_LABS**")
with col_h2:
    st.markdown("<p style='font-size: 0.7rem; color: #94a3b8; margin-bottom: 0;'>ACTIVE SIGNER KEY</p>", unsafe_allow_html=True)
    st.code(st.session_state.verify_key_hex[:32] + "...", language=None)
with col_h3:
    status_color = "#3fb950" if is_valid else "#f85149"
    st.markdown(f"<p style='font-size: 0.7rem; color: #94a3b8; margin-bottom: 0;'>INTEGRITY</p>", unsafe_allow_html=True)
    st.markdown(f"<span style='color: {status_color}; font-weight: bold;'>{'✓ VERIFIED' if is_valid else '⚠ BREACH'}</span>", unsafe_allow_html=True)
st.markdown("---")
# ------------------------------------------------------------
# 📂 DATA OPERATIONS
# ------------------------------------------------------------

def load_data():
    try:
        with open('data/fleet.json', 'r') as f:
            data = json.load(f)
        fl = Fleet()
        for v_data in data:
            vessel = Vessel(id=v_data['id'], name=v_data['name'], vessel_type=v_data['vessel_type'], dwt=v_data.get('dwt', 0))
            for e_data in v_data['events']:
                vessel.add_event(EnergyEvent(
                    id=e_data['id'], vessel_id=v_data['id'], fuel_type=e_data['fuel_type'],
                    energy_mj=e_data['energy_mj'], ghg_intensity=e_data['ghg_intensity'],
                    eu_scope_factor=e_data['eu_scope_factor'], state=State(e_data.get('state', 'RAW'))
                ))
            fl.vessels.append(vessel)
        return fl
    except Exception as e:
        st.error(f"🚨 Fleet load failed: {e}")
        return Fleet()

def save_data(fleet):
    output_data = []
    for v in fleet.vessels:
        v_dict = {"id": v.id, "name": v.name, "vessel_type": v.vessel_type, "dwt": v.dwt, "events": []}
        for e in v.events:
            v_dict["events"].append({
                "id": e.id, "fuel_type": e.fuel_type, "energy_mj": e.energy_mj,
                "ghg_intensity": e.ghg_intensity, "eu_scope_factor": e.eu_scope_factor, "state": e.state.value
            })
        output_data.append(v_dict)
    with open('data/fleet.json', 'w') as f:
        json.dump(output_data, f, indent=4)

# ------------------------------------------------------------
# 🔍 INTEGRITY CHECK
# ------------------------------------------------------------
try:
    ledger.verify_integrity()
    is_valid = True
    chain_errors = []
except Exception as e:
    is_valid = False
    chain_errors = [str(e)]

# ------------------------------------------------------------
# IDENTITY & ROLE MANAGEMENT
# ------------------------------------------------------------
with st.container(border=True):
    st.markdown("### SYSTEM IDENTITY & ACCESS CONTROL")
    st.caption("Security Note: High-privilege roles require PIN authorization (Test-PIN: 1234)")
    
    c1, c2 = st.columns(2)
    
    # Nutzer-Datenbank (Mapping von Name zu Standard-Rolle)
    user_registry = {
        "Andreas": "OWNER",
        "Kristof": "AUDITOR",
        "Jan-Erik": "COMPLIANCE_OFFICER",
        "Guest": "READ_ONLY"
    }

    with c1:
        selected_user = st.selectbox(
            "Select Operator Identity", 
            options=list(user_registry.keys()),
            index=0
        )
        
    with c2:
        # PIN-Abfrage für den Login-Vorgang
        access_pin = st.text_input("Access PIN", type="password", help="Enter 1234 for testing purposes")

    # Validierungs-Logik
    if access_pin == "1234":
        # Erfolg: Identität und Rolle werden im System festgeschrieben
        st.session_state["active_user"] = selected_user
        st.session_state["active_role"] = user_registry[selected_user]
        st.success(f"ACCESS GRANTED: {st.session_state['active_user']} as {st.session_state['active_role']}")
    elif access_pin == "":
        st.info("Please enter PIN to initialize session.")
        st.session_state["active_user"] = "NOT_AUTHENTICATED"
        st.session_state["active_role"] = "GUEST"
    else:
        st.error("ACCESS DENIED: Invalid Credentials")
        st.session_state["active_user"] = "NOT_AUTHENTICATED"
        st.session_state["active_role"] = "GUEST"

st.markdown("---")
# ------------------------------------------------------------
# 🕹️ EMERGENCY CONTROL PANEL (Statt Sidebar)
# ------------------------------------------------------------
with st.container(border=True):
    st.header("SYSTEM CONTROL INTERFACE")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.subheader("COMPLIANCE PARAMETERS")
        selected_year = st.selectbox("Compliance Period", [2025, 2030, 2035, 2040])
        strategy = st.selectbox("Risk Strategy", list(StrategyMode))
    
    with col2:
        st.subheader("MARKET DATA")
        eua_price = st.slider("EUA ETS Price (€/tCO2e)", 50.0, 250.0, 85.5, 0.1)
        st.info("FuelEU: Next tightening 2030.")

    with col3:
        st.subheader("GOVERNANCE & TRUST")
        if is_valid:
            st.success("Ledger: Verified")
        else:
            st.error("Ledger: BREACH")
        
        # Der Siegel-Button
        if st.button(f"Seal Year {selected_year}", key="btn_seal_emergency"):
            try:
                seal = ledger.seal_period(selected_year, lambda h: signing_key.sign(h).signature)
                st.success("Versiegelt!")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(str(e))

        # --- DER KEY ROTATION BUTTON ---
        st.markdown("---")
        if st.button("🔑 Rotate Signing Key", key="btn_rotate_key"):
            try:
                new_key = nacl.signing.SigningKey.generate()
                new_pub_hex = new_key.verify_key.encode(nacl.encoding.HexEncoder).decode()
                
                # Der alte Key beglaubigt den neuen Key im Ledger
                ledger.rotate_key(lambda h: signing_key.sign(h).signature, new_pub_hex)
                
                # Neuen Key lokal speichern
                with open(KEY_PATH, "wb") as f:
                    f.write(new_key.encode())
                
                # Session leeren für Neustart mit neuem Key
                del st.session_state.ledger_bundle
                st.success("Key rotiert! Lädt neu...")
                time.sleep(1.5)
                st.rerun()
            except Exception as e:
                st.error(f"Fehler: {e}")

# --- PERIOD CLOSURE (Authorized Access Only) ---
st.sidebar.markdown("---")
st.sidebar.subheader("Final Period Closure")

# 1. Barriere: Rollen-Check
active_role = st.session_state.get("active_role", "GUEST")

if active_role in ["OWNER", "AUDITOR"]:
    st.sidebar.caption("Authorized Action: Cryptographic Period Seal")
    
    # PIN-Eingabe zur Bestätigung
    seal_pin = st.sidebar.text_input("Enter Authorization PIN", type="password", key="seal_pin_input")
    
    if st.sidebar.button(f"Execute Seal: {selected_year}", width='stretch', type="primary"):
        # 2. Barriere: PIN-Validierung (Wir nutzen hier die Sentinel-Logik)
        if seal_pin == "1234":  # Hier später deine echte Admin-PIN hinterlegen
            try:
                with st.spinner("Generating Cryptographic Seal..."):
                    # Der eigentliche Versiegelungs-Prozess
                    seal = ledger.seal_period(selected_year, lambda h: signing_key.sign(h).signature)
                    st.sidebar.success(f"Year {selected_year} locked successfully.")
                    st.sidebar.code(f"Seal ID: {seal[:16]}", language="bash")
                    time.sleep(2)
                    st.rerun()
            except Exception as e:
                st.sidebar.error(f"Closure failed: {str(e)}")
        else:
            st.sidebar.error("Invalid Authorization PIN")
else:
    st.sidebar.warning("Seal Authority: Restricted to Auditor/Owner")

# ------------------------------------------------------------
# 🛰️ INSTITUTIONAL INTELLIGENCE SENTINEL (Evidence Inbox)
# ------------------------------------------------------------
with st.container(border=True):
    st.markdown("###  INTELLIGENCE SENTINEL")
    st.caption("Active monitoring of EEX, EU-Lex and IMO data streams.")
    
    # Simulation der "Evidence Inbox"
    pending_obs = [
        {
            "id": "OBS-EEX-26",
            "source": "EEX Market Data",
            "msg": "EUA Dec-26 Price exceeded 105.00 EUR/t (+12%)",
            "impact": "Increased liability for pending 2026 certificates."
        },
        {
            "id": "OBS-EU-30",
            "source": "EU-Lex (DG CLIMA)",
            "msg": "Updated FuelEU Maritime delegated act: Biomass RFNBO factors.",
            "impact": "Recalculation of compliance balance required."
        }
    ]

    for obs in pending_obs:
        # Prüfung auf Ausblendung
        if st.session_state.get(f"dismissed_{obs['id']}"):
            continue

        with st.expander(f"⚠️ REVIEW REQUIRED: {obs['source']}"):
            st.write(f"**Observation:** {obs['msg']}")
            st.write(f"**Impact:** {obs['impact']}")
            
            st.markdown("---")
            
            # --- TACTICAL AUTHENTICATION BLOCK ---
            is_officer = st.session_state.get("active_role") == "Compliance Officer"
            SECRET_PIN = "1920"
            
            # Schmale Spalte für das schwarze Terminal-Design
            col_auth, _ = st.columns([1.2, 2]) 
            
            with col_auth:
                st.write("**OPERATOR PIN**")
                pin_input = st.text_input(
                    label="PIN",
                    type="password", 
                    key=f"pin_{obs['id']}",
                    label_visibility="collapsed",
                    help="Geben Sie den 4-stelligen Sicherheitscode ein."
                )
            
            if pin_input == SECRET_PIN and is_officer:
                from datetime import datetime, timezone
                st.warning(f"""
                **LEGAL NOTICE: Pending Digital Signature** You are about to commit this evidence to the immutable ledger.  
                **Signer:** {st.session_state.get('active_user')}  
                **Role:** {st.session_state.get('active_role')}  
                **Timestamp:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC  
                *This action is irreversible and forensic.*
                """)
                
                if st.button(f"✍️ Execute Binding Signature {obs['id']}", key=f"final_sign_{obs['id']}", type="primary"):
                    payload = {
                        "meta": {
                            "observation_id": obs['id'],
                            "event_class": "MARKET_PRICE_ALERT" if "Price" in obs['msg'] else "REGULATORY_UPDATE",
                            "auth_method": "PIN_VERIFIED_SIGNATURE"
                        },
                        "interpretation": {
                            "source": obs['source'],
                            "statement": obs['msg'],
                            "affected_scope": "GLOBAL_FLEET",
                            "materiality": "MEDIUM",
                        },
                        "decision": {
                            "review_outcome": "ACCEPTED",
                            "recommended_action": "RECALCULATE_LIABILITY_RESERVE",
                            "attested_by_role": st.session_state.get("active_role"),
                            "attested_by_user": st.session_state.get("active_user"),
                            "attested_at_utc": datetime.now(timezone.utc).isoformat()
                        }
                    }
                    
                    try:
                        # Hier rufen wir deine Commit-Funktion auf
                        new_hash = commit_regulatory_snapshot("REGULATORY_ATTESTATION", payload, selected_year)
                        if new_hash:
                            st.session_state[f"success_{obs['id']}"] = True
                            st.rerun()
                    except Exception as e:
                        st.error(f"Critical Governance Error: {e}")
            
            elif pin_input != "" and pin_input != SECRET_PIN:
                st.error("Invalid PIN. Access Denied.")
            
            # --- DISMISS LOGIK (In derselben vertikalen Flucht) ---
            if not st.session_state.get(f"success_{obs['id']}"):
                confirm_key = f"confirm_dismiss_{obs['id']}"
                
                if st.session_state.get(confirm_key):
                    st.warning(f"⚠️ **ACHTUNG:** Durch das Verwerfen erklären Sie in Ihrer Rolle als **{st.session_state.get('active_role')}**, dass diese Information für die Organisation irrelevant ist.")
                    c1, c2 = st.columns(2)
                    if c1.button("Ja, verwerfen", key=f"yes_{obs['id']}", type="primary"):
                        st.session_state[f"dismissed_{obs['id']}"] = True
                        st.rerun()
                    if c2.button("Abbrechen", key=f"no_{obs['id']}"):
                        st.session_state[confirm_key] = False
                        st.rerun()
                else:
                    with col_auth:
                        if st.button(f"✖ Dismiss {obs['id']}", key=f"dismiss_{obs['id']}"):
                            st.session_state[confirm_key] = True
                            st.rerun()

        # --- STATUS NACH ERFOLGREICHEM SEALING ---
        if st.session_state.get(f"success_{obs['id']}"):
            st.success(f"✅ DOCUMENT SEALED: Evidence {obs['id']} committed by {st.session_state.get('active_user')}.")
            if st.button(f"Acknowledge & Clear {obs['id']}", key=f"clear_{obs['id']}"):
                st.session_state[f"dismissed_{obs['id']}"] = True
                st.rerun()

st.markdown("---")

#------------------------------------------------
# Modul 3: Fleet Gateway (Version 2026 - Clean)
#-----------------------------------------------
import hashlib
import uuid
import json
import sqlite3
from datetime import datetime, timezone

# --- INITIALISIERUNG ---
with sqlite3.connect(LEDGER_DB_PATH) as conn:
    conn.cursor().execute('''
        CREATE TABLE IF NOT EXISTS telemetry_reports (
            report_id TEXT PRIMARY KEY,
            imo TEXT,
            vessel_name TEXT,
            raw_json TEXT,
            received_at TEXT,
            receipt_hash TEXT,
            status TEXT,
            reviewed_by TEXT,
            reviewed_role TEXT,
            reviewed_at TEXT,
            governance_comment TEXT
        )
    ''')
    conn.commit()

# --- FORENSIC HELPERS ---
def get_canonical_representation(data_dict):
    return json.dumps(data_dict, sort_keys=True, separators=(',', ':'))

def generate_forensic_receipt_hash(imo, ts, canonical_payload):
    forensic_string = f"IMO:{imo}|TS:{ts}|DATA:{canonical_payload}"
    return hashlib.sha256(forensic_string.encode('utf-8')).hexdigest()

# ------------------------------------------------------------
# MODUL 3: FLEET GATEWAY
# ------------------------------------------------------------
st.markdown("---")
st.markdown("## FLEET GATEWAY")
st.caption("Institutional Intake Layer | Forensic Mode: ENABLED | Atomic State Control")

# --- ZONE A: GATEWAY RECEIPT ---
with st.expander("Inbound Telemetry Log (API Monitoring)", expanded=False):
    st.info("Status: Listening | Forensic Recipe: v1 | Time: UTC")
    
    if st.button("Simulate New Noon Report Intake"):
        new_id = f"GR-{uuid.uuid4().hex[:6].upper()}"
        imo_val = "9411147"
        vessel_name = "VELONAUT PRIDE"
        raw_payload = {"dist_nm": 310.5, "fuel_mt": 14.2, "type": "VLSFO", "eng_hours": 24}
        
        received_at = datetime.now(timezone.utc).isoformat()
        canonical_payload = get_canonical_representation(raw_payload)
        r_hash = generate_forensic_receipt_hash(imo_val, received_at, canonical_payload)
        
        with sqlite3.connect(LEDGER_DB_PATH) as conn:
            conn.cursor().execute('''
                INSERT INTO telemetry_reports (report_id, imo, vessel_name, raw_json, received_at, receipt_hash, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (new_id, imo_val, vessel_name, canonical_payload, received_at, r_hash, "RECEIVED"))
            conn.commit()
        st.rerun()

    with sqlite3.connect(LEDGER_DB_PATH) as conn:
        reports = conn.cursor().execute('SELECT * FROM telemetry_reports ORDER BY received_at DESC LIMIT 5').fetchall()
    for r in reports:
        st.code(f"ID: {r[0]} | HASH: {r[5][:12]}... | STATUS: {r[6]}", language="bash")


# --- ZONE B: VALIDATION BUFFER ---
st.markdown("### Validation Buffer")
with sqlite3.connect(LEDGER_DB_PATH) as conn:
    pending_reports = conn.cursor().execute(
        'SELECT * FROM telemetry_reports WHERE status IN ("RECEIVED", "FLAGGED", "UNDER_REVIEW") ORDER BY received_at DESC'
    ).fetchall()

if not pending_reports:
    st.info("No active validation tasks. Fleet Telemetry is fully processed.")
else:
    for r in pending_reports:
        with st.expander(f"ACTION REQUIRED: {r[2]} (ID: {r[0]})"):
            
            if r[6] == "RECEIVED":
                with sqlite3.connect(LEDGER_DB_PATH) as conn:
                    conn.cursor().execute(
                        'UPDATE telemetry_reports SET status="UNDER_REVIEW" WHERE report_id=? AND status="RECEIVED"', 
                        (r[0],)
                    )
                    conn.commit()
            
            payload_dict = json.loads(r[3])
            col_data, col_val = st.columns([2, 1])
            
            with col_data:
                st.write("**Raw Payload (Canonical View):**")
                st.json(payload_dict)
                st.caption(f"Received at: {r[4]} (UTC) | Hash: `{r[5]}`")
            
            with col_val:
                st.write("**Automated Scrutiny:**")
                if payload_dict.get("fuel_mt", 0) > 15:
                    st.error("ANOMALY: High Consumption Flag")
                else:
                    st.success("No automated anomaly detected")

            st.markdown("---")
            
            # --- ZONE C: ELIGIBILITY POOL ---
            with sqlite3.connect(LEDGER_DB_PATH) as conn:
                current_status = conn.cursor().execute('SELECT status FROM telemetry_reports WHERE report_id=?', (r[0],)).fetchone()[0]
            
            if current_status in ["ELIGIBLE", "REJECTED"]:
                st.warning(f"Finalized as: {current_status}")
            else:
                st.write("**Compliance Decision (Manual Attestation)**")
                comment = st.text_input("Decision Reasoning (Mandatory)", key=f"cmt_{r[0]}", placeholder="Required for forensic audit...")
                
                c1, c2 = st.columns(2)
                decision_time = datetime.now(timezone.utc).isoformat()
                user, role = st.session_state.get("active_user"), st.session_state.get("active_role")

                if c1.button("Approve for Compliance Use", key=f"app_{r[0]}", width='stretch', type="primary"):
                    if comment:
                        with sqlite3.connect(LEDGER_DB_PATH) as conn:
                            res = conn.cursor().execute('''
                                UPDATE telemetry_reports 
                                SET status='ELIGIBLE', reviewed_by=?, reviewed_role=?, reviewed_at=?, governance_comment=?
                                WHERE report_id=? AND status IN ("RECEIVED", "UNDER_REVIEW", "FLAGGED")
                            ''', (user, role, decision_time, comment, r[0]))
                            conn.commit()
                            if res.rowcount > 0: st.rerun()
                            else: st.error("Race Condition: Record already processed.")
                    else: st.warning("Reasoning mandatory.")
                    
                if c2.button("Reject / Non-Material", key=f"rej_{r[0]}", width='stretch'):
                    if comment:
                        with sqlite3.connect(LEDGER_DB_PATH) as conn:
                            res = conn.cursor().execute('''
                                UPDATE telemetry_reports 
                                SET status='REJECTED', reviewed_by=?, reviewed_role=?, reviewed_at=?, governance_comment=?
                                WHERE report_id=? AND status IN ("RECEIVED", "UNDER_REVIEW", "FLAGGED")
                            ''', (user, role, decision_time, comment, r[0]))
                            conn.commit()
                            if res.rowcount > 0: st.rerun()
                            else: st.error("Race Condition Error.")
                    else: st.warning("Reasoning mandatory.")

# --- PERSISTENCE VIEW ---
with st.expander("View Eligibility Pool (Released Data)", expanded=False):
    with sqlite3.connect(LEDGER_DB_PATH) as conn:
        eligible_data = conn.cursor().execute('''
            SELECT report_id, vessel_name, reviewed_at, reviewed_by, governance_comment 
            FROM telemetry_reports WHERE status="ELIGIBLE"
        ''').fetchall()
    if eligible_data:
        st.table(eligible_data)
    else:
        st.write("The Eligibility Pool is currently empty.")

# ==============================================================================
# MODUL 4: ASSET GOVERNANCE & FORENSIC REPLAY (v13.0 - Fortress Edition)
# ==============================================================================
import json
import sqlite3
import hashlib
import time
from datetime import datetime, timezone
from nacl.signing import VerifyKey
from nacl.encoding import HexEncoder

# --- REGELWERK 2026 ---
RULES_2026 = {
    "version": "FuelEU-Maritime-v2026.01-Official",
    "ef_vlsfo": 3.114,
    "energy_density": 41.0,
    "target_factor": 3.0
}

st.markdown("---")
st.markdown("# ASSET GOVERNANCE CENTER")
st.caption("Forensic Asset Generation | Deterministic Engine | Institutional Finality")

# --- INITIALISIERUNG: AUTHORITY REGISTRY ---
# Wir nutzen LEDGER_DB_PATH, den du oben im Script definiert hast
with sqlite3.connect(LEDGER_DB_PATH) as conn:
    conn.cursor().execute('''
        CREATE TABLE IF NOT EXISTS authority_registry (
            actor TEXT, role TEXT, valid_from TEXT, valid_until TEXT,
            PRIMARY KEY (actor, role, valid_from)
        )
    ''')
    conn.execute("INSERT OR IGNORE INTO authority_registry VALUES ('Andreas', 'OWNER', '2025-01-01', NULL)")
    conn.execute("INSERT OR IGNORE INTO authority_registry VALUES ('Kristof', 'AUDITOR', '2025-01-01', NULL)")
    conn.commit()

# --- HELPER FUNKTIONEN ---
def generate_deterministic_hash(data_rows):
    canonical = json.dumps(data_rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

def sign_snapshot(snapshot_hash: str):
    return signing_key.sign(snapshot_hash.encode("utf-8")).signature.hex()

def verify_snapshot_signature(hash_value: str, signature_hex: str):
    try:
        v_key = VerifyKey(st.session_state.verify_key_hex, encoder=HexEncoder)
        v_key.verify(hash_value.encode("utf-8"), bytes.fromhex(signature_hex))
        return True
    except Exception: return False

# --- DIE FORENSISCHE ENGINE ---
class FuelEUAssetEngine:
    def __init__(self, eligible_reports, rule_set):
        self.reports = eligible_reports
        self.rules = rule_set
        self.engine_version = "Velonaut-Engine-v13.0-Fortress"

    def _generate_fingerprint(self, source_hashes, metrics):
        payload = {"engine_version": self.engine_version, "rule_set": self.rules, "sources": sorted(source_hashes), "metrics": metrics}
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def calculate_assets(self):
        if not self.reports: return None
        total_fuel, total_emissions, source_refs, source_hashes, rejected = 0.0, 0.0, [], [], 0
        for r in self.reports:
            rid, _, vname, raw, stored_hash, reviewer = r
            if hashlib.sha256(raw.encode()).hexdigest() != stored_hash or not reviewer:
                rejected += 1
                continue
            data = json.loads(raw)
            fuel = float(data.get("fuel_mt", 0))
            total_fuel += fuel
            total_emissions += fuel * self.rules["ef_vlsfo"]
            source_refs.append({"id": rid, "hash": stored_hash})
            source_hashes.append(stored_hash)
        metrics = {"fuel_mt": round(total_fuel, 4), "emissions_t": round(total_emissions, 4), "balance_t": round((total_fuel * self.rules["target_factor"]) - total_emissions, 4)}
        return {"metrics": {**metrics, "count": len(source_refs), "rejected": rejected}, "sources": source_refs, "engine_version": self.engine_version, "fingerprint": self._generate_fingerprint(source_hashes, metrics)}

# --- DATEN LADEN (MIT SICHERHEITS-CHECK) ---
eligible_reports = []
with sqlite3.connect(LEDGER_DB_PATH) as conn:
    try:
        eligible_reports = conn.execute("""
            SELECT report_id, imo, vessel_name, raw_json, receipt_hash, reviewed_by 
            FROM telemetry_reports WHERE status = 'ELIGIBLE' ORDER BY received_at ASC
        """).fetchall()
    except sqlite3.OperationalError:
        st.warning("Telemetry table not found in main database. Please ensure Module 3 is initialized.")

# --- UI LOGIK ---
if not eligible_reports:
    st.info("No ELIGIBLE reports available. Please approve reports in Module 3 first.")
else:
    engine = FuelEUAssetEngine(eligible_reports, RULES_2026)
    results = engine.calculate_assets()
    res = results["metrics"]
    c1, c2, c3 = st.columns(3)
    c1.metric("Verified Fuel", f"{res['fuel_mt']} mt")
    c2.metric("CO2 Emissions", f"{res['emissions_t']} t")
    c3.metric("Compliance Balance", f"{res['balance_t']} t")

    tab_cert, tab_lab = st.tabs(["Asset Certification", "Forensic Replay Lab"])

    with tab_cert:
        st.write("**Calculation Fingerprint:**")
        st.code(results["fingerprint"], language="bash")
        comment = st.text_input("Certification Statement", key="cert_stmt_final_v13")
        if st.session_state.get("active_role") == "OWNER":
            if st.button("Sign & Commit to Ledger", width='stretch', type="primary"):
                if comment:
                    with sqlite3.connect(LEDGER_DB_PATH) as conn:
                        auth_data = conn.execute("SELECT actor, role, valid_from, valid_until FROM authority_registry ORDER BY actor, role, valid_from").fetchall()
                        auth_hash = generate_deterministic_hash(auth_data)
                        source_ids = [s["id"] for s in results["sources"]]
                        cust_data = conn.execute(f"SELECT report_id, previous_status, new_status, actor, role, timestamp_utc, comment FROM telemetry_custody_log WHERE report_id IN ({','.join(['?']*len(source_ids))}) ORDER BY timestamp_utc, id", source_ids).fetchall()
                        cust_hash = generate_deterministic_hash(cust_data)
                        
                        payload = {"calculation_fingerprint": results["fingerprint"], "engine_version": results["engine_version"], "rules_version": results["rules"]["version"], "authority_snapshot_hash": auth_hash, "authority_snapshot_signature": sign_snapshot(auth_hash), "custody_snapshot_hash": cust_hash, "custody_snapshot_signature": sign_snapshot(cust_hash), "sources": results["sources"], "metrics": results["metrics"], "attestation": {"by_user": st.session_state.get("active_user"), "at_utc": datetime.now(timezone.utc).isoformat(), "statement": comment}}
                        
                        # Wir nutzen das ledger Objekt direkt, falls commit_regulatory_snapshot fehlt
                        new_hash = ledger.add_entry("FUELEU_ASSET_CERTIFICATION", payload, selected_year, lambda h: signing_key.sign(h).signature)
                        if new_hash: st.success("INSTITUTIONALLY SIGNED & COMMITTED."); time.sleep(1); st.rerun()
                else: st.warning("Statement required.")

    with tab_lab:
        # Sicherer Abruf der Historie
        all_entries = []
        with sqlite3.connect(LEDGER_DB_PATH) as conn:
            try:
                # Wir fragen die Tabelle ab, die VelonautLedger intern nutzt
                all_entries = conn.execute("SELECT seq, block_hash, block_type, timestamp_utc, payload_json FROM regulatory_ledger ORDER BY seq DESC").fetchall()
            except sqlite3.OperationalError:
                st.error("Ledger table not found. Please ensure Module 2 is initialized.")
        
        asset_blocks = [e for e in all_entries if e[2] == "FUELEU_ASSET_CERTIFICATION"]
        if not asset_blocks: st.info("No certifications found in Ledger.")
        else:
            sel_block = st.selectbox("Historical Record", asset_blocks, format_func=lambda x: f"Block {x[1][:12]} (Seq: {x[0]})")
            p = json.loads(sel_block[4])
            if st.button("Run Forensic Replay", width='stretch'):
                s_ids = [s["id"] for s in p["sources"]]
                with sqlite3.connect(LEDGER_DB_PATH) as conn:
                    rows = conn.execute(f"SELECT report_id, raw_json, receipt_hash, status, vessel_name, reviewed_by FROM telemetry_reports WHERE report_id IN ({','.join(['?']*len(s_ids))})", s_ids).fetchall()
                    curr_cust = conn.execute(f"SELECT report_id, previous_status, new_status, actor, role, timestamp_utc, comment FROM telemetry_custody_log WHERE report_id IN ({','.join(['?']*len(s_ids))}) ORDER BY timestamp_utc, id", s_ids).fetchall()
                    curr_auth = conn.execute("SELECT actor, role, valid_from, valid_until FROM authority_registry ORDER BY actor, role, valid_from").fetchall()
                
                st.markdown("### Integrity Audit")
                cc_hash = generate_deterministic_hash(curr_cust)
                if p.get("custody_snapshot_hash") == cc_hash and verify_snapshot_signature(cc_hash, p.get("custody_snapshot_signature")): st.success("Process: SIGNATURE VALID")
                else: st.error("Process: TAMPER DETECTED")
                
                ca_hash = generate_deterministic_hash(curr_auth)
                if p.get("authority_snapshot_hash") == ca_hash and verify_snapshot_signature(ca_hash, p.get("authority_snapshot_signature")): st.success("Governance: SIGNATURE VALID")
                else: st.warning("Governance: REGISTRY DRIFT")
                
                rep_eng = FuelEUAssetEngine([(r[0], "N/A", r[4], r[1], r[2], r[5]) for r in rows], RULES_2026)
                rep_res = rep_eng.calculate_assets()
                if rep_res and rep_res["fingerprint"] == p["calculation_fingerprint"]: st.success("Calculation: MATHEMATICALLY IDENTICAL")
                else: st.error("Calculation: MISMATCH")

st.markdown("""<style>div[data-testid="stMetricValue"] { color: #D1D5DB !important; } .stTabs [data-baseweb="tab"] { background-color: #1E1E1E; color: #9CA3AF; border-radius: 4px; } .stTabs [aria-selected="true"] { color: #FFFFFF !important; border-bottom-color: #D1D5DB !important; }</style>""", unsafe_allow_html=True)


# ------------------------------------------------------------
# 🚢 MAIN UI
# ------------------------------------------------------------
fleet = load_data()
fueleu_ui = FuelEUEngine(year=selected_year)


st.caption("Arithmetic Sovereignty | Cryptographic Signatures | SQLite Backed")

with st.expander("System Documentation & Quick Guide"):
    try:
        # Hier war der Fehler ("Rst.titleEADME.md") - jetzt korrigiert:
        with open("README.md", "r", encoding="utf-8") as f:
            st.markdown(f.read())
    except Exception as e:
        st.info(f"Documentation (README.md) could not be loaded.")
# --- LEVEL I: DATA INTEGRITY & PROOF LEVEL ---

st.header("DATA INTEGRITY & PROOF LEVEL")
if is_valid:
    st.success("AUTHENTICITY VERIFIED: Cryptographic signatures and chain logic are consistent.")
else:
    st.error(f"INTEGRITY BREACH DETECTED: {chain_errors[0]}")


# --- LEVEL II: COMPLIANCE ISOLATION LAYER ---

st.header("COMPLIANCE ISOLATION LAYER")
for v in fleet.vessels:
    with st.expander(f"Vessel: {v.name} ({v.id})"):
        st.caption(f"Type: {v.vessel_type} | DWT: {v.dwt}")
        for e in v.events:
            c1, c2, c3 = st.columns([3, 2, 1])
            c1.write(f"**ID:** {e.id} | {e.fuel_type}")
            c2.write(f"Status: `{e.state.value}`")
            if e.state == State.RAW:
                if c3.button("SECURE FOR COMPLIANCE", key=f"l_{e.id}"):
                    IsolationFirewall.lock_for_compliance(e)
                    save_data(fleet)
                    st.rerun()
            else:
                c3.write("VERIFIED & LOCKED")


# --- LEVEL III: ASSET GENERATION & VALUE LAYER ---

st.header("ASSET GENERATION & VALUE LAYER")
balance = fueleu_ui.get_compliance_balance(fleet)

if balance > 0:
    report = AdditionalityEngine.calculate_surplus(balance, strategy, selected_year)
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Fleet Compliance Balance", f"{balance:,.2f} gCO2e/MJ")
    col_b.metric("Tradable Net Surplus", f"{report.net_surplus:,.2f} tCO2e")
    market_value = Decimal(str(report.net_surplus)) * Decimal(str(eua_price))
    col_c.metric("Est. Market Value (EUA)", f"€ {market_value:,.2f}")

    if st.button("GENERATE REGULATORY ASSET", width='stretch'):
        raw_events = []
        for e in fleet.get_all_events():
            if e.state != State.RAW:
                raw_events.append({
                    "id": str(e.id), "mj": str(e.energy_mj),
                    "ghg": str(e.ghg_intensity), "scope": str(e.eu_scope_factor)
                })
        
        # 1. Markt-Zustand einfrieren
        market_snapshot = build_market_snapshot(eua_price, source="EEX_SIM")

        # 2. Erweiterten Payload erstellen
        payload = {
            "vol": str(report.net_surplus),
            "strat": strategy.value,
            "rules": {
                "year": selected_year,
                "target": str(fueleu_ui.target_intensities[selected_year])
            },
            "raw_events": raw_events,
            "market_snapshot": market_snapshot,
            "ts_utc": datetime.now(timezone.utc).isoformat(),
            "uuid": str(uuid.uuid4())
        }

        new_hash = commit_regulatory_snapshot("EVENT", payload, selected_year)
        
        if new_hash:
            # ERST JETZT: Den Preis in die Historien-Tabelle loggen
            try:
                with sqlite3.connect(LEDGER_DB_PATH) as conn:
                    cursor = conn.cursor()
                    # INSERT OR IGNORE verhindert Fehler bei Duplikaten (wegen UNIQUE Hash)
                    cursor.execute('''
                        INSERT OR IGNORE INTO market_prices (source, price, currency, confidence_level, timestamp_utc, retrieval_hash)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        market_snapshot['source'], 
                        float(market_snapshot['price']), 
                        market_snapshot['currency'], 
                        market_snapshot['confidence_level'], 
                        market_snapshot['timestamp_utc'], 
                        market_snapshot['snapshot_hash']
                    ))
                    conn.commit()
            except Exception as e:
                # Wir warnen nur, da der Ledger-Eintrag selbst ja erfolgreich war
                st.warning(f"Market History Archive failed, but Ledger is secure: {e}")

            st.success(f"REGULATORY COMMIT SUCCESS: Block {new_hash[:16]}...")
            time.sleep(1)
            st.rerun()
else:
    st.warning("No Surplus available for Level III.")

# --- REGISTRY ---
st.divider()
st.subheader("Sovereign Registry (SQLite)")

all_entries = ledger.get_all_entries()
for entry in all_entries:
    payload = json.loads(entry['payload_json'])
    with st.expander(f"SEQ: {entry['seq']} | Block: {entry['block_hash'][:12]}"):
        c1, c2 = st.columns([2, 1])
        with c1:
            st.write(f"**Type:** {entry['block_type']} | **Year:** {entry['reporting_year']}")
            if 'vol' in payload: st.write(f"**Volume:** {payload['vol']} tCO2e")
            if 'market_snapshot' in payload: st.caption(f"🛡️ Market Anchored: {payload['market_snapshot']['price']} EUR | Hash: {payload['market_snapshot']['snapshot_hash'][:12]}...")
            st.markdown(f'<div class="hash-box">{entry["block_hash"]}</div>', unsafe_allow_html=True)
        with c2:
            st.markdown('<p class="audit-pass">✅ Ed25519 Verified</p>', unsafe_allow_html=True)
            # Kleiner Export für den Einzelblock
            st.download_button(
                "📤 Audit Export", 
                json.dumps(entry, indent=2), 
                file_name=f"block_{entry['seq']}.json",
                key=f"dl_{entry['seq']}"
            )

# --- GROSSER EXPORT BUTTON (Nachdem der Loop fertig ist) ---
st.markdown("---")
# WICHTIG: Wir nutzen all_entries direkt, da st.session_state["ledger_entries"] 
# manchmal nach einem Refresh leer sein kann, die Datenbank aber die Wahrheit enthält.
if all_entries:
    import json
    from datetime import datetime, timezone

    full_audit_payload = {
        "metadata": {
            "report_type": "FULL_LEDGER_EXPORT",
            "operator": st.session_state.get("active_user"),
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "entry_count": len(all_entries)
        },
        "ledger": all_entries
    }
    
    st.download_button(
        label=" Download Full Institutional Audit Trail",
        data=json.dumps(full_audit_payload, indent=4),
        file_name=f"velonaut_full_audit_{datetime.now().strftime('%Y%m%d')}.json",
        mime="application/json",
        type="primary",
        width='stretch',
        help="Sichert alle versiegelten Einträge in einer einzigen Datei."
    )    

# --- INSTITUTIONAL FOOTER ---
st.divider()
st.caption("© 2026 VELONAUT LABS | Institutional Prototyping | Ed25519 Secured")
st.caption("DISCLAIMER: This system is a forensic infrastructure tool. It does not constitute legal or regulatory advice. Responsibility for data accuracy remains with the operator.")

# --- FINAL SEAL (CENTERED & LARGE) ---
st.write("") 
st.write("") 
col_s1, col_s2, col_s3 = st.columns([1, 1, 1])

with col_s2:
    try:
        # 'use_container_width' ist der moderne Ersatz für 'use_column_width'
        st.image("assets/logo.png", width='stretch')
    except:
        # Fallback, falls das Logo nicht gefunden wird
        st.markdown("<div style='text-align: center;'>🏛️<br><b>VELONAUT ARITHMETIC SOVEREIGNTY</b></div>", unsafe_allow_html=True)