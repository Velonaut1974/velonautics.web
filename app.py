import streamlit as st
import json
import uuid
import hashlib
from decimal import Decimal, getcontext
from datetime import datetime
from core.models import Fleet, Vessel, EnergyEvent, State, StrategyMode, InsettingAsset
from core.engine_fueleu import FuelEUEngine
from core.engine_ets import ETSEngine
from core.states import IsolationFirewall
from core.additionality import AdditionalityEngine

# --- PRÄZISIONSEINSTELLUNG ---
getcontext().prec = 28

# --- KONFIGURATION & STYLING ---
st.set_page_config(page_title="Velonaut | Institutional Ledger v0.5.4", layout="wide")

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

# --- SOVEREIGN REPLAY ENGINE (v0.5.4) ---

def recompute_surplus_deterministically(raw_events, rules):
    total_balance = Decimal('0')
    target_intensity = Decimal(str(rules['target']))
    for e in raw_events:
        mj = Decimal(str(e['mj']))
        ghg = Decimal(str(e['ghg']))
        scope = Decimal(str(e['scope']))
        diff = target_intensity - ghg
        total_balance += (diff * mj * scope)
    return total_balance

def get_regulatory_hash(event_snapshots, rules_snapshot):
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
        "engine_logic": "v0.5.4-arithmetic-sovereign"
    }
    serialized = json.dumps(basis, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

def validate_entire_ledger(ledger):
    errors = []
    last_hash = "0".zfill(64)
    last_seq = 0
    for entry in ledger:
        if not isinstance(entry, dict) or 'payload' not in entry or 'asset_hash' not in entry:
            continue
        p = entry['payload']
        if entry['seq'] != last_seq + 1:
            errors.append(f"SEQ Break: {entry['seq']} follows {last_seq}")
        if entry['prev_hash'] != last_hash:
            errors.append(f"Chain Break at SEQ {entry['seq']}")
        try:
            calculated_vol = recompute_surplus_deterministically(p['raw_events'], p['rules'])
            claimed_vol = Decimal(str(p['vol']))
            if abs(calculated_vol - claimed_vol) > Decimal('0.000001'):
                errors.append(f"Math Mismatch SEQ {entry['seq']}")
        except:
            errors.append(f"Math Error SEQ {entry['seq']}")
        recomputed_reg = get_regulatory_hash(p['raw_events'], p['rules'])
        if entry['reg_hash'] != recomputed_reg:
            errors.append(f"Anchor Fraud SEQ {entry['seq']}")
        last_hash = entry['asset_hash']
        last_seq = entry['seq']
    return len(errors) == 0, errors

# --- DATA OPS ---

def load_data():
    try:
        with open('data/fleet.json', 'r') as f:
            data = json.load(f)
        fl = Fleet()
        for v_data in data:
            # Hier wird das neue DWT Feld aus der JSON gezogen:
            vessel = Vessel(
                id=v_data['id'], 
                name=v_data['name'], 
                vessel_type=v_data['vessel_type'],
                dwt=v_data.get('dwt', 0)
            )
            # WICHTIG: Die Schleife für die Events muss bleiben!
            for e_data in v_data['events']:
                vessel.add_event(EnergyEvent(
                    id=e_data['id'], 
                    vessel_id=v_data['id'], 
                    fuel_type=e_data['fuel_type'],
                    energy_mj=e_data['energy_mj'], 
                    ghg_intensity=e_data['ghg_intensity'],
                    eu_scope_factor=e_data['eu_scope_factor'], 
                    state=State(e_data.get('state', 'RAW'))
                ))
            fl.vessels.append(vessel)
        return fl
    except Exception as e:
        st.error(f"Fehler beim Laden der Flottendaten: {e}")
        return Fleet()

def save_data(fleet):
    output_data = []
    for v in fleet.vessels:
        v_dict = {"id": v.id, "name": v.name, "vessel_type": v.vessel_type, "events": []}
        for e in v.events:
            v_dict["events"].append({"id": e.id, "fuel_type": e.fuel_type, "energy_mj": e.energy_mj, "ghg_intensity": e.ghg_intensity, "eu_scope_factor": e.eu_scope_factor, "state": e.state.value})
        output_data.append(v_dict)
    with open('data/fleet.json', 'w') as f: json.dump(output_data, f, indent=4)

def load_ledger():
    try:
        with open('data/assets.json', 'r') as f:
            content = json.load(f)
            return content if isinstance(content, list) else []
    except: return []

# --- APP EXECUTION ---

fleet = load_data()
ledger = load_ledger()

st.sidebar.header("🕹️ Institutional Control")
selected_year = st.sidebar.selectbox("Reporting Year", [2025, 2030, 2035])
eua_price = st.sidebar.slider("ETS Price (€)", 50, 150, 85)
strategy = st.sidebar.selectbox("Risk Strategy", list(StrategyMode))

fueleu_ui = FuelEUEngine(year=selected_year)

st.title("🚢 Velonaut | v0.5.4 Forensic Ledger")
st.caption("Arithmetic Sovereignty | Mathematical Replay | Triple-Layer Architecture")

# --- README SEKTION ---
with st.expander("📖 System Documentation & Logic (Quick Guide)"):
    try:
        with open("README.md", "r", encoding="utf-8") as f:
            st.markdown(f.read())
    except:
        st.info("Documentation guide (README.md) not found in repository.")

# --- LAYER I: PHYSICAL DATA PROOF ---
st.header("📡 Layer I: Physical Data Proof")
st.info("Integritäts-Check der physikalischen Rohdaten (IoT/Bunker-Reports)")

is_valid, chain_errors = validate_entire_ledger(ledger)
if not is_valid:
    st.error(f"🚨 LAYER I BREACH: {chain_errors[0]}")
else:
    st.success("🔒 Physical Integrity Verified: Mathematics & Hashes Consistent.")

# --- LAYER II: ISOLATION FIREWALL ---
st.divider()
st.header("🛡️ Layer II: Isolation Firewall")
st.info("Transformation von physikalischen Daten in regulatorisch geschützte Compliance-Events.")

for v in fleet.vessels:
    with st.expander(f"Vessel: {v.name} ({v.id})"):
        if hasattr(v, 'dwt'): st.caption(f"Type: {v.vessel_type} | DWT: {v.dwt}")
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
st.info("Berechnung des Net-Surplus und Tokenisierung der Emissionsvorteile.")

balance = fueleu_ui.get_compliance_balance(fleet)

if balance > 0:
    report = AdditionalityEngine.calculate_surplus(balance, strategy, selected_year)
    col_a, col_b = st.columns(2)
    col_a.metric("Fleet Compliance Balance", f"{balance:,.2f} gCO2e/MJ")
    col_b.metric("Tradable Net Surplus", f"{report.net_surplus:,.2f} tCO2e")
    
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
        ledger.append(new_entry)
        with open('data/assets.json', 'w') as f: json.dump(ledger, f, indent=4)
        st.rerun()
else:
    st.warning("No Surplus available for Layer III Issuance. Verify Locked Events in Layer II.")

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
            current_reg_audit = get_regulatory_hash(entry['payload']['raw_events'], entry['payload']['rules'])
            if current_reg_audit == entry['reg_hash']:
                st.markdown('<p class="audit-pass">✅ Layer I-III Audit Pass</p>', unsafe_allow_html=True)
            else:
                st.markdown('<p class="audit-fail">⚠️ Integrity Breach</p>', unsafe_allow_html=True)
            st.download_button("📤 Audit Export", json.dumps(entry, indent=2), file_name=f"{entry['asset_id']}.json")