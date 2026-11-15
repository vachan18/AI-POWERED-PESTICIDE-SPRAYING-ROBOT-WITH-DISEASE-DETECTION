"""
AGRO VISION — Leaf Disease Detection & Targeted Coordinate Mapping Module.
Processes vision inputs, evaluates foliage disease severity, and maps
detections to spray nozzle targeting coordinates.
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class DiseaseDetection:
    """Represents an identified plant disease instance."""
    disease_name: str
    confidence: float
    bbox: Tuple[float, float, float, float]  # (x_min, y_min, x_max, y_max) in [0, 1]
    severity: str  # "mild", "moderate", "severe"

    @property
    def center(self) -> Tuple[float, float]:
        """Calculates normalized center (cx, cy) of the diseased region."""
        cx = (self.bbox[0] + self.bbox[2]) / 2.0
        cy = (self.bbox[1] + self.bbox[3]) / 2.0
        return round(cx, 4), round(cy, 4)

    @property
    def area(self) -> float:
        """Calculates bounding box coverage area."""
        width = max(0.0, self.bbox[2] - self.bbox[0])
        height = max(0.0, self.bbox[3] - self.bbox[1])
        return round(width * height, 4)


class LeafDiseaseDetector:
    """
    Inference pipeline for plant leaf disease recognition.
    Integrates YOLOv8 / CNN inference output and applies thresholding,
    severity ranking, and nozzle targeting assignment.
    """

    CONFIDENCE_THRESHOLD = 0.50
    KNOWN_DISEASES = {
        "early_blight": 0.20,
        "late_blight": 0.40,
        "leaf_mold": 0.15,
        "septoria_leaf_spot": 0.15,
        "bacterial_spot": 0.35,
        "yellow_leaf_curl_virus": 0.50,
    }

    def __init__(self, min_confidence: float = CONFIDENCE_THRESHOLD):
        self.min_confidence = min_confidence

    def calculate_severity(self, disease_name: str, area: float) -> str:
        """
        Classifies infection severity based on affected leaf area
        and pathogen virulence weighting.
        """
        base_virulence = self.KNOWN_DISEASES.get(disease_name.lower(), 0.20)
        impact_score = area * 100.0 * (1.0 + base_virulence)

        if impact_score > 35.0:
            return "severe"
        elif impact_score > 12.0:
            return "moderate"
        return "mild"

    def filter_and_format_detections(
        self, raw_predictions: List[dict]
    ) -> List[DiseaseDetection]:
        """
        Filters raw inference predictions below confidence threshold
        and produces structured DiseaseDetection instances.
        """
        results = []
        for pred in raw_predictions:
            conf = pred.get("confidence", 0.0)
            if conf < self.min_confidence:
                continue

            bbox = pred.get("bbox", (0.0, 0.0, 0.0, 0.0))
            # Validate bounding box boundaries
            x1, y1, x2, y2 = bbox
            if not (0.0 <= x1 <= x2 <= 1.0 and 0.0 <= y1 <= y2 <= 1.0):
                continue

            disease = pred.get("class", "unknown_disease")
            area = (x2 - x1) * (y2 - y1)
            severity = self.calculate_severity(disease, area)

            results.append(
                DiseaseDetection(
                    disease_name=disease,
                    confidence=round(conf, 4),
                    bbox=(x1, y1, x2, y2),
                    severity=severity,
                )
            )
        return results
