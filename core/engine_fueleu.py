from core.models import Fleet, State

# Offizielle FuelEU Maritime Reduktionspfade (gCO2e/MJ)
# Quelle: FuelEU Maritime Regulation (EU) 2023/1805
# Referenzwert 2020: 91.16 gCO2e/MJ
# Stufen gelten jeweils bis zur naechsten Reduktion
_FUELEU_STEPS = [
    (2025, 89.34),  # -2%,   gilt 2025-2029
    (2030, 85.69),  # -6%,   gilt 2030-2034
    (2035, 77.50),  # -14.5%, gilt 2035-2039
    (2040, 63.00),  # -31%,  gilt 2040-2044
    (2045, 34.64),  # -62%,  gilt 2045-2049
    (2050, 18.23),  # -80%,  gilt ab 2050
]

def _resolve_target(year: int) -> float:
    """Gibt den gueltigen Zielwert fuer ein beliebiges Jahr zurueck.
    Vor 2025: Referenzwert 91.16 (keine Reduktionspflicht).
    Nach letzter Stufe: letzter bekannter Wert.
    """
    target = 91.16  # Fallback: Referenzwert vor 2025
    for step_year, step_value in _FUELEU_STEPS:
        if year >= step_year:
            target = step_value
        else:
            break
    return target


class FuelEUEngine:
    def __init__(self, year: int):
        self.year = year
        self.target_intensities = {
            y: _resolve_target(y) for y in range(2020, 2051)
        }

    def calculate_fleet_intensity(self, fleet: Fleet) -> float:
        events = fleet.get_all_events()
        if not events:
            return 0.0
        total_energy = sum(e.energy_mj for e in events)
        total_emissions_g = sum((e.energy_mj * e.ghg_intensity) for e in events)
        return total_emissions_g / total_energy

    def get_compliance_balance(self, fleet: Fleet) -> float:
        target = _resolve_target(self.year)
        actual_intensity = self.calculate_fleet_intensity(fleet)
        events = fleet.get_all_events()
        total_energy = sum(e.energy_mj for e in events)
        balance_g = (target - actual_intensity) * total_energy
        return balance_g / 1_000_000