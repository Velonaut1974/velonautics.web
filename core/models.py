from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum
from datetime import datetime

class State(Enum):
    RAW = "RAW"               # Daten frisch importiert
    COMPLIANCE = "LOCKED"     # In der Isolation Firewall gesperrt
    MARKET = "MARKET"         # Als Asset auf Layer III verbrieft

class StrategyMode(Enum):
    CONSERVATIVE = "CONSERVATIVE (30% Buffer)"
    BALANCED = "BALANCED (15% Buffer)"
    AGRESSIVE = "AGGRESSIVE (5% Buffer)"

@dataclass
class EnergyEvent:
    id: str
    vessel_id: str
    fuel_type: str
    energy_mj: float
    ghg_intensity: float
    eu_scope_factor: float
    state: State = State.RAW
    created_at: datetime = field(default_factory=datetime.utcnow)

@dataclass
class Vessel:
    id: str
    name: str
    vessel_type: str
    dwt: int = 0  # Neu für v0.5.4.1
    events: List[EnergyEvent] = field(default_factory=list)

    def add_event(self, event: EnergyEvent):
        self.events.append(event)

@dataclass
class Fleet:
    vessels: List[Vessel] = field(default_factory=list)

    def get_all_events(self) -> List[EnergyEvent]:
        all_events = []
        for v in self.vessels:
            all_events.extend(v.events)
        return all_events

@dataclass
class InsettingAsset:
    asset_id: str
    vintage_year: int
    volume_t_co2e: float
    strategy_applied: str
    source_data_hash: str
    engine_version: str
    source_event_ids: List[str]
    created_at: datetime = field(default_factory=datetime.utcnow)