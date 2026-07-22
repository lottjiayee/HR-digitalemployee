"""Tests for loading a JRP from a YAML configuration file (FR-6)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from hr_digital_employee.scoring_engine.jrp_config import (
    JRPConfigError,
    load_jrp_from_yaml,
    parse_jrp_config,
)
from hr_digital_employee.scoring_engine.models import (
    JRP,
    Dimension,
    EducationLevel,
    MatchingCurve,
    MustHaveKind,
    Tier,
    WeightTemplate,
)

FULL_CONFIG = """
jrp_id: backend-engineer
role_name: Backend Engineer
version: 1
weight_template: general

must_have:
  - kind: required_skill
    label: Must know Python
    required_skill: Python

weighted_criteria:
  - dimension: mandatory_skills
    curve: linear
    required_skills: [Python, SQL]
  - dimension: experience_tenure
    curve: buffered
    required_years: 5
  - dimension: educational_level
    curve: linear
    required_education_level: bachelor
  - dimension: project_relevance
    curve: linear
    required_project_count: 2

tier_thresholds:
  high_match_min: 85
  mid_match_min: 65
"""

MINIMAL_CONFIG = """
jrp_id: backend-engineer
role_name: Backend Engineer
version: 1
weight_template: general

weighted_criteria:
  - dimension: mandatory_skills
    curve: linear
    required_skills: [Python]
  - dimension: experience_tenure
    curve: linear
    required_years: 5
  - dimension: educational_level
    curve: linear
    required_education_level: bachelor
  - dimension: project_relevance
    curve: linear
    required_project_count: 2
