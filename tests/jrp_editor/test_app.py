"""Tests for the JRP editor's Streamlit UI (app.py), exercised via Streamlit's `AppTest` harness.

Skipped entirely when the optional `ui` extra (streamlit) isn't installed -- config_builder.py's
own tests cover the Streamlit-free logic and always run.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("streamlit")

from streamlit.testing.v1 import AppTest  # noqa: E402

_APP_PATH = str(
    Path(__file__).resolve().parents[2] / "src" / "hr_digital_employee" / "jrp_editor" / "app.py"
)

_RUN_TIMEOUT = 15

_SENIOR_ROLE_YAML = """\
jrp_id: senior-role
role_name: Senior Engineer
version: 1
weight_template: senior_technical
weighted_criteria:
  - dimension: mandatory_skills
    curve: linear
    required_skills: [Python, Go]
    weight: 35
  - dimension: experience_tenure
    curve: linear
    required_years: 8
    weight: 35
  - dimension: educational_level
    curve: linear
    required_education_level: bachelor
    weight: 10
  - dimension: project_relevance
    curve: linear
    required_project_count: 3
    weight: 20
"""


def test_loading_a_jrp_actually_updates_the_weight_and_requirement_widgets(tmp_path: Path) -> None:
    # Regression: every per-dimension widget used a fixed key (e.g. "weight_mandatory_skills").
    # Once a keyed widget is instantiated, only st.session_state[key] -- not a later `value=`
    # argument -- determines what it displays. Loading a file used to update the plain
    # `weighted_criteria` list (and show a "Loaded" success message) while every widget kept
    # showing the *previous* template's stale defaults -- a false-positive confirmation that HR
    # was now editing the loaded JRP when they were actually still editing the old one.
    config_path = tmp_path / "senior-role.yaml"
    config_path.write_text(_SENIOR_ROLE_YAML, encoding="utf-8")

    at = AppTest.from_file(_APP_PATH)
    at.run(timeout=_RUN_TIMEOUT)
    assert at.number_input(key="weight_mandatory_skills").value == 40.0  # GENERAL preset default

    path_input = next(w for w in at.text_input if w.label == "Path to a JRP YAML file")
    path_input.set_value(str(config_path))
    next(b for b in at.button if b.label == "Load").click()
    at.run(timeout=_RUN_TIMEOUT)

    assert not at.exception
    jrp_id_input = next(w for w in at.text_input if w.label == "JRP ID")
    assert jrp_id_input.value == "senior-role"
    assert at.number_input(key="weight_mandatory_skills").value == 35.0
    skills_input = next(w for w in at.text_input if w.label == "Required skills (comma-separated)")
    assert skills_input.value == "Python, Go"
    assert at.number_input(key="years_experience_tenure").value == 8.0
    assert at.number_input(key="proj_project_relevance").value == 3
    assert at.selectbox(key="weight_template").value == "senior_technical"


def _find_must_have_editor(at: AppTest) -> object:
    def walk(node: object) -> object | None:
        if getattr(node, "type", None) == "dataframe" and getattr(node, "key", None) == (
            "must_have_editor"
        ):
            return node
        for child in getattr(node, "children", {}).values():
            found = walk(child)
            if found is not None:
                return found
        return None

    editor = walk(at.main)
    assert editor is not None, "must_have_editor widget not found"
    return editor


def test_must_have_table_has_its_columns_even_when_the_jrp_has_no_must_have_rows() -> None:
    # Regression: st.data_editor(st.session_state.must_have, ...) was passed a bare empty list on
    # every brand-new JRP (the common case -- none of the 5 weight-template presets seed a
    # must-have row). Streamlit infers a data_editor's schema from the data it's given, so an
    # empty list produced a table with zero columns -- kind/label/required_skill/minimum_years all
    # missing -- leaving HR with no way to add a must-have criterion through the form at all.
    at = AppTest.from_file(_APP_PATH)
    at.run(timeout=_RUN_TIMEOUT)
    assert not at.exception

    editor = _find_must_have_editor(at)
    schema = editor.proto.arrow_data.data
    for column in (b"kind", b"label", b"required_skill", b"minimum_years"):
        assert column in schema, f"column {column!r} missing from the must-have table's schema"


def test_switching_weight_template_actually_resets_the_weight_widgets() -> None:
    at = AppTest.from_file(_APP_PATH)
    at.run(timeout=_RUN_TIMEOUT)

    at.number_input(key="weight_mandatory_skills").set_value(55.0)
    at.run(timeout=_RUN_TIMEOUT)
    assert at.number_input(key="weight_mandatory_skills").value == 55.0

    at.selectbox(key="weight_template").set_value("senior_technical")
    at.run(timeout=_RUN_TIMEOUT)

    assert not at.exception
    assert at.number_input(key="weight_mandatory_skills").value == 35.0  # senior_technical preset
