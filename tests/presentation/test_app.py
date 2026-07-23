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
