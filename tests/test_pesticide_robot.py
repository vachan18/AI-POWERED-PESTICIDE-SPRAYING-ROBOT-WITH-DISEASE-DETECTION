"""
Unit Tests for AGRO VISION Precision Spraying Robot.
Verifies leaf disease detection filter, coordinate-to-nozzle resolution,
solenoid pulse duration calculations, and cloud telemetry generation.
"""

import os
import sys

# Add repository root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from src.detection import DiseaseDetection, LeafDiseaseDetector
from src.controller import SprayController
from src.telemetry import TelemetryLogger


def test_disease_detection_center_and_area():
    """Verify center coordinates and area calculation."""
    det = DiseaseDetection(
        disease_name="early_blight",
        confidence=0.88,
        bbox=(0.10, 0.20, 0.30, 0.60),
        severity="moderate",
    )
    cx, cy = det.center
    assert cx == 0.20
    assert cy == 0.40
    assert pytest.approx(det.area, 0.001) == 0.08


def test_detector_filters_low_confidence():
    """Ensure raw predictions below threshold are filtered out."""
    detector = LeafDiseaseDetector(min_confidence=0.60)
    raw = [
        {"class": "early_blight", "confidence": 0.82, "bbox": (0.1, 0.1, 0.3, 0.3)},
        {"class": "late_blight", "confidence": 0.45, "bbox": (0.4, 0.4, 0.6, 0.6)},
    ]
    formatted = detector.filter_and_format_detections(raw)
    assert len(formatted) == 1
    assert formatted[0].disease_name == "early_blight"
    assert formatted[0].confidence == 0.82


def test_detector_filters_invalid_bbox():
    """Ensure invalid / inverted bounding boxes are skipped."""
    detector = LeafDiseaseDetector(min_confidence=0.50)
    raw = [
        {"class": "leaf_mold", "confidence": 0.90, "bbox": (0.8, 0.2, 0.4, 0.6)},  # x1 > x2
        {"class": "leaf_mold", "confidence": 0.90, "bbox": (-0.1, 0.2, 0.4, 0.6)},  # x1 < 0
    ]
    formatted = detector.filter_and_format_detections(raw)
    assert len(formatted) == 0


def test_severity_calculation_tiers():
    """Verify mild, moderate, and severe classifications."""
    detector = LeafDiseaseDetector()
    assert detector.calculate_severity("early_blight", 0.02) == "mild"
    assert detector.calculate_severity("early_blight", 0.15) == "moderate"
    assert detector.calculate_severity("late_blight", 0.30) == "severe"


def test_nozzle_resolution():
    """Verify coordinate mapping across Left, Center, and Right nozzles."""
    controller = SprayController()
    assert controller.resolve_nozzle(0.15) == 1  # Left
    assert controller.resolve_nozzle(0.50) == 2  # Center
    assert controller.resolve_nozzle(0.85) == 3  # Right


def test_actuation_command_generation():
    """Verify solenoid duration and estimated chemical usage."""
    controller = SprayController()
    det = DiseaseDetection(
        disease_name="bacterial_spot",
        confidence=0.91,
        bbox=(0.05, 0.10, 0.25, 0.40),
        severity="mild",
    )
    cmd = controller.generate_actuation_command(det)
    assert cmd["nozzle_id"] == 1
    assert cmd["duration_ms"] == 150
    assert cmd["disease"] == "bacterial_spot"
    assert cmd["estimated_chemical_ml"] == pytest.approx(3.75, 0.01)
    assert controller.total_sprays_executed == 1


def test_batch_detection_processing():
    """Test multi-target processing in a single frame."""
    controller = SprayController()
    dets = [
        DiseaseDetection("early_blight", 0.85, (0.1, 0.1, 0.2, 0.3), "mild"),
        DiseaseDetection("late_blight", 0.92, (0.7, 0.2, 0.9, 0.5), "severe"),
    ]
    cmds = controller.process_batch_detections(dets)
    assert len(cmds) == 2
    assert cmds[0]["nozzle_id"] == 1
    assert cmds[1]["nozzle_id"] == 3
    assert cmds[1]["duration_ms"] == 600


def test_telemetry_packet_generation():
    """Verify Firebase RTDB telemetry payload structure and savings calculation."""
    logger = TelemetryLogger("AGRO-TEST-BOT")
    sprays_log = [
        {"estimated_chemical_ml": 3.75, "nozzle_id": 1},
        {"estimated_chemical_ml": 7.50, "nozzle_id": 2},
    ]
    packet = logger.build_telemetry_packet(
        battery_voltage=12.4,
        solar_power_watts=48.5,
        sprays_log=sprays_log,
    )
    assert packet["robot_id"] == "AGRO-TEST-BOT"
    assert packet["telemetry"]["system_status"] == "ONLINE"
    assert packet["telemetry"]["battery_voltage"] == 12.4
    assert packet["telemetry"]["solar_power_watts"] == 48.5
    assert packet["operation_metrics"]["active_sprays_count"] == 2
    assert packet["operation_metrics"]["targeted_chemical_ml"] == 11.25
    # Benchmark: 2 * 35.0 = 70.0 ml. Targeted: 11.25 ml. Saved: 58.75 ml (~83.9% savings)
    assert packet["operation_metrics"]["chemical_savings_percentage"] > 70.0


def test_telemetry_low_battery_state():
    """Verify low battery alert trigger."""
    logger = TelemetryLogger()
    packet = logger.build_telemetry_packet(
        battery_voltage=10.8,
        solar_power_watts=5.0,
        sprays_log=[],
    )
    assert packet["telemetry"]["system_status"] == "LOW_BATTERY"
    assert packet["telemetry"]["battery_percentage"] == 0
