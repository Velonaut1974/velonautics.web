from core.models import StrategyMode, AdditionalitySurplus

class AdditionalityEngine:
    @staticmethod
    def calculate_surplus(compliance_balance: float, mode: StrategyMode, year: int) -> AdditionalitySurplus:
        """
        Berechnet den handelbaren Überschuss basierend auf der gewählten Risikostrategie.
        """
        # Risiko-Puffer Logik
        if mode == StrategyMode.CONSERVATIVE:
            buffer_factor = 0.30  # 30% Sicherheitsmarge
        elif mode == StrategyMode.BALANCED:
            buffer_factor = 0.15  # 15% Sicherheitsmarge
        else:
            buffer_factor = 0.05  # 5% Sicherheitsmarge (Aggressive)

        gross_surplus = compliance_balance
        risk_buffer = gross_surplus * buffer_factor
        net_surplus = gross_surplus - risk_buffer

        # Rückgabe des Objekts passend zur neuen Struktur in models.py
        return AdditionalitySurplus(
            gross_surplus=float(gross_surplus),
            risk_buffer=float(risk_buffer),
            net_surplus=float(net_surplus)
        )