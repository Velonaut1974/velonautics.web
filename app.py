import streamlit as st
import json
import uuid
import hashlib
import hmac
import os
from decimal import Decimal, getcontext
from datetime import datetime
from core.models import Fleet, Vessel, EnergyEvent, State, StrategyMode, InsettingAsset
from core.engine_fueleu import FuelEUEngine
from core.engine_ets import ETSEngine
from core.states import IsolationFirewall
from core.additionality import AdditionalityEngine

# --- PRÄZISIONSEINSTELLUNG ---
getcontext().prec = 28

# --- CLAUDE-SECURITY-KEY (v0.5.6) ---
# Holt den Schlüssel aus den Streamlit Secrets oder der Umgebung.
# Fallback nur für lokale Entwicklung.
SECRET_KEY = st.secrets.get("VELONAUT_LEDGER_KEY", os.environ.get("VELONAUT_LEDGER_KEY", "dev-only-insecure-key"))

# --- KONFIGURATION & STYLING ---
st.set_page_config(page_title="Velonaut | Institutional Ledger v0.5.6", layout="wide")

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    .stDeployButton {display:none;}
    .hash-box { 
        background-color: #f8fafc; padding: 10px; border-radius: 4px; 
        font-family: monospace; font-size: 0.75rem; border: 1px solid #e2e8f0; 
        word-wrap: break-word;
    }
    .audit-pass { color: #059669; font-weight: bold; }
    .audit-fail { color: #dc2626; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# --- SOVEREIGN REPLAY ENGINE (v0.5.6) ---

def sign_entry(entry_dict):
    """ Erzeugt eine kryptografische Signatur über das gesamte Asset-Dict. """
    data = {k: v for k, v in entry_dict.items() if k != 'signature'}
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hmac.new(SECRET_KEY.encode(), canonical.encode(), hashlib.sha256).hexdigest()

def recompute_surplus_deterministically(raw_events, rules):
    """ Das mathematische Herzstück für das Forensic Replay. """
    total_balance = Decimal('0')
    target_intensity = Decimal(str(rules.get('target', '0')))
    for e in raw_events:
        mj = Decimal(str(e['mj']))
        ghg = Decimal(str(e['ghg']))
        scope = Decimal(str(e['scope']))
        diff = target_intensity - ghg
        total_balance += (diff * mj * scope)
    return total_balance

def get_regulatory_hash(event_snapshots, rules_snapshot):
    """ Ebene 1: Regulatory Hash - Der kanonische Anker für Daten und Regeln. """
    canonical_events = []
    for e in sorted(event_snapshots, key=lambda x: str(x['id'])):
        canonical_events.append({
            "id": str(e['id']), "mj": str(e['mj']),   
            "ghg": str(e['ghg']), "scope": str(e['scope'])
        })
    basis = {
        "physicals": canonical_events,
        "rules": {
            "year": int(rules_snapshot['year']),
            "target": str(rules_snapshot['target']),
            "ets_factor": str(rules_snapshot.get('ets_factor', '1.0'))
        },
        "engine_logic": "v0.5.6-institutional-grade"
    }
    serialized = json.dumps(basis, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

def validate_entire_ledger(ledger):
    """ Vollständiger forensischer Audit: Signatur, Zeit, Chain & Mathematik. """
    errors = []
    last_hash = "0".zfill(64)
    last_seq = -1 # Start bei -1 wegen Genesis Block (SEQ 0)
    last_ts = None
    
    for entry in ledger:
        # 1. Signatur-Check
        if 'signature' not in entry:
            errors.append(f"Unsigned Entry @ SEQ {entry.get('seq', '?')}")
        else:
            if not hmac.compare_digest(entry['signature'], sign_entry(entry)):
                errors.append(f"SIGNATURE FRAUD @ SEQ {entry['seq']}!")

        p = entry['payload']
        
        # 2. Timestamp Monotonie (Try-Catch für Sicherheit)
        try:
            current_ts = datetime.fromisoformat(p['ts'])
            if last_ts and current_ts < last_ts:
                errors.append(f"Time Regression @ SEQ {entry['seq']}")
            last_ts = current_ts
        except:
            errors.append(f"Timestamp Format Error @ SEQ {entry['seq']}")

        # 3. Chain & Sequence Integrity
        if entry['seq'] != last_seq + 1:
            errors.append(f"SEQ Break: {entry['seq']} follows {last_seq}")
        if entry['prev_hash'] != last_hash:
            errors.append(f"Chain Break @ SEQ {entry['seq']}")

        # 4. Mathematical Replay (überspringen für Genesis)
        if entry['reg_hash'] != "GENESIS":
            try:
                calculated_vol = recompute_surplus_deterministically(p['raw_events'], p['rules'])
                claimed_vol = Decimal(str(p['vol']))
                if abs(calculated_vol - claimed_vol) > Decimal('0.000001'):
                    errors.append(f"Math Error @ SEQ {entry['seq']}")
            except Exception as e:
                errors.append(f"Replay Failed @ SEQ {entry['seq']}: {str(e)}")

        last_hash = entry['asset_hash']
        last_seq = entry['seq']
    
    return len(errors) == 0, errors

# --- DATA OPS ---

def initialize_genesis_if_empty(ledger):
    """ Erstellt den Genesis Block (SEQ 0), falls das Ledger leer ist. """
    if not ledger or len(ledger) == 0:
        genesis_payload = {
            "vol": "0",
            "strat": "N/A",
            "rules": {"year": 0, "target": "0", "ets_factor": "0"},
            "raw_events": [],
            "ts": "2026-01-01T00:00:00",
            "uuid": "00000000-0000-0000-0000-000000000000"
        }
        genesis = {
            "seq": 0,
            "prev_hash": "0" * 64,
            "reg_hash": "GENESIS",
            "asset_id": "VELO-GENESIS",
            "payload": genesis_payload,
            "asset_hash": hashlib.sha256(b"VELO_GENESIS_2026").hexdigest()
        }
        genesis["signature"] = sign_entry(genesis)
        return [genesis]
    return ledger

def load_data():
    try:
        with open('data/fleet.json', 'r') as f:
            data = json.load(f)
        fl = Fleet()
        for v_data in data:
            vessel = Vessel(id=v_data['id'], name=v_data['name'], vessel_type=v_data['vessel_type'], dwt=v_data.get('dwt', 0))
            for e_data in v_data['events']:
                vessel.add_event(EnergyEvent(id=e_data['id'], vessel_id=v_data['id'], fuel_type=e_data['fuel_type'], energy_mj=e_data['energy_mj'], ghg_intensity=e_data['ghg_intensity'], eu_scope_factor=e_data['eu_scope_factor'], state=State(e_data.get('state', 'RAW'))))
            fl.vessels.append(vessel)
        return fl
    except: return Fleet()

def save_data(fleet):
    output_data = []
    for v in fleet.vessels:
        v_dict = {"id": v.id, "name": v.name, "vessel_type": v.vessel_type, "dwt": v.dwt, "events": []}
        for e in v.events:
            v_dict["events"].append({"id": e.id, "fuel_type": e.fuel_type, "energy_mj": e.energy_mj, "ghg_intensity": e.ghg_intensity, "eu_scope_factor": e.eu_scope_factor, "state": e.state.value})
        output_data.append(v_dict)
    with open('data/fleet.json', 'w') as f: json.dump(output_data, f, indent=4)

def load_ledger():
    try:
        with open('data/assets.json', 'r') as f:
            content = json.load(f)
            l = content if isinstance(content, list) else []
            return initialize_genesis_if_empty(l)
    except: return initialize_genesis_if_empty([])

# --- APP EXECUTION ---

fleet = load_data()
ledger = load_ledger()

# --- SIDEBAR: INSTITUTIONAL COCKPIT ---
st.sidebar.header("🕹️ Institutional Control")
st.sidebar.markdown("---")

# ABSCHNITT 1: REGULATORIK
st.sidebar.subheader("⚖️ Regulatory Framework")
st.sidebar.info(
    "Grenzwerte der FuelEU Maritime gelten immer für 5-Jahres-Perioden. "
    "Die nächste Verschärfung erfolgt 2030."
)

selected_year = st.sidebar.selectbox(
    "Compliance Period", 
    [2025, 2030, 2035, 2040],
    help="Wähle das Startjahr der regulatorischen Phase. Die EU verschärft die Ziele alle 5 Jahre."
)

strategy = st.sidebar.selectbox(
    "Risk Strategy", 
    list(StrategyMode),
    help="Bestimmt, wie viel Sicherheits-Puffer (Buffer) einbehalten wird, bevor Assets tokenisiert werden."
)

st.sidebar.markdown("---")

# ABSCHNITT 2: MARKT-DATEN
st.sidebar.subheader("📈 Market Environment")
st.sidebar.caption("Simuliert den aktuellen Marktwert deiner überschüssigen Emissionsrechte.")

eua_price = st.sidebar.slider(
    "EUA ETS Price (€/tCO2e)", 
    min_value=50.0, 
    max_value=250.0, 
    value=85.5, 
    step=0.1,
    format="%.1f",
    help="Der aktuelle Börsenpreis für EU-Emissionsberechtigungen."
)

st.sidebar.markdown("---")

# ABSCHNITT 3: SYSTEM-STATUS
st.sidebar.subheader("🔒 Integrity Status")
if is_valid: # Wir nutzen die Variable aus dem Validierungs-Check oben
    st.sidebar.success("Ledger: Verified")
    st.sidebar.caption(f"Engine: v0.5.6-Sovereign")
else:
    st.sidebar.error("Ledger: BREACH DETECTED")

# Initialisierung der Engine mit dem gewählten Jahr
fueleu_ui = FuelEUEngine(year=selected_year)

st.title("🚢 Velonaut | v0.5.6 Institutional Ledger")
st.caption("Arithmetic Sovereignty | Cryptographic Signatures | Triple-Layer Architecture")

# --- README SEKTION ---
with st.expander("📖 System Documentation & Logic (Quick Guide)"):
    try:
        with open("README.md", "r", encoding="utf-8") as f:
            st.markdown(f.read())
    except:
        st.info("Documentation guide (README.md) not found in repository.")

# --- LAYER I: PHYSICAL DATA PROOF ---
st.header("📡 Layer I: Physical Data Proof")
st.info("Integritäts-Check der physikalischen Rohdaten & Signatur-Verifizierung")

with st.spinner("Forensic Audit in progress..."):
    is_valid, chain_errors = validate_entire_ledger(ledger)

if not is_valid:
    st.error(f"🚨 LAYER I BREACH: {chain_errors[0]}")
else:
    st.success("🔒 Institutional Chain of Custody Verified: Signatures & Mathematics Consistent.")

# --- LAYER II: ISOLATION FIREWALL ---
st.divider()
st.header("🛡️ Layer II: Isolation Firewall")
for v in fleet.vessels:
    with st.expander(f"Vessel: {v.name} ({v.id})"):
        st.caption(f"Type: {v.vessel_type} | DWT: {v.dwt}")
        for e in v.events:
            c1, c2, c3 = st.columns([3, 2, 1])
            c1.write(f"**ID:** {e.id} | {e.fuel_type}")
            c2.write(f"Status: `{e.state.value}`")
            if e.state == State.RAW:
                if c3.button("Lock for Compliance", key=f"l_{e.id}"):
                    IsolationFirewall.lock_for_compliance(e)
                    save_data(fleet)
                    st.rerun()
            else: c3.write("🔒 LOCKED")

# --- LAYER III: ADDITIONALITY ASSETS ---
st.divider()
st.header("💎 Layer III: Additionality Assets")
balance = fueleu_ui.get_compliance_balance(fleet)

if balance > 0:
    report = AdditionalityEngine.calculate_surplus(balance, strategy, selected_year)
    
    # Wir erweitern auf 3 Spalten, um Platz für die monetäre Bewertung zu schaffen
    col_a, col_b, col_c = st.columns(3)
    
    # Spalte 1: Der regulatorische Status (Unveränderter Fachbegriff)
    col_a.metric("Fleet Compliance Balance", f"{balance:,.2f} gCO2e/MJ")
    
    # Spalte 2: Das berechnete Asset (Unveränderter Fachbegriff)
    col_b.metric("Tradable Net Surplus", f"{report.net_surplus:,.2f} tCO2e")
    
    # Spalte 3: Die monetäre Bewertung basierend auf dem hochpräzisen ETS-Preis
    # Nutzung von Decimal für arithmetische Souveränität
    from decimal import Decimal
    market_value = Decimal(str(report.net_surplus)) * Decimal(str(eua_price))
    col_c.metric("Estimated Market Value (EUA)", f"€ {market_value:,.2f}")
    
    if st.button("🚀 Issue Chained Asset (Tokenize)"):
        valid_ledger = [e for e in ledger if isinstance(e, dict) and 'asset_hash' in e]
        prev_h = valid_ledger[-1]['asset_hash'] if valid_ledger else "0".zfill(64)
        
        raw_events = []
        for e in fleet.get_all_events():
            if e.state != State.RAW:
                raw_events.append({"id": str(e.id), "mj": str(e.energy_mj), "ghg": str(e.ghg_intensity), "scope": str(e.eu_scope_factor)})
        
        rules = {"year": selected_year, "target": str(fueleu_ui.target_intensities[selected_year]), "ets_factor": str(ETSEngine(year=selected_year).phase_in_factor)}
        reg_h = get_regulatory_hash(raw_events, rules)
        payload = {"vol": str(report.net_surplus), "strat": strategy.value, "rules": rules, "raw_events": raw_events, "ts": datetime.utcnow().isoformat(), "uuid": str(uuid.uuid4())}
        asset_h = hashlib.sha256(json.dumps({"prev": prev_h, "reg": reg_h, "load": payload}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        
        new_entry = {"seq": len(ledger) + 1, "prev_hash": prev_h, "reg_hash": reg_h, "asset_id": f"VELO-{payload['uuid'][:8].upper()}", "payload": payload, "asset_hash": asset_h}
        new_entry["signature"] = sign_entry(new_entry)
        
        ledger.append(new_entry)
        with open('data/assets.json', 'w') as f: json.dump(ledger, f, indent=4)
        st.rerun()
else: st.warning("No Surplus available for Layer III.")

# --- REGISTRY ---
st.divider()
st.subheader("🏦 Sovereign Registry")
for entry in reversed(ledger):
    if not isinstance(entry, dict) or 'payload' not in entry: continue
    with st.expander(f"SEQ: {entry['seq']} | Asset: {entry['asset_id']}"):
        c1, c2 = st.columns([2, 1])
        with c1:
            st.write(f"**Volume:** {entry['payload']['vol']} tCO2e")
            st.write(f"**Timestamp:** {entry['payload']['ts']}")
            st.markdown(f'<div class="hash-box">{entry["asset_hash"]}</div>', unsafe_allow_html=True)
        with c2:
            if hmac.compare_digest(entry['signature'], sign_entry(entry)):
                st.markdown('<p class="audit-pass">✅ Cryptographically Authentic</p>', unsafe_allow_html=True)
            else: st.markdown('<p class="audit-fail">⚠️ Signature Invalid</p>', unsafe_allow_html=True)
            st.download_button("📤 Audit Export", json.dumps(entry, indent=2), file_name=f"{entry['asset_id']}.json")