"""
AGRO VISION — Cloud Telemetry & Firebase RTDB Payload Generator.
Monitors battery status, solar harvesting wattage, spraying events,
and chemical conservation metrics.
"""

from datetime import datetime, timezone
from typing import Dict, List


class TelemetryLogger:
    """
    Serializes telemetry records for real-time synchronization
    with Firebase Realtime Database and the React telemetry dashboard.
    """

    BENCHMARK_MANUAL_SPRAY_ML_PER_PLANT = 35.0  # Blanket knapsack spray baseline

    def __init__(self, robot_id: str = "AGRO-VISION-01"):
        self.robot_id = robot_id

    def build_telemetry_packet(
        self,
        battery_voltage: float,
        solar_power_watts: float,
        sprays_log: List[Dict],
        location: Dict[str, float] = None,
    ) -> Dict:
        """Constructs a synchronized snapshot for Firebase RTDB."""
        if location is None:
            location = {"lat": 12.9698, "lng": 77.5023}  # Bengaluru Dr. AIT campus

        total_targeted_ml = sum(s.get("estimated_chemical_ml", 0.0) for s in sprays_log)
        benchmark_baseline_ml = len(sprays_log) * self.BENCHMARK_MANUAL_SPRAY_ML_PER_PLANT
        saved_ml = max(0.0, benchmark_baseline_ml - total_targeted_ml)
        savings_percentage = (
            round((saved_ml / benchmark_baseline_ml) * 100.0, 1)
            if benchmark_baseline_ml > 0
            else 0.0
        )

        return {
            "robot_id": self.robot_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "telemetry": {
                "battery_voltage": round(battery_voltage, 2),
                "battery_percentage": min(100, max(0, int((battery_voltage - 11.1) / (12.6 - 11.1) * 100))),
                "solar_power_watts": round(solar_power_watts, 2),
                "system_status": "ONLINE" if battery_voltage > 11.2 else "LOW_BATTERY",
            },
            "field_coordinates": location,
            "operation_metrics": {
                "active_sprays_count": len(sprays_log),
                "targeted_chemical_ml": round(total_targeted_ml, 2),
                "chemical_saved_ml": round(saved_ml, 2),
                "chemical_savings_percentage": savings_percentage,
            },
        }
