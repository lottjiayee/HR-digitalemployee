"""Load a JRP from a human-editable YAML file (FR-6: HR defines a JRP per role, selecting a
weight template and fine-tuning weights). A stand-in for the real JRP configuration UI Module 5
owns (design.md §3.8) -- see ASSUMPTIONS.md.

Example file:

    jrp_id: backend-engineer
    role_name: Backend Engineer
    version: 1
    weight_template: general        # see WeightTemplate for the full list

    must_have:
      - kind: required_skill
        label: Must know Python
        required_skill: Python

    weighted_criteria:
      - dimension: mandatory_skills
        curve: linear
        required_skills: [Python, SQL]
        # weight: 40                # optional -- omit to use the template's preset weight
      - dimension: experience_tenure
        curve: buffered
        required_years: 5
      - dimension: educational_level
        curve: linear
        required_education_level: bachelor
      - dimension: project_relevance
        curve: linear
        required_project_count: 2

    tier_thresholds:                # optional -- omit to use the 80/60 defaults
      high_match_min: 80
      mid_match_min: 60
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from hr_digital_employee.scoring_engine.models import (
    JRP,
    Dimension,
    EducationLevel,
    MatchingCurve,
    MustHaveCriterion,
    MustHaveKind,
    TierThresholds,
    WeightedCriterion,
    WeightTemplate,
)
from hr_digital_employee.scoring_engine.weight_templates import preset_weights


class JRPConfigError(ValueError):
    """The YAML file is well-formed YAML but not a valid JRP configuration."""


def load_jrp_from_yaml(path: Path) -> JRP:
    """Read and parse a JRP configuration file. Raises `JRPConfigError` on anything invalid --
    an unrecognized `dimension`/`curve`/`weight_template` name, a missing required key, etc."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise JRPConfigError(f"{path}: not valid YAML: {error}") from error
    return parse_jrp_config(raw, source=str(path))


def parse_jrp_config(raw: Any, source: str = "<config>") -> JRP:
    if not isinstance(raw, dict):
        raise JRPConfigError(f"{source}: top level must be a mapping, got {type(raw).__name__}")

    try:
        weight_template = WeightTemplate(raw["weight_template"])
        return JRP(
            jrp_id=raw["jrp_id"],
            role_name=raw["role_name"],
            version=raw["version"],
            weight_template=weight_template,
            must_have_criteria=tuple(
                _parse_must_have(entry, source) for entry in raw.get("must_have", [])
            ),
            weighted_criteria=tuple(
                _parse_weighted_criterion(entry, weight_template, source)
                for entry in raw["weighted_criteria"]
            ),
            tier_thresholds=_parse_tier_thresholds(raw.get("tier_thresholds")),
        )
    except KeyError as error:
        raise JRPConfigError(f"{source}: missing required key {error}") from error
    except (ValueError, TypeError) as error:
        raise JRPConfigError(f"{source}: {error}") from error


def _parse_must_have(entry: dict[str, Any], source: str) -> MustHaveCriterion:
    return MustHaveCriterion(
        kind=MustHaveKind(entry["kind"]),
        label=entry["label"],
        required_skill=entry.get("required_skill"),
        minimum_years=entry.get("minimum_years"),
    )


def _parse_weighted_criterion(
    entry: dict[str, Any], weight_template: WeightTemplate, source: str
) -> WeightedCriterion:
    dimension = Dimension(entry["dimension"])
    weight = entry.get("weight")
    if weight is None:
        weight = preset_weights(weight_template)[dimension]

    education_level = entry.get("required_education_level")
    required_skills = entry.get("required_skills")

    return WeightedCriterion(
        dimension=dimension,
        weight=float(weight),
        curve=MatchingCurve(entry["curve"]),
        required_skills=tuple(required_skills) if required_skills else (),
        required_years=entry.get("required_years"),
        required_education_level=(
            _parse_education_level(education_level) if education_level is not None else None
        ),
        required_project_count=entry.get("required_project_count"),
    )


def _parse_education_level(value: str) -> EducationLevel:
    # EducationLevel is an IntEnum (values 0-5) -- look it up by member *name*, not by value,
    # so a YAML string like "bachelor" resolves to EducationLevel.BACHELOR.
    try:
        return EducationLevel[value.upper()]
    except KeyError:
        valid = ", ".join(level.name.lower() for level in EducationLevel)
        raise ValueError(
            f"unrecognized required_education_level {value!r}, expected one of: {valid}"
        ) from None


def _parse_tier_thresholds(entry: dict[str, Any] | None) -> TierThresholds:
    if entry is None:
        return TierThresholds()
    return TierThresholds(
        high_match_min=float(entry.get("high_match_min", 80.0)),
        mid_match_min=float(entry.get("mid_match_min", 60.0)),
    )
