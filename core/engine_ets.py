from core.models import EnergyEvent
from core.config import ETS_PHASE_IN, DEFAULT_EUA_PRICE

class ETSEngine:
    def __init__(self, year: int = 2025):
        self.year = year
        self.phase_in_factor = ETS_PHASE_IN.get(year, 1.0)

    def calculate_cost(self, event: EnergyEvent, eua_price: float = DEFAULT_EUA_PRICE):
        """Berechnet die ETS-Kosten für ein einzelnes Ereignis."""
        # Formel: Emissionen * Fahrtgebiet-Faktor (50/100%) * Phase-in * Preis
        taxable_emissions = event.emissions_tonnes * event.eu_scope_factor * self.phase_in_factor
        cost = taxable_emissions * eua_price
        return cost