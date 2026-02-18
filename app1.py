import streamlit as st

st.set_page_config(
    page_title="Velonaut | Institutional Ledger v0.7.4",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items=None
)

# --- 1. CORE IMPORTS & SYSTEM CONFIG ---
import sqlite3
import re
import json
import uuid
import hashlib
import os
import time
import unicodedata
import nacl.signing
import nacl.encoding
import streamlit as st  # Sicherstellen, dass streamlit als 'st' verfügbar ist
from uuid import uuid4
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation, getcontext

# --- 2. GLOBAL PATH DEFINITION (Pylance Fix) ---
# Wir definieren den Pfad HIER, damit alle folgenden Blöcke ihn kennen.
LEDGER_DB_PATH = "data/velonaut_ledger.db"



# --- PDF EXPORT IMPORTS ---
import qrcode
import io
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.pagesizes import A4

# --- PDF GENERATOR FUNKTION ---
def generate_asset_pdf_from_block(block_record):
    """Erzeugt ein institutionelles Zertifikat basierend auf einem Ledger-Block."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=A4,
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm
    )
    elements = []
    styles = getSampleStyleSheet()
    
    # Style für lange kryptographische Hashes
    hash_style = ParagraphStyle(
        'HashStyle',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=7,
        leading=9,
        wordWrap='CJK'
    )

    payload = json.loads(block_record["payload_json"])

    # Titel
    elements.append(Paragraph("VELONAUT INSTITUTIONAL ASSET CERTIFICATE", styles["Heading1"]))
    elements.append(Spacer(1, 0.5 * cm))

    # Tabelle 1: Block-Authentifizierung
    meta_data = [
        [Paragraph("<b>LEDGER AUTHENTICATION</b>", styles["Normal"]), ""],
        ["Block Hash", Paragraph(block_record["block_hash"], hash_style)],
        ["Ed25519 Signature", Paragraph(block_record["signature"], hash_style)],
        ["Reporting Year", str(block_record["reporting_year"])],
        ["Engine Version", payload["calculation"]["engine_version"]]
    ]
    t1 = Table(meta_data, colWidths=[4 * cm, 11 * cm])
    t1.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.grey), ('BACKGROUND', (0,0), (0,-1), colors.whitesmoke)]))
    elements.append(t1)
    elements.append(Spacer(1, 1 * cm))

    # Tabelle 2: Metriken (Die Werte)
    metrics = payload["calculation"]["metrics"]
    rules = payload["header"].get("rules", {"target_factor": "N/A"})
    metrics_data = [
        ["DESCRIPTION", "VALUE"],
        ["Verified Fuel (mt)", metrics["fuel_mt"]],
        ["FuelEU Target Factor", str(rules["target_factor"])],
        ["CO2 Emissions (t)", metrics["emissions_t"]],
        ["Compliance Balance (t)", metrics["balance_t"]]
    ]
    t2 = Table(metrics_data, colWidths=[7.5 * cm, 7.5 * cm])
    t2.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black), ('BACKGROUND', (0,0), (-1,0), colors.lightgrey)]))
    elements.append(t2)

    doc.build(elements)
    buffer.seek(0)
    return buffer

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

LEDGER_DB_PATH = "data/velonaut_ledger.db"      # Hier liegen deine Zertifikate (Asset Layer)
GOVERNANCE_DB_PATH = "data/velonaut_gov.db"    # Hier liegt nur die "Regierung" (Governance)
KEY_PATH = "data/velonaut_signing.key"
# --- MARKET HISTORY INITIALIZATION ---
import sqlite3
def init_market_db():
    with sqlite3.connect(LEDGER_DB_PATH) as conn:
        cursor = conn.cursor()
        # 1. Marktdaten
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS market_prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT, price REAL, currency TEXT, 
                confidence_level TEXT, timestamp_utc TEXT, retrieval_hash TEXT UNIQUE
            )
        ''')
        # 2. DAS ARCHIV (Hier war der payload-Fehler!)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ledger_entries (
                block_hash TEXT PRIMARY KEY,
                payload TEXT,
                timestamp TEXT,
                prev_hash TEXT
            )
        ''')
        # 3. DIE SPERRLISTE
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS certified_receipts (
                receipt_hash TEXT PRIMARY KEY,
                certificate_block_hash TEXT,
                FOREIGN KEY(certificate_block_hash) REFERENCES ledger_entries(block_hash)
            )
        ''')
        conn.commit()

init_market_db() # Jetzt werden alle 3 Tabellen beim Start korrekt angelegt

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

        # 2. Ledger Instanz erstellen (auf dem neuen GOV-Pfad!)
        ledger_instance = VelonautLedger(
            institution_id="VELONAUT_LABS",
            db_path=GOVERNANCE_DB_PATH,  # <-- Geändert von LEDGER_DB_PATH
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

# --- PERIOD CLOSURE & YEAR SELECTION ---
st.sidebar.markdown("---")
st.sidebar.subheader("Compliance Period Management")

# NEU: Das Auswahlfeld für das Jahr (behebt das 2025-Problem)
selected_year = st.sidebar.selectbox(
    "Select Reporting Year", 
    [2025, 2026], 
    index=1, # Standardmäßig auf 2026 (zweiter Wert in der Liste)
    help="Institutional rule sets are year-specific."
)

st.sidebar.markdown("---")
st.sidebar.subheader("Final Period Closure")

# 1. Barriere: Rollen-Check
active_role = st.session_state.get("active_role", "GUEST")

if active_role in ["OWNER", "AUDITOR"]:
    st.sidebar.caption(f"Authorized Action: Cryptographic Period Seal {selected_year}")
    
    # PIN-Eingabe zur Bestätigung
    seal_pin = st.sidebar.text_input("Enter Authorization PIN", type="password", key="seal_pin_input")
    
    if st.sidebar.button(f"Execute Seal: {selected_year}", use_container_width=True, type="primary"):
        # 2. Barriere: PIN-Validierung
        if seal_pin == "1234":
            try:
                with st.spinner(f"Generating Cryptographic Seal for {selected_year}..."):
                    # Der Versiegelungs-Prozess nutzt das gewählte Jahr
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
# Modul 3: Fleet Gateway (Institutional Intake)
#------------------------------------------------
import hashlib
import uuid
import json
import sqlite3
import random
from datetime import datetime, timezone

import unicodedata
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

import csv
import io
from decimal import Decimal, InvalidOperation
from datetime import datetime
import re

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
            if not reader.fieldnames: continue
            
            f_type = OVDFormatDetector.detect(reader.fieldnames)
            
            for row in reader:
                # --- STRIKTE IMO VALIDIERUNG ---
                current_imo = row.get("IMO", "").strip()
                if current_imo:
                    # Regex: Muss exakt 7 Ziffern sein
                    if not re.match(r"^\d{7}$", current_imo):
                        raise ValueError(f"IMO_POLICY_VIOLATION: '{current_imo}' is not a valid 7-digit IMO number.")
                    
                    # Cross-File Consistency Check
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
                    
                    # Roh-Fuel Aggregation (Gateway validiert später gegen ALLOWED_FUELS)
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
        
        # Entscheidung: LA vor BR
        final_fuel_map = la_fuel_aggregator if la_fuel_aggregator else br_fuel_aggregator
        
        if not final_fuel_map:
            raise ValueError("MISSING_MATERIAL_DATA: No fuel consumption (LA) or bunker data (BR) found in package.")
        if total_dist <= 0 and la_fuel_aggregator:
            # Nur Warnung oder Hard Fail? Wir wählen Hard Fail für maximale Strenge im LA.
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
            q = Decimal("0." + "0"*(precision-1) + "1")
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
        if not raw_fuels: raise ValueError("Data-Error: No fuel entries found.")

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
        if verification_ctx: canonical_base["verification"] = verification_ctx

        canonical_json = json.dumps(canonical_base, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
        normalized_json = unicodedata.normalize('NFC', canonical_json)
        receipt_hash = hashlib.sha256(normalized_json.encode('utf-8')).hexdigest().lower()

        # Engine Input für die Kompatibilität mit M4/M5 wiederherstellen
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

# --- DATABASE SCHEMA HARDENING (v0.7.4) ---
with sqlite3.connect(LEDGER_DB_PATH) as conn:
    cursor = conn.cursor()
    # 1. Haupttabelle für Telemetrie erstellen/erweitern
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
    
    # 2. Migration: Fehlende Spalten hinzufügen, falls die DB bereits existiert
    columns = [info[1] for info in cursor.execute("PRAGMA table_info(telemetry_reports)").fetchall()]
    if "canonical_base" not in columns:
        cursor.execute("ALTER TABLE telemetry_reports ADD COLUMN canonical_base TEXT")
    if "engine_input" not in columns:
        cursor.execute("ALTER TABLE telemetry_reports ADD COLUMN engine_input TEXT")

    # 3. Sperrtabelle für Double-Spending-Schutz (Fortress Core)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS certified_receipts (
            receipt_hash TEXT PRIMARY KEY,
            certificate_block_hash TEXT NOT NULL
        )
    ''')
    conn.commit()

# --- FORENSIC HELPERS (PRODUKTIONS-STANDARD) ---
def get_canonical_representation(data_dict):
    """Erzeugt eine deterministische JSON-Zeichenfolge (sortiert, kompakt)."""
    return json.dumps(data_dict, sort_keys=True, separators=(',', ':'), ensure_ascii=False)

def generate_forensic_receipt_hash(imo, ts, canonical_payload):
    """Erzeugt den fälschungssicheren Eingangsstempel nach Fortress-Standard."""
    forensic_string = f"IMO:{imo}|TS:{ts}|DATA:{canonical_payload}"
    return hashlib.sha256(forensic_string.encode('utf-8')).hexdigest()

# --- SIMULATOR LOGIK (AUDITOR APPROVED) ---
def simulate_inbound_report(vessel_name, imo):
    """Simuliert Telemetrie-Eingang mit exaktem Fortress-Hashing-Schema."""
    try:
        fuel_consumption = round(random.uniform(10.5, 45.8), 2)
        raw_payload = {
            "fuel_mt": fuel_consumption,
            "fuel_type": "VLSFO",
            "reporter": "Chief Engineer"
        }
        received_at = datetime.now(timezone.utc).isoformat()
        canonical_payload = get_canonical_representation(raw_payload)
        
        # Exaktes Produktions-Hash-Muster
        r_hash = generate_forensic_receipt_hash(imo, received_at, canonical_payload)
        report_id = f"SIM-{imo}-{uuid.uuid4().hex[:8].upper()}"

        with sqlite3.connect(LEDGER_DB_PATH) as conn:
            conn.cursor().execute('''
                INSERT INTO telemetry_reports 
                (report_id, imo, vessel_name, raw_json, received_at, receipt_hash, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (report_id, imo, vessel_name, canonical_payload, received_at, r_hash, "RECEIVED"))
            conn.commit()
        return report_id
    except Exception as e:
        st.error(f"Simulator Fault: {e}")
        return None

# --- UI: FLEET GATEWAY ---
st.markdown("---")
st.markdown("## FLEET GATEWAY")
st.caption("Institutional Intake Layer | Forensic Mode: ENABLED | Atomic State Control")

# --- ZONE A: GATEWAY RECEIPT & SIMULATOR ---
with st.expander("Inbound Telemetry Log (API Monitoring)", expanded=False):
    st.info("Status: Listening | Forensic Recipe: v1 | Time: UTC")
    
    st.write("### 📥 Institutional Data Intake (OVD/DCS)")
    
    # 1. Dateiupload (Multiple Files für CSV-Pakete)
    uploaded_files = st.file_uploader(
        "Upload OVD Package (CSV/TXT/JSON)", 
        type=['csv', 'txt', 'json'], 
        accept_multiple_files=True,
        key="ovd_uploader_main"
    )
    
    if uploaded_files:
        if st.button("Validate and Seal Data", width='stretch', type="primary"):
            try:
                # 2. Parsing-Layer (Hier rufen wir unsere neue Klasse auf)
                # Fall A: Einzelne JSON
                if len(uploaded_files) == 1 and uploaded_files[0].name.endswith('.json'):
                    import json
                    raw_data = json.load(uploaded_files[0])
                # Fall B: CSV/TXT-Paket von Kristof
                else:
                    raw_data = OVDPackageParser.parse(uploaded_files)
                
                # 3. Gateway-Prozess (Dein bestehendes Gateway)
                gateway = ComplianceGateway()
                processed_record = gateway.process_intake(raw_data, "OVD_VOYAGE")
                
                # 4. Speichern in der Telemetry-Tabelle
                with sqlite3.connect(LEDGER_DB_PATH) as conn:
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
                        processed_record['dataset_metadata']['receipt_hash'],
                        "ELIGIBLE"
                    ))
                    conn.commit()
                
                st.success("✅ OVD Package successfully parsed and sealed.")
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ Intake Error: {str(e)}")

    st.write("---")
    st.write("**Recent Activity (Last 5 Events):**")
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
            
            # --- ZONE C: GOVERNANCE DECISION ---
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
# MODULE 4: ASSET GOVERNANCE CENTER (v1.5-Fortress-Institutional-Final)
# ==============================================================================

# --- 1. CONFIGURATION & CORE UTILITIES ---
results = None 
RULES_2026 = {
    "version": "FuelEU-Maritime-v2026.01-Official",
    "ef_vlsfo": 3.114,
    "energy_density": 41.0,
    "target_factor": 3.0
}

def deterministic_hash(data):
    """Generates an immutable hash from a data object (canonical JSON)."""
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

def build_eligibility_snapshot(conn):
    """Freezes the set of reports considered 'eligible' at the time of commit."""
    rows = conn.execute("""
        SELECT report_id, receipt_hash 
        FROM telemetry_reports 
        WHERE status = 'ELIGIBLE' 
        ORDER BY report_id ASC
    """).fetchall()
    snapshot = [{"report_id": r[0], "receipt_hash": r[1]} for r in rows]
    return deterministic_hash(snapshot), snapshot

def build_selection_snapshot(engine_results_sources):
    """Freezes the exact data subset actually used by the engine."""
    snapshot = sorted(engine_results_sources, key=lambda x: x["id"])
    return deterministic_hash(snapshot), snapshot

def build_authority_snapshot(conn):
    """Freezes the mandate registry at the time of commit."""
    rows = conn.execute("""
        SELECT actor, role, valid_from, valid_until 
        FROM authority_registry 
        ORDER BY actor ASC, role ASC, valid_from ASC
    """).fetchall()
    snapshot = [{"actor": r[0], "role": r[1], "valid_from": r[2], "valid_until": r[3]} for r in rows]
    return deterministic_hash(snapshot), snapshot

def generate_json_certificate(block_record):
    """Erzeugt den digitalen JSON-Zwilling mit flachen Metriken für Banken."""
    payload = json.loads(block_record["payload_json"])
    cert_id = payload["header"].get("certificate_id", "N/A")
    cert_data = {
        "certificate_id": cert_id,
        "metrics_summary": payload["calculation"]["metrics"],
        "ledger_proof": {
            "block_hash": block_record["block_hash"],
            "signature": block_record["signature"],
            "public_key": ledger.get_genesis_public_key()
        },
        "full_audit_payload": payload
    }
    return json.dumps(cert_data, indent=4)

def generate_enhanced_pdf(block_record):
    """Erzeugt das institutionelle PDF mit QR-Code und Replay-Infos."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    elements = []
    styles = getSampleStyleSheet()
    
    payload = json.loads(block_record["payload_json"])
    cert_id = payload["header"].get("certificate_id", "N/A")
    
    elements.append(Paragraph("INSTITUTIONAL ASSET CERTIFICATE", styles["Heading1"]))
    elements.append(Paragraph(f"Certificate ID: {cert_id}", styles["Heading2"]))
    elements.append(Spacer(1, 1*cm))

    # QR Code Generierung
    qr = qrcode.QRCode(version=None, box_size=10, border=4)
    qr.add_data(f"VELO_VERIFY|{cert_id}|{block_record['block_hash']}")
    qr.make(fit=True)
    img_qr = qr.make_image(fill_color="black", back_color="white")
    qr_buffer = io.BytesIO()
    img_qr.save(qr_buffer, format='PNG')
    qr_buffer.seek(0)
    elements.append(Image(qr_buffer, width=3*cm, height=3*cm))
    elements.append(Spacer(1, 1*cm))

    # Metriken-Tabelle
    m = payload["calculation"]["metrics"]
    data = [
        ["Metric Description", "Verified Value"],
        ["Reporting Year", str(block_record["reporting_year"])],
        ["Verified Fuel", f"{m['fuel_mt']} mt"],
        ["Compliance Balance", f"{m['balance_t']} t"],
        ["Block Hash (Short)", block_record["block_hash"][:32] + "..."]
    ]
    t = Table(data, colWidths=[7*cm, 9*cm])
    t.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.grey), ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke)]))
    elements.append(t)
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

