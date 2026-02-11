from core.models import StrategyMode, AdditionalitySurplus

class AdditionalityEngine:
    @staticmethod
    def calculate_surplus(total_balance: float, mode: StrategyMode, year: int):
        if total_balance <= 0:
            return None
        
        # Puffer-Logik basierend auf dem Strategie-Modus
        if mode == StrategyMode.CONSERVATIVE:
            buffer_factor = 0.30
        elif mode == StrategyMode.BALANCED:
            buffer_factor = 0.15
        else:
            buffer_factor = 0.05
            
        buffer = total_balance * buffer_factor
        net = total_balance - buffer
        
        return AdditionalitySurplus(
            year=year,
            gross_surplus=total_balance,
            risk_buffer=buffer,
            net_surplus=net,
            strategy_mode=mode.value
        )