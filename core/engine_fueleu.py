from core.models import Fleet, State

class FuelEUEngine:
    def __init__(self, year: int):
        self.year = year
        # Zielwerte laut FuelEU Maritime (vereinfacht für Prototyp)
        self.target_intensities = {
            2025: 89.34, # -2% vs 2020 (91.16)
            2030: 85.69, # -6%
            2035: 77.50  # -14.5%
        }

    def calculate_fleet_intensity(self, fleet: Fleet) -> float:
        events = fleet.get_all_events()
        if not events:
            return 0.0
        
        total_energy = sum(e.energy_mj for e in events)
        # Wir berechnen die Emissionen hier direkt, falls das Modell-Attribut hakt
        total_emissions_g = sum((e.energy_mj * e.ghg_intensity) for e in events)
        
        return total_emissions_g / total_energy

    def get_compliance_balance(self, fleet: Fleet) -> float:
        target = self.target_intensities.get(self.year, 91.16)
        actual_intensity = self.calculate_fleet_intensity(fleet)
        
        events = fleet.get_all_events()
        total_energy = sum(e.energy_mj for e in events)
        
        # Balance in Tonnen CO2e Überschuss/Defizit
        balance_g = (target - actual_intensity) * total_energy
        return balance_g / 1_000_000