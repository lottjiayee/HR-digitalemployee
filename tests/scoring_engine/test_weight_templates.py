"""Tests for weight-template presets (test.md T2.12)."""

from __future__ import annotations

from hr_digital_employee.scoring_engine.models import Dimension, WeightTemplate
from hr_digital_employee.scoring_engine.weight_templates import preset_weights

_EXPECTED = {
    WeightTemplate.GENERAL: {
        Dimension.MANDATORY_SKILLS: 40.0,
        Dimension.EXPERIENCE_TENURE: 30.0,
        Dimension.EDUCATIONAL_LEVEL: 15.0,
        Dimension.PROJECT_RELEVANCE: 15.0,
    },
    WeightTemplate.SENIOR_TECHNICAL: {
        Dimension.MANDATORY_SKILLS: 35.0,
        Dimension.EXPERIENCE_TENURE: 35.0,
        Dimension.EDUCATIONAL_LEVEL: 10.0,
        Dimension.PROJECT_RELEVANCE: 20.0,
    },
    WeightTemplate.JUNIOR_GRADUATE: {
        Dimension.MANDATORY_SKILLS: 45.0,
        Dimension.EXPERIENCE_TENURE: 5.0,
        Dimension.EDUCATIONAL_LEVEL: 30.0,
        Dimension.PROJECT_RELEVANCE: 20.0,
    },
    WeightTemplate.MANAGERIAL: {
        Dimension.MANDATORY_SKILLS: 25.0,
        Dimension.EXPERIENCE_TENURE: 30.0,
        Dimension.EDUCATIONAL_LEVEL: 15.0,
        Dimension.PROJECT_RELEVANCE: 30.0,
    },
    WeightTemplate.LICENSED_COMPLIANCE: {
        Dimension.MANDATORY_SKILLS: 50.0,
        Dimension.EXPERIENCE_TENURE: 20.0,
        Dimension.EDUCATIONAL_LEVEL: 20.0,
        Dimension.PROJECT_RELEVANCE: 10.0,
    },
}


def test_t2_12_every_preset_matches_the_requirement_table_exactly() -> None:
    for template, expected_weights in _EXPECTED.items():
        assert preset_weights(template) == expected_weights


def test_every_preset_sums_to_100() -> None:
    for template in WeightTemplate:
        assert sum(preset_weights(template).values()) == 100.0
