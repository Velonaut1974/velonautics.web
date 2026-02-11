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

# --- KONFIGURATION ---
st.set_page_config(page_title="Velonaut OS | v0.3.1", layout="wide")

# --- HILFSFUNKTION FÜR BEWEISBARKEIT (SNAPSHOT HASHING) ---
def generate_fleet_hash(fleet):
    """Erzeugt einen SHA-256 Fingerabdruck des aktuellen Flottenzustands."""
    # Wir serialisieren die IDs und Zustände aller Events, um die Integrität zu prüfen
    data_to_hash = []
    for v in fleet.vessels:
        event_states = [f"{e.id}:{e.state.value}:{e.energy_mj}" for e in v.events]
        data_to_hash.append(f"{v.id}:{event_states}")
    
    serialized_data = json.dumps(data_to_hash, sort_keys=True)
    return hashlib.sha256(serialized_data.encode()).hexdigest()

# --- PERSISTENZ-LAYER ---
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
    
    assets.append({
        "asset_id": asset_obj.asset_id,
        "vintage": asset_obj.vintage_year,
        "volume": asset_obj.volume_t_co2e,
        "strategy": asset_obj.strategy_applied,
        "source_hash": asset_obj.source_data_hash, # Der kryptografische Anker
        "engine": asset_obj.engine_version,
        "events": asset_obj.source_event_ids,
        "timestamp": asset_obj.created_at.isoformat()
    })
    with open('data/assets.json', 'w') as f:
        json.dump(assets, f, indent=4)

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

# --- LOGIK-INITIALISIERUNG ---
fleet = load_data()
st.title("🚢 Velonaut Operating System v0.3.1")
st.caption("Immutable Accounting Infrastructure | Compliance & Additionality Engine")

# --- SIDEBAR ---
st.sidebar.header("🕹️ Compliance Control")
selected_year = st.sidebar.selectbox("Reporting Year", [2025, 2030, 2035])
eua_price = st.sidebar.slider("ETS EUA Price (€/t)", 50, 150, 85)

st.sidebar.divider()
st.sidebar.header("⚖️ Risk & Strategy")
strategy = st.sidebar.selectbox("Additionality Mode", list(StrategyMode))

fueleu = FuelEUEngine(year=selected_year)
ets = ETSEngine(year=selected_year)

# --- LAYER I: ANALYTICS ---
col1, col2, col3 = st.columns(3)
balance = fueleu.get_compliance_balance(fleet)
avg_int = fueleu.calculate_fleet_intensity(fleet)
total_ets = sum(ets.calculate_cost(e, eua_price) for e in fleet.get_all_events())

col1.metric("Fleet Intensity", f"{avg_int:.2f} g/MJ")
col2.metric("FuelEU Balance", f"{balance:.2f} tCO2e", delta=f"{balance:.2f}")
col3.metric("Est. ETS Liability", f"{total_ets:,.2f} €")

# --- LAYER II: ISOLATION LEDGER ---
st.divider()
st.header("🛡️ Layer II: Isolation Firewall (Ledger)")
for v in fleet.vessels:
    with st.expander(f"Vessel: {v.name}"):
        for e in v.events:
            c1, c2, c3 = st.columns([3, 2, 1])
            c1.write(f"**ID:** {e.id} | {e.fuel_type}")
            c2.write(f"Status: `{e.state.value}`")
            if e.state == State.RAW:
                if c3.button("Lock", key=f"l_{e.id}"):
                    IsolationFirewall.lock_for_compliance(e)
                    save_data(fleet)
                    st.rerun()
            else: c3.write("🔒")

# --- LAYER III: ASSET ISSUANCE (WITH PROVENANCE) ---
st.divider()
st.header("💎 Layer III: Additionality & Verified Issuance")

if balance > 0:
    report = AdditionalityEngine.calculate_surplus(balance, strategy, selected_year)
    ca, cb, cc = st.columns(3)
    ca.metric("Gross Surplus", f"{report.gross_surplus:.2f}")
    cb.metric("Risk Buffer", f"-{report.risk_buffer:.2f}")
    cc.metric("Marketable Surplus", f"{report.net_surplus:.2f}")

    if st.button("🚀 Issue Asset with Provenance Hash"):
        # Beweiskette generieren
        current_hash = generate_fleet_hash(fleet)
        event_ids = [e.id for e in fleet.get_all_events()]
        
        new_asset = InsettingAsset(
            asset_id=f"VELO-{uuid.uuid4().hex[:8].upper()}",
            vintage_year=selected_year,
            volume_t_co2e=report.net_surplus,
            strategy_applied=strategy.value,
            source_data_hash=current_hash,
            engine_version="Velonaut-Core-v0.3.1-Beta",
            source_event_ids=event_ids
        )
        save_new_asset(new_asset)
        st.balloons()
        st.success(f"Asset {new_asset.asset_id} emittiert. Herkunft kryptografisch versiegelt.")
else:
    st.warning("⚠️ No Additionality available.")

# --- ASSET INVENTORY ---
st.subheader("🏦 Verified Asset Registry")
try:
    with open('data/assets.json', 'r') as f:
        assets = json.load(f)
    if assets:
        st.dataframe(assets, use_container_width=True)
    else: st.info("Registry empty.")
except: st.info("Registry not initialized.")

st.sidebar.success("System Status: Online")