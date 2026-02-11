from core.models import State, EnergyEvent

class IsolationFirewall:
    @staticmethod
    def lock_for_compliance(event: EnergyEvent):
        """Überführt ein Event in den COMPLIANCE State. Irreversibel."""
        # Das ist die eigentliche Firewall-Logik:
        if event.state != State.RAW:
            raise PermissionError(f"Isolation Breach: Event {event.id} ist bereits im Status {event.state.value}!")
        
        event.state = State.COMPLIANCE
        print(f"🔒 Layer II: Event {event.id} erfolgreich für Compliance isoliert.")
        return True

    @staticmethod
    def release_to_market(event: EnergyEvent):
        """Isoliert das Event für Layer III (Markt/Insetting). Nur aus RAW möglich."""
        if event.state != State.RAW:
            raise PermissionError(f"Isolation Breach: Event {event.id} kann nicht vermarktet werden (Status: {event.state.value})!")
        
        event.state = State.MARKET
        print(f"💹 Layer III: Event {event.id} als Markt-Asset freigegeben.")
        return True