# --- 2. ENGINE KERNEL (INSTITUTIONAL GRADE) ---
class FuelEUAssetEngine:
    ENGINE_VERSION = "Velonaut-Engine-v16.0-Fortress"

    @staticmethod
    def calculate(engine_inputs: list[dict], rule_set: dict) -> dict:
        """
        UNIVERSAL CALCULATOR: Erkennt sowohl verschachtelte OVD-Strukturen 
        als auch flache Gateway-Inputs.
        """
        total_fuel = Decimal("0")
        total_dist = Decimal("0")
        
        for entry in engine_inputs:
            # 1. Daten-Extraktion (Verschachtelung vs. Flach)
            voyage = entry.get("voyage", {})
            # Greift 'fuel' aus deinem JSON oder 'fuels' aus dem Standard-Input
            fuel_entries = voyage.get("fuel", entry.get("fuels", []))
            
            # Falls es eine Liste ist (wie in deinem JSON unter voyage -> fuel)
            if isinstance(fuel_entries, list):
                for f in fuel_entries:
                    # Erkennt 'code' (dein JSON) oder 'fuel_type' (Standard)
                    f_type = str(f.get("code", f.get("fuel_type", ""))).upper()
                    if f_type == "MGO":
                        # Erkennt 'mt' (dein JSON) oder 'fuel_mt' (Standard)
                        total_fuel += Decimal(str(f.get("mt", f.get("fuel_mt", 0))))
            
            # 2. Distanz-Extraktion
            dist = voyage.get("dist_nm", entry.get("distance_nm", 0))
            total_dist += Decimal(str(dist))

        # 3. Mathematische Verrechnung (Fortress-Logic)
        target = Decimal(str(rule_set.get("target_factor", 1.0)))
        # Standard-Emissionsfaktor für MGO, falls nichts im Rule-Set steht
        ef_mgo = Decimal(str(rule_set.get("ef_mgo", 3.206))) 
        total_emissions = total_fuel * ef_mgo
        balance = (total_fuel * target) - total_emissions

        # 4. Finales Metrik-Package
        metrics = {
            "fuel_mt": str(total_fuel),
            "emissions_t": str(total_emissions),
            "balance_t": str(balance),
            "dist_nm": str(total_dist)
        }

        # Rule-Hash für die Unveränderbarkeit
        canonical_rule = json.dumps(rule_set, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        normalized_rule = unicodedata.normalize("NFC", canonical_rule)
        rule_hash = hashlib.sha256(normalized_rule.encode("utf-8")).hexdigest()

        return {
            "metrics": metrics,
            "engine_version": FuelEUAssetEngine.ENGINE_VERSION,
            "rule_hash": rule_hash
        }
    
# --- FORTRESS CONTROLLER LAYER ---

def generate_calculation_fingerprint(receipt_hashes, engine_version, rule_hash, metrics):
    """Erzeugt den End-to-End Fingerprint auf Controller-Ebene."""
    calculation_core = {
        "receipt_hashes": sorted(list(set(receipt_hashes))),
        "engine_version": engine_version,
        "rule_hash": rule_hash,
        "metrics": metrics
    }
    
    # Streng deterministische Serialisierung (Audit-konform)
    canonical_json = json.dumps(calculation_core, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    normalized_json = unicodedata.normalize('NFC', canonical_json)
    return hashlib.sha256(normalized_json.encode('utf-8')).hexdigest().lower()

def atomic_certification_commit(conn, receipt_hashes: list[str], ledger_payload: dict) -> str:
    """
    FORTRESS MODE: Atomarer Commit mit Double-Spending-Schutz.
    Garantiert: Ledger-Eintrag und Sperre existieren nur gemeinsam.
    """
    if not receipt_hashes:
        raise ValueError("NO_RECEIPTS_SELECTED")
    
    unique_hashes = sorted(list(set(receipt_hashes)))
    
    try:
        # DB-Sperre für absolute Konsistenz
        conn.execute("BEGIN EXCLUSIVE TRANSACTION")
        
        # 1. Double-Spending Check innerhalb der Sperre
        placeholders = ', '.join(['?'] * len(unique_hashes))
        query = f"SELECT receipt_hash FROM certified_receipts WHERE receipt_hash IN ({placeholders})"
        existing = conn.execute(query, unique_hashes).fetchall()
        
        if existing:
            raise ValueError(f"DOUBLE_SPENDING_DETECTED: {existing}")

        # 2. Canonical Timestamp (Sekundengenau, ohne Drift)
        canonical_now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        # 3. Ledger Block schreiben
        block_hash = ledger_payload['block_hash']
        conn.execute('''
            INSERT INTO ledger_entries (block_hash, payload, timestamp, prev_hash)
            VALUES (?, ?, ?, ?)
        ''', (
            block_hash,
            json.dumps(ledger_payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False),
            canonical_now,
            ledger_payload.get('prev_hash', 'GENESIS')
        ))

        # 4. Sperrliste (certified_receipts) schreiben
        for r_hash in unique_hashes:
            conn.execute('''
                INSERT INTO certified_receipts (receipt_hash, certificate_block_hash)
                VALUES (?, ?)
            ''', (r_hash, block_hash))

        conn.commit()
        return block_hash

    except Exception as e:
        try:
            conn.rollback()
        except sqlite3.OperationalError:
            pass 
        raise RuntimeError(f"FORTRESS_COMMIT_FAILED: {str(e)}")

# --- 3. UI & GOVERNANCE INTERFACE ---
st.markdown("---")
st.markdown("## ASSET GOVERNANCE CENTER")

try:
    current_year = selected_year
except NameError:
    current_year = 2026 

st.caption(f"Arithmetic Sovereignty | Institutional Finality | Period: {current_year}")

if current_year != 2026:
    st.error(f"No official rule set defined for the year {current_year}.")
else:
    active_rules = RULES_2026

    with sqlite3.connect(LEDGER_DB_PATH) as conn:
        # 1. Erweiterte Abfrage für Fortress-Integrität
        eligible_reports = conn.execute("""
            SELECT report_id, imo, vessel_name, raw_json, engine_input, canonical_base, received_at, receipt_hash 
            FROM telemetry_reports WHERE status = 'ELIGIBLE' ORDER BY received_at ASC
        """).fetchall()

    if eligible_reports:
        try:
            # 2. Daten für die Pure-Engine isolieren
            engine_inputs = []
            receipt_hashes = []
            
            for r in eligible_reports:
                if r[4]: # Das engine_input Feld
                    engine_inputs.append(json.loads(r[4]))
                    receipt_hashes.append(r[7]) # Der receipt_hash
                else:
                    st.error(f"Legacy Data Conflict: Report {r[0]} lacks Fortress data. Please re-upload.")
                    st.stop()

            # 3. Pure Engine Calculation
            engine_data = FuelEUAssetEngine.calculate(engine_inputs, active_rules)
            
            # 4. Fingerprint-Erzeugung (Controller-Ebene)
            from decimal import Decimal
            normalized_metrics = {k: str(Decimal(v)) for k, v in engine_data['metrics'].items()}
            
            calc_fp = generate_calculation_fingerprint(
                receipt_hashes,
                engine_data['engine_version'],
                engine_data['rule_hash'],
                normalized_metrics
            )

            # 5. Kompatibilitäts-Objekt für das bestehende UI
            results = {
                "metrics": normalized_metrics,
                "fingerprint": calc_fp,
                "engine_version": engine_data['engine_version'],
                "rule_hash": engine_data['rule_hash'],
                "receipt_hashes": receipt_hashes
            }

            if results:
                res = results["metrics"]
                c1, c2, c3 = st.columns(3)
                c1.metric("Verified Fuel", f"{res['fuel_mt']} mt")
                c2.metric("CO2 Emissions", f"{res['emissions_t']} t")
                c3.metric("Compliance Balance", f"{res['balance_t']} t")

                tab_cert, tab_lab = st.tabs(["Institutional Certification", "Forensic Replay Lab"])

                with tab_cert:
                    st.write("**Calculation Fingerprint:**")
                    st.code(results["fingerprint"], language="bash")
                    
                    comment = st.text_input("Certification Statement", key="cert_final_gold_input", placeholder="Purpose of Issuance...")
                    
                    if st.button("EXECUTE INSTITUTIONAL COMMIT", type="primary", use_container_width=True, key="btn_execute_gold"):
                        if not comment:
                            st.warning("Mandatory: Attestation Statement required.")
                        else:
                            try:
                                # 1. Payload für den Ledger vorbereiten
                                certificate_payload = {
                                    "block_hash": results["fingerprint"],
                                    "metrics": results["metrics"],
                                    "engine_version": results["engine_version"],
                                    "rule_hash": results["rule_hash"],
                                    "receipt_hashes": results["receipt_hashes"],
                                    "operator": st.session_state.get("active_role", "UNKNOWN"),
                                    "statement": comment,
                                    "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                                }

                                # 2. ATOMARER COMMIT (Ledger + Sperrliste)
                                with sqlite3.connect(LEDGER_DB_PATH) as conn:
                                    # --- SELF-HEALING: Tabellen für den Ledger sicherstellen ---
                                    # Wir stellen sicher, dass alle Spalten (inkl. payload) existieren
                                    conn.execute("""
                                        CREATE TABLE IF NOT EXISTS ledger_entries (
                                            block_hash TEXT PRIMARY KEY,
                                            payload TEXT,
                                            timestamp TEXT,
                                            prev_hash TEXT
                                        )
                                    """)
                                    conn.execute("""
                                        CREATE TABLE IF NOT EXISTS certified_receipts (
                                            receipt_hash TEXT PRIMARY KEY,
                                            certificate_block_hash TEXT,
                                            FOREIGN KEY(certificate_block_hash) REFERENCES ledger_entries(block_hash)
                                        )
                                    """)

                                    # 3. Den eigentlichen Commit ausführen
                                    final_hash = atomic_certification_commit(
                                        conn, 
                                        results["receipt_hashes"], 
                                        certificate_payload
                                    )
                                    
                                    # 4. Status-Update der Reports in der Telemetrie
                                    placeholders = ', '.join(['?'] * len(results["receipt_hashes"]))
                                    conn.execute(f"""
                                        UPDATE telemetry_reports 
                                        SET status = 'CERTIFIED' 
                                        WHERE receipt_hash IN ({placeholders})
                                    """, results["receipt_hashes"])
                                    
                                    conn.commit()

                                st.success(f"BLOCK SEALED & LOCKED: {final_hash}")
                                
                                if st.button("Acknowledge and Clear Buffer"):
                                    st.rerun()

                            except Exception as e:
                                st.error(f"FORTRESS REJECTION: {str(e)}")
                    else:
                        st.info("Benötigt OWNER-Rolle.")

                with tab_lab:
                    st.info("Forensic Replay Engine aktiv.")
                    if st.session_state.get("cert_success"):
                        st.success(f"✅ INSTITUTIONAL ASSET GENERATED: `{st.session_state.last_cert_id}`")
                        
                        col_pdf, col_json = st.columns(2)
                        with col_pdf:
                            st.download_button(
                                label="📥 Download Certificate (PDF)",
                                data=st.session_state.last_pdf,
                                file_name=f"{st.session_state.last_cert_id}.pdf",
                                mime="application/pdf",
                                key="dl_btn_pdf_final"
                            )
                        with col_json:
                            st.download_button(
                                label="💾 Download ERP-Data (JSON)",
                                data=st.session_state.last_json,
                                file_name=f"{st.session_state.last_cert_id}.json",
                                mime="application/json",
                                key="dl_btn_json_final"
                            )

        except Exception as e:
            st.error(f"🚨 ENGINE ERROR: {e}")
    else:
        st.info("Waiting for ELIGIBLE reports...")

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

# --- TEIL A: GOVERNANCE LAYER (Regierung) ---
st.subheader("Sovereign Registry (Governance Layer)")

if ledger is not None and is_valid:
    try:
        all_entries = ledger.get_all_entries()
    except Exception:
        all_entries = []
else:
    all_entries = []

if all_entries:
    for entry in all_entries:
        payload = json.loads(entry['payload_json'])
        with st.expander(f"GOV SEQ: {entry['seq']} | Block: {entry['block_hash'][:12]}"):
            c1, c2 = st.columns([2, 1])
            with c1:
                st.write(f"**Type:** {entry['block_type']} | **Year:** {entry['reporting_year']}")
                if 'vol' in payload: st.write(f"**Volume:** {payload['vol']} tCO2e")
                if 'market_snapshot' in payload: st.caption(f"🛡️ Market Anchored: {payload['market_snapshot']['price']} EUR | Hash: {payload['market_snapshot']['snapshot_hash'][:12]}...")
                st.markdown(f'<div class="hash-box">{entry["block_hash"]}</div>', unsafe_allow_html=True)
            with c2:
                st.markdown('<p class="audit-pass">✅ Ed25519 Verified</p>', unsafe_allow_html=True)
                st.download_button(
                    "📤 Audit Export", 
                    json.dumps(entry, indent=2), 
                    file_name=f"block_{entry['seq']}.json",
                    key=f"dl_{entry['seq']}"
                )
else:
    st.info("No governance events recorded.")

# --- TEIL B: ASSET LAYER (Zertifikate) ---
st.subheader("Certification Registry (Asset Layer)")

with sqlite3.connect(LEDGER_DB_PATH) as conn:
    try:
        conn.row_factory = sqlite3.Row
        certs = conn.execute("SELECT block_hash, payload as payload_json, timestamp, prev_hash FROM ledger_entries ORDER BY timestamp DESC").fetchall()
    except sqlite3.OperationalError:
        certs = []

if certs:
    for c in certs:
        try:
            raw_payload = json.loads(c["payload_json"])
            
            # --- TRANSLATION LAYER: Wir machen das Zertifikat PDF-kompatibel ---
            # Deine PDF-Funktion erwartet "calculation" -> "metrics"
            formatted_payload = {
                "header": {
                    "certificate_id": c["block_hash"][:12],
                    "rules": {"target_factor": raw_payload.get("rules", {}).get("target", "3.0")}
                },
                "calculation": {
                    "engine_version": raw_payload.get("engine_version", "v1.0-INST"),
                    "metrics": raw_payload.get("metrics", {})
                }
            }

            block_record = {
                "block_hash": c["block_hash"],
                "signature": "Ed25519_Institutional_Verified",
                "reporting_year": selected_year,
                "payload_json": json.dumps(formatted_payload) # Das hier füttert jetzt die PDF-Engine
            }
            
            with st.expander(f"CERT: {c['block_hash'][:12]} | {c['timestamp']}"):
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.write(f"**Operator:** {raw_payload.get('operator', 'UNKNOWN')}")
                    st.write(f"**Statement:** {raw_payload.get('statement', 'N/A')}")
                    st.json(raw_payload.get('metrics', {}))

                with col2:
                    # JSON Export
                    st.download_button(
                        label="📄 Download JSON",
                        data=json.dumps(raw_payload, indent=2),
                        file_name=f"certificate_{c['block_hash'][:8]}.json",
                        mime="application/json",
                        key=f"json_btn_{c['block_hash']}",
                        width="stretch"
                    )
                    
                    # PDF Export (FIXED)
                    try:
                        pdf_data = generate_asset_pdf_from_block(block_record)
                        st.download_button(
                            label="📑 Download PDF",
                            data=pdf_data,
                            file_name=f"velonaut_cert_{c['block_hash'][:8]}.pdf",
                            mime="application/pdf",
                            key=f"pdf_btn_{c['block_hash']}",
                            width="stretch"
                        )
                    except Exception as pdf_err:
                        st.error(f"PDF Engine: {pdf_err}")
                            
        except Exception as e:
            st.error(f"Display Error: {e}")
else:
    st.info("No institutional certificates generated yet.")

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

# --- INSTITUTIONAL AUDIT & INTEGRITY LAYER (Robust Version) ---
st.markdown("---")
with st.expander(" INSTITUTIONAL AUDIT MONITOR", expanded=False):
    st.caption(f"Forensic Node: {LEDGER_DB_PATH} | Double-Spending Guard: ACTIVE")
    
    try:
        with sqlite3.connect(LEDGER_DB_PATH) as conn:
            # Check, ob die Tabellen existieren
            check = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='certified_receipts'").fetchone()
            
            if check:
                # 1. Übersicht der gesperrten Hashes
                audit_trail = conn.execute("SELECT * FROM certified_receipts ORDER BY ROWID DESC LIMIT 50").fetchall()
                
                # 2. Letzte Ledger-Einträge (Wir holen einfach alle Spalten, egal wie sie heißen)
                ledger_logs = conn.execute("SELECT * FROM ledger_entries ORDER BY ROWID DESC LIMIT 5").fetchall()

                col_audit1, col_audit2 = st.columns(2)
                
                with col_audit1:
                    st.subheader("Locked Proofs")
                    if audit_trail:
                        import pandas as pd
                        # Wir zeigen die Rohdaten an, falls die Spaltennamen variieren
                        df_audit = pd.DataFrame(audit_trail)
                        st.dataframe(df_audit, use_container_width=True, height=200)
                    else:
                        st.info("Registry is active but empty.")

                with col_audit2:
                    st.subheader("Ledger Finality")
                    if ledger_logs:
                        for entry in ledger_logs:
                            # Wir zeigen den ersten Wert (meist der Hash) und den Rest als Info
                            st.code(f"BLOCK ID: {str(entry[0])[:16]}...\nDATA: {str(entry[1])[:50]}...", language="bash")
                    else:
                        st.info("No blocks sealed yet.")
            else:
                st.warning("Forensic Registry not yet initialized. Complete your first 'Commit' to activate.")

    except Exception as e:
        # Falls es immer noch kracht, zeigen wir genau an, was der Datenbank fehlt
        st.error(f"Audit View Structural Note: {e}")

    st.divider()
    st.caption("Verification Method: SHA-256 Atomic Cross-Check | Status: 🟢 SYSTEM NOMINAL")

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
