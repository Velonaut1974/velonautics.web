import json

def save_fleet_state(fleet):
    data = []
    for v in fleet.vessels:
        v_dict = {
            "id": v.id,
            "name": v.name,
            "vessel_type": v.vessel_type,
            "events": []
        }
        for e in v.events:
            v_dict["events"].append({
                "id": e.id,
                "fuel_type": e.fuel_type,
                "energy_mj": e.energy_mj,
                "ghg_intensity": e.ghg_intensity,
                "eu_scope_factor": e.eu_scope_factor,
                "state": e.state.value # Hier speichern wir den neuen Status!
            })
        data.append(v_dict)
    
    with open('data/fleet.json', 'w') as f:
        json.dump(data, f, indent=4)