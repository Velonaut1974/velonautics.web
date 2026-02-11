import streamlit as st
import json
import uuid
import hashlib
from datetime import datetime
from core.models import Fleet, Vessel, EnergyEvent, State, StrategyMode, InsettingAsset
from core.engine_fueleu import FuelEUEngine
from core.engine_ets import ETSEngine
from core.states import IsolationFirewall
from core.additionality import AdditionalityEngine

# --- KONFIGURATION & STYLING ---
st.set_page_config(page_title="Velonaut | Integrity Infrastructure", layout="wide")

# SECURITY & DESIGN CSS
st.markdown("""
    <style>
    /* Versteckt GitHub-Icon, Streamlit-Menü und Header-Leiste */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {display:none;}
    
    /* Deine Design-Klassen */
    .hash-box {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 5px;
        font-family: 'Courier New', monospace;
        font-size: 0.8rem;
        border: 1px solid #d1d5db;
    }
    .audit-pass { color: #059669; font-weight: bold; }
    .audit-fail { color: #dc2626; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# --- HILFSFUNKTIONEN ---
def generate_fleet_hash(fleet):
    data_to_hash = []
    for v in fleet.vessels:
        event_states = [f"{e.id}:{e.state.value}:{e.energy_mj}" for e in v.events]
        data_to_hash.append(f"{v.id}:{event_states}")
    serialized_data = json.dumps(data_to_hash, sort_keys=True)
    return hashlib.sha256(serialized_data.encode()).hexdigest()

def save_data(fleet):
    output_data = []
    for v in fleet.vessels:
        v_dict = {"id": v.id, "name": v.name, "vessel_type": v.vessel_type, "events": []}
        for e in v.events:
            v_dict["events"].append({
                "id": e.id, "fuel_type": e.fuel_type, "energy_mj": e.energy_mj,
                "ghg_intensity": e.ghg_intensity, "eu_scope_factor": e.eu_scope_factor,
                "state": e.state.value
            })
        output_data.append(v_dict)
    with open('data/fleet.json', 'w') as f:
        json.dump(output_data, f, indent=4)

def save_new_asset(asset_obj):
    try:
        with open('data/assets.json', 'r') as f:
            assets = json.load(f)
    except: assets = []
    
    asset_dict = {
        "asset_id": asset_obj.asset_id,
        "vintage": asset_obj.vintage_year,
        "volume": asset_obj.volume_t_co2e,
        "strategy": asset_obj.strategy_applied,
        "source_hash": asset_obj.source_data_hash,
        "engine": asset_obj.engine_version,
        "events": asset_obj.source_event_ids,
        "timestamp": asset_obj.created_at.isoformat()
    }
    assets.append(asset_dict)
    with open('data/assets.json', 'w') as f:
        json.dump(assets, f, indent=4)
    return asset_dict

def load_data():
    with open('data/fleet.json', 'r') as f:
        data = json.load(f)
    fleet = Fleet()
    for v_data in data:
        vessel = Vessel(id=v_data['id'], name=v_data['name'], vessel_type=v_data['vessel_type'])
        for e_data in v_data['events']:
            vessel.add_event(EnergyEvent(
                id=e_data['id'], vessel_id=v_data['id'], fuel_type=e_data['fuel_type'],
                energy_mj=e_data['energy_mj'], ghg_intensity=e_data['ghg_intensity'],
                eu_scope_factor=e_data['eu_scope_factor'], state=State(e_data.get('state', 'RAW'))
            ))
        fleet.vessels.append(vessel)
    return fleet

# --- INITIALISIERUNG ---
fleet = load_data()
fueleu = FuelEUEngine(year=2025)
ets = ETSEngine(year=2025)

st.title("🚢 Velonaut | Maritime Integrity Infrastructure")
st.caption("v0.4.1-Beta | Institutional Data Provenance & Regulatory Isolation")

# --- DOCUMENTATION INTEGRATION ---
with st.expander("📖 System Documentation & Logic (Quick Guide)"):
    try:
        with open("README.md", "r", encoding="utf-8") as f:
            st.markdown(f.read())
    except:
        st.info("Documentation guide is currently being loaded...")

# --- SIDEBAR ---
st.sidebar.header("🕹️ Control Center")
selected_year = st.sidebar.selectbox("Reporting Year", [2025, 2030, 2035])
eua_price = st.sidebar.slider("ETS EUA Price (€/t)", 50, 150, 85)
st.sidebar.divider()
strategy = st.sidebar.selectbox("Additionality Strategy", list(StrategyMode))

# --- LAYER I: COMPLIANCE ANALYTICS ---
col1, col2, col3 = st.columns(3)
balance = fueleu.get_compliance_balance(fleet)
avg_int = fueleu.calculate_fleet_intensity(fleet)
total_ets = sum(ets.calculate_cost(e, eua_price) for e in fleet.get_all_events())

col1.metric("Fleet Intensity", f"{avg_int:.2f} g/MJ")
col2.metric("FuelEU Balance (Surplus)", f"{balance:.2f} tCO2e")
col3.metric("Est. ETS Liability", f"{total_ets:,.2f} €")

# --- LAYER II: ISOLATION LEDGER ---
st.divider()
st.header("🛡️ Layer II: Isolation Firewall")
for v in fleet.vessels:
    with st.expander(f"Vessel: {v.name}"):
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

# --- LAYER III: ASSET ISSUANCE ---
st.divider()
st.header("💎 Layer III: Additionality & Asset Issuance")
if balance > 0:
    report = AdditionalityEngine.calculate_surplus(balance, strategy, selected_year)
    ca, cb, cc = st.columns(3)
    ca.metric("Gross Surplus", f"{report.gross_surplus:.2f}")
    cb.metric("Risk Buffer", f"-{report.risk_buffer:.2f}")
    cc.metric("Net Marketable Surplus", f"{report.net_surplus:.2f}")

    if st.button("🚀 Issue Verified Asset"):
        current_hash = generate_fleet_hash(fleet)
        new_asset = InsettingAsset(
            asset_id=f"VELO-{uuid.uuid4().hex[:8].upper()}",
            vintage_year=selected_year,
            volume_t_co2e=report.net_surplus,
            strategy_applied=strategy.value,
            source_data_hash=current_hash,
            engine_version="Velonaut-Core-v0.4.1",
            source_event_ids=[e.id for e in fleet.get_all_events()]
        )
        save_new_asset(new_asset)
        st.balloons()
        st.rerun()
else:
    st.warning("No Additionality available.")

# --- ASSET REGISTRY & AUDIT ---
st.subheader("🏦 Institutional Asset Registry")
try:
    with open('data/assets.json', 'r') as f:
        assets = json.load(f)
    
    for asset in reversed(assets):
        with st.expander(f"Asset: {asset['asset_id']} | {asset['volume']:.2f} tCO2e"):
            m1, m2 = st.columns([2, 1])
            with m1:
                st.write(f"**Vintage:** {asset['vintage']} | **Strategy:** {asset['strategy']}")
                st.markdown(f'<div class="hash-box">{asset["source_hash"]}</div>', unsafe_allow_html=True)
            with m2:
                # Audit Verification
                current_hash = generate_fleet_hash(fleet)
                if current_hash == asset['source_hash']:
                    st.markdown('<p class="audit-pass">✅ Hash Verified</p>', unsafe_allow_html=True)
                else:
                    st.markdown('<p class="audit-fail">⚠️ State Changed</p>', unsafe_allow_html=True)
                
                # Export Button
                asset_json = json.dumps(asset, indent=2)
                st.download_button("📤 Export JSON", asset_json, file_name=f"{asset['asset_id']}.json", mime="application/json")
except: st.info("Registry initializing...")