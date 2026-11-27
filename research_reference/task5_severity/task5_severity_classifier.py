import math

def classify_stenosis_severity(narrowing_percent):
    if narrowing_percent is None:
        return "Unclassified"

    try:
        value = float(narrowing_percent)
    except (TypeError, ValueError):
        return "Invalid measurement"

    if math.isnan(value):
        return "Unclassified"

    if not math.isfinite(value) or value < 0 or value > 100:
        return "Invalid measurement"

    if value == 0:
        return "Normal"
    if value < 50:
        return "Mild / Outside configured classes"
    if value < 70:
        return "Moderate"
    return "Critical"
