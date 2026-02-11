# Offizielle FuelEU Maritime Reduktionspfade (gegenüber dem Referenzwert 91.16 gCO2e/MJ)
FUELEU_TARGETS = {
    2025: 91.16 * 0.98,    # -2% Reduktion
    2030: 91.16 * 0.94,    # -6% Reduktion
    2035: 91.16 * 0.85,    # -15% Reduktion
    2040: 91.16 * 0.69,    # -31% Reduktion
    2045: 91.16 * 0.38,    # -62% Reduktion
    2050: 91.16 * 0.20     # -80% Reduktion
}

# ETS Phase-in Plan (Wie viel Prozent der Emissionen bezahlt werden müssen)
ETS_PHASE_IN = {
    2024: 0.40,  # 40% der Emissionen
    2025: 0.70,  # 70% der Emissionen
    2026: 1.00   # 100% der Emissionen
}

# Standard-Werte für die Simulation
DEFAULT_EUA_PRICE = 85.0  # Euro pro Tonne CO2