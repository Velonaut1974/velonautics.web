from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional
from datetime import datetime
import uuid
import hashlib
import json

# 1. Status Definitionen
class State(Enum):
    RAW = "RAW"
    COMPLIANCE = "LOCKED"
    MARKET = "MARKETABLE"

class StrategyMode(Enum):
    CONSERVATIVE = "CONSERVATIVE (30% Buffer)"
    BALANCED = "BALANCED (15% Buffer)"
    AGGRESSIVE = "AGGRESSIVE (5% Buffer)"

# 2. Basis-Modelle
@dataclass
class EnergyEvent:
    id: str
    vessel_id: str
    fuel_type: str
    energy_mj: float
    ghg_intensity: float
    eu_scope_factor: float
    state: State = State.RAW

    @property
    def emissions_tonnes(self) -> float:
        """Berechnet die CO2e-Emissionen in Tonnen."""
        return (self.energy_mj * self.ghg_intensity) / 1_000_000

    def to_dict(self):
        return {k: (v.value if isinstance(v, Enum) else v) for k, v in self.__dict__.items()}

@dataclass
class Vessel:
    id: str
    name: str
    vessel_type: str
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

# 3. Layer III Modelle (Additionality & Assets)
@dataclass
class AdditionalitySurplus:
    year: int
    gross_surplus: float
    risk_buffer: float
    net_surplus: float
    strategy_mode: str

@dataclass
class InsettingAsset:
    asset_id: str
    vintage_year: int
    volume_t_co2e: float
    strategy_applied: str
    source_data_hash: str
    engine_version: str
    source_event_ids: List[str]
    verification_status: str = "ISSUED"
    created_at: datetime = field(default_factory=datetime.utcnow)