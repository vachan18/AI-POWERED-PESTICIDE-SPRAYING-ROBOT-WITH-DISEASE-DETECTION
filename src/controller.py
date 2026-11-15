"""
AGRO VISION — Precision Spray Controller & Nozzle Actuation.
Maps disease center coordinates to physical solenoid spray nozzles
and calculates pulse duration to minimize chemical usage.
"""

from typing import Dict, List, Optional
from src.detection import DiseaseDetection


class SprayController:
    """
    Manages actuation commands for the 3-channel solenoid spray manifold
    (Nozzle 1: Left, Nozzle 2: Center, Nozzle 3: Right).
    """

    NOZZLE_ZONES = {
        1: (0.00, 0.35),  # Left bank
        2: (0.33, 0.67),  # Center bank
        3: (0.65, 1.00),  # Right bank
    }

    # Pulse durations in milliseconds matching severity tier
    PULSE_DURATIONS_MS = {
        "mild": 150,
        "moderate": 300,
        "severe": 600,
    }

    FLOW_RATE_ML_PER_SEC = 25.0  # Precision mist nozzle rating

    def __init__(self):
        self.total_sprays_executed = 0
        self.total_chemical_consumed_ml = 0.0

    def resolve_nozzle(self, cx: float) -> int:
        """Determines which nozzle covers the target x coordinate."""
        for nozzle_id, (min_x, max_x) in self.NOZZLE_ZONES.items():
            if min_x <= cx <= max_x:
                return nozzle_id
        return 2  # Default to center

    def generate_actuation_command(self, detection: DiseaseDetection) -> Dict:
        """
        Creates an actuation payload for Raspberry Pi Pico WH firmware.
        """
        cx, _ = detection.center
        nozzle_id = self.resolve_nozzle(cx)
        duration_ms = self.PULSE_DURATIONS_MS.get(detection.severity, 200)

        chemical_used_ml = (duration_ms / 1000.0) * self.FLOW_RATE_ML_PER_SEC
        self.total_sprays_executed += 1
        self.total_chemical_consumed_ml += chemical_used_ml

        return {
            "nozzle_id": nozzle_id,
            "duration_ms": duration_ms,
            "target_center": (cx, detection.center[1]),
            "disease": detection.disease_name,
            "severity": detection.severity,
            "estimated_chemical_ml": round(chemical_used_ml, 2),
        }

    def process_batch_detections(
        self, detections: List[DiseaseDetection]
    ) -> List[Dict]:
        """Dispatches actuation commands for an entire frame of detections."""
        return [self.generate_actuation_command(det) for det in detections]
