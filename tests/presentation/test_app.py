"""Tests for Module 5's comparison-table/drill-down dashboard (app.py), exercised via Streamlit's
`AppTest` harness.

Skipped entirely when the optional `ui` extra (streamlit) isn't installed -- dashboard_data.py's
own tests cover the Streamlit-free logic and always run.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("streamlit")

from streamlit.testing.v1 import AppTest  # noqa: E402

_APP_PATH = str(
    Path(__file__).resolve().parents[2] / "src" / "hr_digital_employee" / "presentation" / "app.py"
)

_RUN_TIMEOUT = 15

_JRP_CONFIG = """\
jrp_id: backend-engineer
role_name: Backend Engineer
version: 1
weight_template: general

weighted_criteria:
  - dimension: mandatory_skills
    curve: linear
    required_skills: [Python, SQL]
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

_STRONG_RESUME = (
    b"Skills:\nPython\nSQL\n\n"
    b"Projects:\nBuilt a data pipeline\nLed a small team\n\n"
    b"Working Experience:\n5 years at TechCorp as a backend engineer\n\n"
    b"Education:\nBachelor of Computer Science\n"
)


def test_running_the_dashboard_shows_a_scored_candidate_and_its_drill_down(
    tmp_path: Path,
) -> None:
    resumes_dir = tmp_path / "resumes"
    resumes_dir.mkdir()
    (resumes_dir / "candidate.pdf").write_bytes(_STRONG_RESUME)
    jrp_path = tmp_path / "backend-engineer.yaml"
    jrp_path.write_text(_JRP_CONFIG, encoding="utf-8")

    at = AppTest.from_file(_APP_PATH)
    at.run(timeout=_RUN_TIMEOUT)

    at.text_input(key="resumes_path").set_value(str(resumes_dir))
    at.text_input(key="jrp_path").set_value(str(jrp_path))
    at.button[0].click()
    at.run(timeout=_RUN_TIMEOUT)

    assert not at.exception
    assert any("Backend Engineer" in md.value for md in at.markdown) or any(
        "candidate.pdf" not in title.value for title in at.subheader
    )
    assert at.selectbox(key="selected_candidate").options
    assert "100.0" in at.metric[0].value


def test_an_invalid_jrp_path_shows_a_clean_error_not_a_crash(tmp_path: Path) -> None:
    resumes_dir = tmp_path / "resumes"
    resumes_dir.mkdir()

    at = AppTest.from_file(_APP_PATH)
    at.run(timeout=_RUN_TIMEOUT)

    at.text_input(key="resumes_path").set_value(str(resumes_dir))
    at.text_input(key="jrp_path").set_value(str(tmp_path / "does-not-exist.yaml"))
    at.button[0].click()
    at.run(timeout=_RUN_TIMEOUT)

    assert not at.exception
    assert any("Error loading JRP config" in e.value for e in at.error)


def test_a_blank_resumes_folder_shows_a_clean_error_not_a_silent_cwd_scan(
    tmp_path: Path,
) -> None:
    # Path("") resolves to the current working directory, which always exists -- an unvalidated
    # blank field would silently scan and score whatever unrelated files happen to sit in the
    # launch directory, with no indication the field was ever empty.
    jrp_path = tmp_path / "backend-engineer.yaml"
    jrp_path.write_text(_JRP_CONFIG, encoding="utf-8")

    at = AppTest.from_file(_APP_PATH)
    at.run(timeout=_RUN_TIMEOUT)

    at.text_input(key="resumes_path").set_value("")
    at.text_input(key="jrp_path").set_value(str(jrp_path))
    at.button[0].click()
    at.run(timeout=_RUN_TIMEOUT)

    assert not at.exception
    assert any("Resumes folder is required" in e.value for e in at.error)
    assert at.session_state["dashboard_rows"] == []


def test_a_nonexistent_resumes_folder_shows_a_clean_error_not_a_crash(tmp_path: Path) -> None:
    jrp_path = tmp_path / "backend-engineer.yaml"
    jrp_path.write_text(_JRP_CONFIG, encoding="utf-8")

    at = AppTest.from_file(_APP_PATH)
    at.run(timeout=_RUN_TIMEOUT)

    at.text_input(key="resumes_path").set_value(str(tmp_path / "does-not-exist"))
    at.text_input(key="jrp_path").set_value(str(jrp_path))
    at.button[0].click()
    at.run(timeout=_RUN_TIMEOUT)

    assert not at.exception
    assert any("Resumes folder not found" in e.value for e in at.error)


def test_the_overall_score_metric_never_colors_low_match_as_a_positive_change(
    tmp_path: Path,
) -> None:
    # st.metric colors an unrecognized (non-numeric, no leading "-") delta string green/"up" by
    # default -- previously rendering Low Match, the worst tier, with the same positive-looking
    # indicator as High Match. delta_color="off" must keep every tier's metric color GRAY.
    resumes_dir = tmp_path / "resumes"
    resumes_dir.mkdir()
    (resumes_dir / "candidate.pdf").write_bytes(
        b"Skills:\nCOBOL programming and mainframe systems\n\n"
        b"Working Experience:\nOne year as a junior mainframe operator\n\n"
        b"Education:\nHigh school diploma\n"
    )
    jrp_path = tmp_path / "backend-engineer.yaml"
    jrp_path.write_text(_JRP_CONFIG, encoding="utf-8")

    at = AppTest.from_file(_APP_PATH)
    at.run(timeout=_RUN_TIMEOUT)

    at.text_input(key="resumes_path").set_value(str(resumes_dir))
    at.text_input(key="jrp_path").set_value(str(jrp_path))
    at.button[0].click()
    at.run(timeout=_RUN_TIMEOUT)

    assert not at.exception
    assert "low_match" in at.session_state["dashboard_rows"][0].score.tier.value
    assert at.metric[0].proto.color == at.metric[0].proto.GRAY
