"""Streamlit form for creating/editing a JRP YAML file -- the same file `hr-digital-employee`
reads -- without HR touching YAML or the command line directly.

Run via the `hr-digital-employee-jrp-editor` console script (see launcher.py), or directly with
`streamlit run src/hr_digital_employee/jrp_editor/app.py`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from hr_digital_employee.jrp_editor.config_builder import (
    build_yaml_text,
    default_weighted_criteria,
    jrp_to_editable_dict,
    validate_jrp_dict,
    weighted_criteria_total,
)
from hr_digital_employee.scoring_engine.jrp_config import JRPConfigError, load_jrp_from_yaml
from hr_digital_employee.scoring_engine.models import (
    EDUCATIONAL_LEVEL_WEIGHT_GUIDELINE_MAX,
    EducationLevel,
    MatchingCurve,
    MustHaveKind,
    WeightTemplate,
)

st.set_page_config(page_title="JRP Editor", layout="wide")
st.title("Job Requirement Profile Editor")
st.caption(
    "A temporary convenience form over the same YAML JRP config the `hr-digital-employee` CLI "
    "reads -- not Module 5's real dashboard (no auth, no history, no Pass/Reject). See "
    "ASSUMPTIONS.md."
)

def _apply_weighted_criteria_to_widget_state(rows: list[dict[str, Any]]) -> None:
    """Writes each row's values directly into the *widgets' own* session_state keys.

    Once a widget with a given `key=` has been instantiated, only `st.session_state[key]` -- not
    a later `value=` argument passed on a subsequent rerun -- determines what it displays (this is
    Streamlit's documented behavior, confirmed here via `AppTest`: a `value=` on an already-keyed
    widget is silently ignored). Loading a file or switching weight templates must therefore write
    these keys directly to actually change what's shown; just updating the plain
    `st.session_state.weighted_criteria` list looked correct but never reached the widgets at all.
    """
    for row in rows:
        dimension = row["dimension"]
        st.session_state[f"weight_{dimension}"] = float(row["weight"])
        st.session_state[f"curve_{dimension}"] = row["curve"]
        if dimension == "mandatory_skills":
            st.session_state[f"skills_{dimension}"] = ", ".join(row["required_skills"])
        elif dimension == "experience_tenure":
            st.session_state[f"years_{dimension}"] = float(row["required_years"] or 0.0)
        elif dimension == "educational_level":
            st.session_state[f"edu_{dimension}"] = row["required_education_level"] or "bachelor"
        elif dimension == "project_relevance":
            st.session_state[f"proj_{dimension}"] = int(row["required_project_count"] or 0)
    st.session_state.weighted_criteria = rows


if "weighted_criteria" not in st.session_state:
    _apply_weighted_criteria_to_widget_state(default_weighted_criteria(WeightTemplate.GENERAL))
    st.session_state._applied_template = WeightTemplate.GENERAL.value
if "must_have" not in st.session_state:
    st.session_state.must_have = []

with st.sidebar:
    st.header("Load an existing JRP")
    existing_path = st.text_input("Path to a JRP YAML file", value="")
    if st.button("Load") and existing_path:
        try:
            loaded_jrp = load_jrp_from_yaml(Path(existing_path))
        except JRPConfigError as error:
            st.error(str(error))
        except OSError as error:
            st.error(f"Could not read {existing_path}: {error}")
        else:
            loaded = jrp_to_editable_dict(loaded_jrp)
            st.session_state.jrp_id = loaded["jrp_id"]
            st.session_state.role_name = loaded["role_name"]
            st.session_state.version = loaded["version"]
            st.session_state.weight_template = loaded["weight_template"]
            st.session_state._applied_template = loaded["weight_template"]
            _apply_weighted_criteria_to_widget_state(loaded["weighted_criteria"])
            st.session_state.must_have = loaded["must_have"]
            st.session_state.high_match_min = loaded["tier_thresholds"]["high_match_min"]
            st.session_state.mid_match_min = loaded["tier_thresholds"]["mid_match_min"]
            st.success(f"Loaded {loaded['jrp_id']} (v{loaded['version']})")

if "jrp_id" not in st.session_state:
    st.session_state.jrp_id = ""
if "role_name" not in st.session_state:
    st.session_state.role_name = ""
if "version" not in st.session_state:
    st.session_state.version = 1
if "weight_template" not in st.session_state:
    st.session_state.weight_template = WeightTemplate.GENERAL.value

left, right = st.columns(2)
with left:
    jrp_id = st.text_input("JRP ID", key="jrp_id")
    role_name = st.text_input("Role name", key="role_name")
with right:
    version = int(st.number_input("Version", min_value=1, step=1, key="version"))
    template_options = [t.value for t in WeightTemplate]
    weight_template_value = st.selectbox("Weight template", template_options, key="weight_template")
    if weight_template_value != st.session_state.get("_applied_template"):
        _apply_weighted_criteria_to_widget_state(
            default_weighted_criteria(WeightTemplate(weight_template_value))
        )
        st.session_state._applied_template = weight_template_value
        st.info(f"Weights reset to the {weight_template_value} template's defaults.")

st.subheader("Weighted criteria")
st.caption("One row per scored dimension. Weights across all four rows must sum to 100.")

curve_options = [c.value for c in MatchingCurve]
education_options = [level.name.lower() for level in EducationLevel]

updated_rows: list[dict[str, Any]] = []
for row in st.session_state.weighted_criteria:
    dimension = row["dimension"]
    st.markdown(f"**{dimension.replace('_', ' ').title()}**")
    cols = st.columns(4)
    weight = cols[0].number_input(
        "Weight", min_value=0.0, max_value=100.0, key=f"weight_{dimension}"
    )
    curve = cols[1].selectbox("Curve", curve_options, key=f"curve_{dimension}")
    new_row = dict(row, weight=weight, curve=curve)

    if dimension == "mandatory_skills":
        skills_text = cols[2].text_input(
            "Required skills (comma-separated)", key=f"skills_{dimension}"
        )
        new_row["required_skills"] = [s.strip() for s in skills_text.split(",") if s.strip()]
    elif dimension == "experience_tenure":
        new_row["required_years"] = cols[2].number_input(
            "Required years", min_value=0.0, key=f"years_{dimension}"
        )
    elif dimension == "educational_level":
        new_row["required_education_level"] = cols[2].selectbox(
            "Required education level", education_options, key=f"edu_{dimension}"
        )
    elif dimension == "project_relevance":
        new_row["required_project_count"] = int(
            cols[2].number_input(
                "Required project count", min_value=0, step=1, key=f"proj_{dimension}"
            )
        )
    updated_rows.append(new_row)
st.session_state.weighted_criteria = updated_rows

total_weight = weighted_criteria_total(st.session_state.weighted_criteria)
if abs(total_weight - 100.0) < 0.01:
    st.success(f"Total weight: {total_weight:.1f} / 100")
else:
    st.warning(f"Total weight: {total_weight:.1f} / 100 -- must equal 100 before this JRP is valid")

for row in st.session_state.weighted_criteria:
    is_educational_level = row["dimension"] == "educational_level"
    if is_educational_level and row["weight"] > EDUCATIONAL_LEVEL_WEIGHT_GUIDELINE_MAX:
        st.warning(
            f"Educational Level weight is {row['weight']}%, above the "
            f"{EDUCATIONAL_LEVEL_WEIGHT_GUIDELINE_MAX}% guideline default (module-2 doc §4)."
        )

st.subheader("Must-have criteria (gating flags)")
st.caption(
    "A candidate failing any of these still gets a full weighted score -- the failure is flagged "
    "alongside it for HR to review, never an auto-reject (SOP 2.2.2/2.2.4; module-2 doc §4)."
)
_MUST_HAVE_COLUMNS = ["kind", "label", "required_skill", "minimum_years"]
must_have_df = pd.DataFrame(st.session_state.must_have, columns=_MUST_HAVE_COLUMNS)
edited_must_have_df = st.data_editor(
    must_have_df,
    num_rows="dynamic",
    column_config={
        "kind": st.column_config.SelectboxColumn(options=[k.value for k in MustHaveKind]),
    },
    key="must_have_editor",
)
st.session_state.must_have = edited_must_have_df.to_dict("records")

if "high_match_min" not in st.session_state:
    st.session_state.high_match_min = 80.0
if "mid_match_min" not in st.session_state:
    st.session_state.mid_match_min = 60.0

st.subheader("Tier thresholds (optional)")
tier_cols = st.columns(2)
high_match_min = tier_cols[0].number_input(
    "High Match minimum", min_value=0.0, max_value=100.0, key="high_match_min"
)
mid_match_min = tier_cols[1].number_input(
    "Mid Match minimum", min_value=0.0, max_value=100.0, key="mid_match_min"
)

raw_config: dict[str, Any] = {
    "jrp_id": jrp_id,
    "role_name": role_name,
    "version": version,
    "weight_template": weight_template_value,
    "must_have": st.session_state.must_have,
    "weighted_criteria": st.session_state.weighted_criteria,
    "tier_thresholds": {"high_match_min": high_match_min, "mid_match_min": mid_match_min},
}

st.subheader("Validation")
validated_jrp = None
try:
    validated_jrp = validate_jrp_dict(raw_config)
except JRPConfigError as error:
    st.error(f"Not valid yet: {error}")
else:
    st.success("Valid JRP -- ready to save.")

st.subheader("Save")
save_path = st.text_input("Save to path", value=f"{jrp_id or 'new-jrp'}.yaml")
if st.button("Save YAML", disabled=validated_jrp is None):
    Path(save_path).write_text(build_yaml_text(raw_config), encoding="utf-8")
    st.success(f"Saved to {save_path}")

with st.expander("Preview generated YAML"):
    st.code(build_yaml_text(raw_config), language="yaml")
