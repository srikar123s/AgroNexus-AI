"""Stable disease-evidence API backed by the intentionally dummy classifier adapter."""

from __future__ import annotations

from typing import Any

from .adapters import DiseaseClassificationAdapter


def analyze_disease_evidence(
    *,
    crop: str,
    crop_stage: str,
    sample_id: str | None = None,
    image_name: str | None = None,
) -> dict[str, Any]:
    return DiseaseClassificationAdapter().analyze(
        crop=crop,
        crop_stage=crop_stage,
        sample_id=sample_id,
        image_name=image_name,
    )
