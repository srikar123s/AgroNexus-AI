"""Explicit ML integration boundaries.

These adapters intentionally return clearly marked dummy values.  They do not
load model artifacts or perform inference; production model integrations can
replace an adapter without changing decision-service contracts.
"""

from __future__ import annotations

from typing import Any


class DummyModelAdapter:
    task_type = "unknown"

    def predict(self, features: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "dummy": True,
            "task_type": self.task_type,
            "model_loaded": False,
            "prediction": None,
            "message": "Dummy adapter only; no real model was loaded.",
        }


class DiseaseClassificationAdapter(DummyModelAdapter):
    task_type = "disease_classification"

    def analyze(self, *, crop: str, crop_stage: str, sample_id: str | None, image_name: str | None) -> dict[str, Any]:
        crop_name = (crop or "Tomato").strip()
        crop_key = crop_name.lower().split()[0]
        sample_key = (sample_id or "").lower()
        image_key = (image_name or "").lower()
        provider = f"image-check-{crop_key}"
        if "healthy" in sample_key or "healthy" in image_key or "normal" in image_key:
            return self._result(provider, crop_name, crop_stage, False, "Healthy Crop (No Disease Detected)", "low", 97, "Healthy", "Leaves show uniform green colour without fungal lesions or dark spots.", .97, .95, crop_key)
        if "late" in sample_key or "mod" in sample_key or "spot" in image_key:
            return self._result(provider, crop_name, crop_stage, True, f"{crop_name} Foliar Blight / Leaf Spot", "moderate", 89, "Moderate Infection", "Water-soaked marks along leaf margins are consistent with wet, humid conditions.", .89, .91, crop_key)
        return self._result(provider, crop_name, crop_stage, True, f"{crop_name} Early Blight (Alternaria solani)", "high", 94, "Disease Detected", "Concentric dark rings on the leaves are consistent with early blight symptoms.", .94, .93, crop_key)

    @staticmethod
    def _result(provider: str, crop: str, crop_stage: str, detected: bool, disease_name: str,
                severity: str, confidence: int, health_label: str, summary: str,
                quality: float, reliability: float, crop_key: str) -> dict[str, Any]:
        return {
            "provider": provider, "crop": crop, "crop_stage": crop_stage,
            "detected": detected, "disease_name": disease_name, "severity": severity,
            "confidence": confidence, "health_label": health_label, "summary": summary,
            "dummy": True,
            "evidence_item": {
                "attribute": "disease_severity", "value": severity, "quality": quality,
                "reliability": reliability, "source_id": f"{provider}-{crop_key}",
            },
        }


class DiseaseSeverityAdapter(DummyModelAdapter):
    task_type = "disease_severity"


class CropSuitabilityAdapter(DummyModelAdapter):
    task_type = "crop_suitability"


class FertilizerSuitabilityAdapter(DummyModelAdapter):
    task_type = "fertilizer_suitability"


class IrrigationRequirementAdapter(DummyModelAdapter):
    task_type = "irrigation_requirement"


class YieldPredictionAdapter(DummyModelAdapter):
    task_type = "yield_prediction"


class AgriculturalRiskPredictionAdapter(DummyModelAdapter):
    task_type = "agricultural_risk_prediction"


MODEL_ADAPTERS = {
    adapter().task_type: adapter
    for adapter in (
        DiseaseClassificationAdapter,
        DiseaseSeverityAdapter,
        CropSuitabilityAdapter,
        FertilizerSuitabilityAdapter,
        IrrigationRequirementAdapter,
        YieldPredictionAdapter,
        AgriculturalRiskPredictionAdapter,
    )
}
