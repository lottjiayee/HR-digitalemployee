"""Tests for the JRP-editor's Streamlit-free form logic (jrp_editor/config_builder.py)."""

from __future__ import annotations

from typing import Any

import pytest
import yaml

from hr_digital_employee.jrp_editor.config_builder import (
    build_yaml_text,
    default_weighted_criteria,
    jrp_to_editable_dict,
    validate_jrp_dict,
    weighted_criteria_total,
)
from hr_digital_employee.scoring_engine.jrp_config import JRPConfigError
from hr_digital_employee.scoring_engine.models import WeightTemplate


def _base_raw(weighted_criteria: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "jrp_id": "role-1",
        "role_name": "Backend Engineer",
        "version": 1,
        "weight_template": WeightTemplate.GENERAL.value,
        "must_have": [],
        "weighted_criteria": weighted_criteria,
        "tier_thresholds": {"high_match_min": 80.0, "mid_match_min": 60.0},
    }


def _fill_in_requirements(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The form's default rows have blank requirement fields (placeholders) -- fills them with
    plausible values so the resulting JRP actually validates."""
    for row in rows:
        if row["dimension"] == "mandatory_skills":
            row["required_skills"] = ["Python"]
        elif row["dimension"] == "experience_tenure":
            row["required_years"] = 5.0
        elif row["dimension"] == "educational_level":
            row["required_education_level"] = "bachelor"
        elif row["dimension"] == "project_relevance":
            row["required_project_count"] = 2
    return rows


@pytest.mark.parametrize("template", list(WeightTemplate))
def test_default_weighted_criteria_sums_to_100_for_every_template(
    template: WeightTemplate,
) -> None:
    rows = default_weighted_criteria(template)

    assert weighted_criteria_total(rows) == pytest.approx(100.0)


def test_default_weighted_criteria_has_one_row_per_dimension() -> None:
    rows = default_weighted_criteria(WeightTemplate.GENERAL)

    assert {row["dimension"] for row in rows} == {
        "mandatory_skills",
        "experience_tenure",
        "educational_level",
        "project_relevance",
    }


def test_blank_default_rows_do_not_validate_until_requirements_are_filled_in() -> None:
    # Regression guard: the form's starting point is intentionally incomplete (no required
    # skills/years/etc yet) -- it must not silently pass validation before HR fills those in.
    rows = default_weighted_criteria(WeightTemplate.GENERAL)

    with pytest.raises(JRPConfigError):
        validate_jrp_dict(_base_raw(rows))


def test_filled_in_default_rows_validate_successfully() -> None:
    rows = _fill_in_requirements(default_weighted_criteria(WeightTemplate.GENERAL))

    jrp = validate_jrp_dict(_base_raw(rows))

    assert jrp.jrp_id == "role-1"
    assert len(jrp.weighted_criteria) == 4


def test_jrp_to_editable_dict_round_trips_through_validate_jrp_dict() -> None:
    rows = _fill_in_requirements(default_weighted_criteria(WeightTemplate.SENIOR_TECHNICAL))
    original = validate_jrp_dict(_base_raw(rows))

    round_tripped = validate_jrp_dict(jrp_to_editable_dict(original))

    assert round_tripped == original


def test_build_yaml_text_round_trips_through_yaml_parsing() -> None:
    rows = _fill_in_requirements(default_weighted_criteria(WeightTemplate.GENERAL))
    raw = _base_raw(rows)

    yaml_text = build_yaml_text(raw)
    reloaded = yaml.safe_load(yaml_text)

    assert validate_jrp_dict(reloaded) == validate_jrp_dict(raw)


def test_build_yaml_text_keeps_jrp_id_as_the_first_key() -> None:
    # sort_keys=False -- confirms the YAML reads top-to-bottom the way HR filled the form in,
    # not yaml.safe_dump's default alphabetical key order.
    raw = _base_raw(_fill_in_requirements(default_weighted_criteria(WeightTemplate.GENERAL)))

    yaml_text = build_yaml_text(raw)

    assert yaml_text.splitlines()[0].startswith("jrp_id:")
