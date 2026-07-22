"""Streamlit-free JRP form logic: builds/reads the same dict shape `jrp_config.py` parses, so it
can be unit-tested without a Streamlit runtime and reused unchanged by `app.py`.
"""

from __future__ import annotations

from typing import Any

import yaml

from hr_digital_employee.scoring_engine.jrp_config import parse_jrp_config
from hr_digital_employee.scoring_engine.models import (
    JRP,
    Dimension,
    MatchingCurve,
    WeightedCriterion,
    WeightTemplate,
)
from hr_digital_employee.scoring_engine.weight_templates import preset_weights

DIMENSION_ORDER: tuple[Dimension, ...] = (
    Dimension.MANDATORY_SKILLS,
    Dimension.EXPERIENCE_TENURE,
    Dimension.EDUCATIONAL_LEVEL,
    Dimension.PROJECT_RELEVANCE,
)
"""Every existing weight template scores all four dimensions (weight_templates.py) -- the form
always shows one row per dimension in this fixed order, rather than letting HR add/remove
dimensions freely."""


def default_weighted_criteria(template: WeightTemplate) -> list[dict[str, Any]]:
    """One blank row per dimension, pre-filled with `template`'s preset weight -- the starting
    point for a brand-new JRP."""
    presets = preset_weights(template)
    return [
        {
            "dimension": dimension.value,
            "weight": presets[dimension],
            "curve": MatchingCurve.LINEAR.value,
            "required_skills": [],
            "required_years": None,
            "required_education_level": None,
            "required_project_count": None,
        }
        for dimension in DIMENSION_ORDER
    ]


def jrp_to_editable_dict(jrp: JRP) -> dict[str, Any]:
    """The inverse of `parse_jrp_config`: turns an already-loaded JRP back into the dict shape a
    YAML file parses into, so an existing JRP can be reopened for editing."""
    by_dimension: dict[Dimension, WeightedCriterion] = {
        criterion.dimension: criterion for criterion in jrp.weighted_criteria
    }
    weighted_criteria: list[dict[str, Any]] = []
    for dimension in DIMENSION_ORDER:
        criterion = by_dimension.get(dimension)
        if criterion is None:
            continue
        weighted_criteria.append(
            {
                "dimension": criterion.dimension.value,
                "weight": criterion.weight,
                "curve": criterion.curve.value,
                "required_skills": list(criterion.required_skills),
                "required_years": criterion.required_years,
                "required_education_level": (
                    criterion.required_education_level.name.lower()
                    if criterion.required_education_level is not None
                    else None
                ),
                "required_project_count": criterion.required_project_count,
            }
        )

    must_have = [
        {
            "kind": entry.kind.value,
            "label": entry.label,
            "required_skill": entry.required_skill,
            "minimum_years": entry.minimum_years,
        }
        for entry in jrp.must_have_criteria
    ]

    return {
        "jrp_id": jrp.jrp_id,
        "role_name": jrp.role_name,
        "version": jrp.version,
        "weight_template": jrp.weight_template.value,
        "must_have": must_have,
        "weighted_criteria": weighted_criteria,
        "tier_thresholds": {
            "high_match_min": jrp.tier_thresholds.high_match_min,
            "mid_match_min": jrp.tier_thresholds.mid_match_min,
        },
    }


def validate_jrp_dict(raw: dict[str, Any]) -> JRP:
    """Parses/validates a form-built dict the same way `load_jrp_from_yaml` validates a file --
    raises `JRPConfigError` on anything invalid -- so the editor and the CLI can never disagree
    about what counts as a valid JRP."""
    return parse_jrp_config(raw, source="<jrp-editor>")


def weighted_criteria_total(weighted_criteria: list[dict[str, Any]]) -> float:
    """Live running total for the UI's weight-sum indicator -- `JRP.__post_init__` requires this
    to equal 100 before the config will validate."""
    return sum(float(entry["weight"]) for entry in weighted_criteria)


def build_yaml_text(raw: dict[str, Any]) -> str:
    """Renders a form-built dict as YAML in the same field order HR filled the form in, rather
    than `yaml.safe_dump`'s default alphabetical key sort."""
    return yaml.safe_dump(raw, sort_keys=False, allow_unicode=True)
