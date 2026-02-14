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

# --- NEU: PERIOD CLOSURE BUTTON ---
st.sidebar.markdown("---")
st.sidebar.subheader("🏛 Period Closure")
if st.sidebar.button(f"Seal Year {selected_year}", help="Sperrt das Jahr permanent"):
    try:
        with st.spinner("Erzeuge Jahressiegel..."):
            seal = ledger.seal_period(selected_year, lambda h: signing_key.sign(h).signature)
            st.sidebar.success(f"Versiegelt! Hash: {seal[:12]}")
            time.sleep(1.5)
            st.rerun()
    except Exception as e:
        st.sidebar.error(f"Fehler: {str(e)}")

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

    if st.button("GENERATE REGULATORY ASSET", use_container_width=True):
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
            st.download_button(
                "📤 Audit Export", 
                json.dumps(entry, indent=2), 
                file_name=f"block_{entry['seq']}.json",
                key=f"dl_{entry['seq']}"
            )# --- INSTITUTIONAL FOOTER ---
st.divider()
st.caption("© 2026 VELONAUT LABS | Institutional Prototyping | Ed25519 Secured")
st.caption("DISCLAIMER: This system is a forensic infrastructure tool. It does not constitute legal or regulatory advice. Responsibility for data accuracy remains with the operator.")
# --- FINAL SEAL (CENTERED & LARGE) ---
st.write("") 
st.write("") # Zusätzlicher Weißraum für die Urkunden-Optik
col_s1, col_s2, col_s3 = st.columns([1, 1, 1]) # 1:1:1 Verhältnis für eine breite Mitte

with col_s2: # Die mittlere Spalte ist jetzt breiter
    try:
        # use_container_width=True füllt die gesamte mittlere Spalte aus
        st.image("assets/logo.png", width="stretch")
    except:
        pass