"""


def _parse(config_text: str) -> JRP:
    return parse_jrp_config(yaml.safe_load(config_text))


def test_parses_a_full_config() -> None:
    jrp = _parse(FULL_CONFIG)

    assert jrp.jrp_id == "backend-engineer"
    assert jrp.role_name == "Backend Engineer"
    assert jrp.version == 1
    assert jrp.weight_template is WeightTemplate.GENERAL
    assert len(jrp.must_have_criteria) == 1
    assert jrp.must_have_criteria[0].kind is MustHaveKind.REQUIRED_SKILL
    assert jrp.must_have_criteria[0].required_skill == "Python"
    assert jrp.tier_thresholds.high_match_min == 85.0
    assert jrp.tier_thresholds.mid_match_min == 65.0


def test_weighted_criteria_are_parsed_with_correct_types() -> None:
    jrp = _parse(FULL_CONFIG)
    by_dimension = {c.dimension: c for c in jrp.weighted_criteria}

    skills = by_dimension[Dimension.MANDATORY_SKILLS]
    assert skills.curve is MatchingCurve.LINEAR
    assert skills.required_skills == ("Python", "SQL")

    experience = by_dimension[Dimension.EXPERIENCE_TENURE]
    assert experience.curve is MatchingCurve.BUFFERED
    assert experience.required_years == 5.0

    education = by_dimension[Dimension.EDUCATIONAL_LEVEL]
    assert education.required_education_level is EducationLevel.BACHELOR


def test_omitted_weight_falls_back_to_the_template_preset() -> None:
    jrp = _parse(FULL_CONFIG)
    by_dimension = {c.dimension: c for c in jrp.weighted_criteria}

    # General template preset: Mandatory Skills 40, Experience Tenure 30, Educational Level 15,
    # Project Relevance 15 -- none of this config's entries set `weight` explicitly.
    assert by_dimension[Dimension.MANDATORY_SKILLS].weight == 40.0
    assert by_dimension[Dimension.EXPERIENCE_TENURE].weight == 30.0
    assert by_dimension[Dimension.EDUCATIONAL_LEVEL].weight == 15.0
    assert by_dimension[Dimension.PROJECT_RELEVANCE].weight == 15.0


def test_config_without_tier_thresholds_uses_the_defaults() -> None:
    jrp = _parse(MINIMAL_CONFIG)

    assert jrp.tier_thresholds.high_match_min == 80.0
    assert jrp.tier_thresholds.mid_match_min == 60.0


def test_config_without_must_have_section_is_valid() -> None:
    jrp = _parse(MINIMAL_CONFIG)

    assert jrp.must_have_criteria == ()


def test_load_jrp_from_yaml_reads_a_real_file(tmp_path: Path) -> None:
    config_path = tmp_path / "backend-engineer.yaml"
    config_path.write_text(FULL_CONFIG, encoding="utf-8")

    jrp = load_jrp_from_yaml(config_path)

    assert jrp.jrp_id == "backend-engineer"


def test_unrecognized_weight_template_raises_jrp_config_error() -> None:
    config = FULL_CONFIG.replace("weight_template: general", "weight_template: nonsense")

    with pytest.raises(JRPConfigError):
        _parse(config)


def test_unrecognized_education_level_raises_a_clear_error() -> None:
    config = FULL_CONFIG.replace(
        "required_education_level: bachelor", "required_education_level: highschool"
    )

    with pytest.raises(JRPConfigError, match="unrecognized required_education_level"):
        _parse(config)


def test_missing_required_key_raises_jrp_config_error() -> None:
    config = FULL_CONFIG.replace("jrp_id: backend-engineer\n", "")

    with pytest.raises(JRPConfigError, match="missing required key"):
        _parse(config)


def test_non_mapping_top_level_raises_jrp_config_error() -> None:
    with pytest.raises(JRPConfigError, match="top level must be a mapping"):
        parse_jrp_config(["not", "a", "mapping"])


def test_invalid_yaml_syntax_raises_jrp_config_error(tmp_path: Path) -> None:
    config_path = tmp_path / "broken.yaml"
    config_path.write_text("jrp_id: [unclosed", encoding="utf-8")

    with pytest.raises(JRPConfigError, match="not valid YAML"):
        load_jrp_from_yaml(config_path)


def test_weight_still_sums_to_100_after_parsing() -> None:
    jrp = _parse(FULL_CONFIG)
    assert sum(c.weight for c in jrp.weighted_criteria) == 100.0
    assert jrp.tier_thresholds.classify(90.0) is Tier.HIGH_MATCH


def test_non_numeric_minimum_years_raises_jrp_config_error_not_a_later_crash() -> None:
    # Regression: this used to parse successfully (no JRPConfigError) and only crash later, mid-
    # scoring, with a TypeError comparing int >= str inside engine.py -- caught here instead.
    config = FULL_CONFIG.replace(
        "  - kind: required_skill\n    label: Must know Python\n    required_skill: Python\n",
        "  - kind: minimum_years_experience\n    label: Must have experience\n"
        "    minimum_years: five\n",
    )

    with pytest.raises(JRPConfigError):
        _parse(config)


def test_negative_minimum_years_raises_jrp_config_error() -> None:
    config = FULL_CONFIG.replace(
        "  - kind: required_skill\n    label: Must know Python\n    required_skill: Python\n",
        "  - kind: minimum_years_experience\n    label: Must have experience\n"
        "    minimum_years: -5\n",
    )

    with pytest.raises(JRPConfigError):
        _parse(config)


def test_non_mapping_tier_thresholds_raises_jrp_config_error_not_a_later_crash() -> None:
    # Regression: _parse_tier_thresholds assumed a mapping and called .get() on it unconditionally
    # -- a YAML list here raised an uncaught AttributeError instead of a clean JRPConfigError.
    config = FULL_CONFIG.replace(
        "tier_thresholds:\n  high_match_min: 85\n  mid_match_min: 65\n",
        "tier_thresholds: [1, 2, 3]\n",
    )

    with pytest.raises(JRPConfigError):
        _parse(config)


def test_scalar_required_skills_raises_jrp_config_error_not_silent_char_splitting() -> None:
    # Regression: a bare string here (HR forgetting the `[...]`) used to pass through `tuple(...)`
    # silently as one-character "skills" ('P', 'y', 't', 'h', ...) instead of raising -- tanking
    # the mandatory_skills score with no diagnostic surfaced at all.
    config = FULL_CONFIG.replace("required_skills: [Python, SQL]", "required_skills: Python")

    with pytest.raises(JRPConfigError, match="required_skills must be a list"):
        _parse(config)


def test_non_string_required_skills_element_raises_jrp_config_error_not_a_later_crash() -> None:
    # Regression: a non-string element (e.g. a YAML int) passed the list/tuple type check and
    # loaded with zero further validation, then crashed later, mid-scoring, the moment
    # skill-ontology matching called a string method on it.
    config = FULL_CONFIG.replace("required_skills: [Python, SQL]", "required_skills: [123, 456]")

    with pytest.raises(JRPConfigError, match="required_skills must all be strings"):
        _parse(config)


def test_non_string_required_education_level_raises_jrp_config_error_not_a_later_crash() -> None:
    # Regression: a non-string value (e.g. a YAML int) crashed with an unrelated AttributeError
    # (`'int' object has no attribute 'upper'`) instead of a clean JRPConfigError.
    config = FULL_CONFIG.replace(
        "required_education_level: bachelor", "required_education_level: 5"
    )

    with pytest.raises(JRPConfigError, match="required_education_level must be a string"):
        _parse(config)
