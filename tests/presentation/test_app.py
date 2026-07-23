"""Tests for Module 5's comparison-table/drill-down dashboard (app.py), exercised via Streamlit's
`AppTest` harness.

Skipped entirely when the optional `ui` extra (streamlit) isn't installed -- dashboard_data.py's
own tests cover the Streamlit-free logic and always run.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from unittest import mock

import pytest

pytest.importorskip("streamlit")

from streamlit.testing.v1 import AppTest  # noqa: E402

from hr_digital_employee.governance_audit.audit_log import InMemoryAuditLog  # noqa: E402
from hr_digital_employee.presentation.dashboard_data import build_dashboard_rows  # noqa: E402
from hr_digital_employee.scoring_engine.jrp_config import load_jrp_from_yaml  # noqa: E402

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


class _FakeUploadedFile:
    """Stand-in for Streamlit's real `UploadedFile` -- only exposes the `.name`/`.read()` surface
    app.py actually uses. Streamlit 1.60.0's `testing.v1` harness (AppTest) has no public API to
    simulate `st.file_uploader` (unlike `st.text_input`/`st.button`, there's no widget wrapper for
    it in `element_tree.py`) -- so the upload widgets are monkeypatched at the `streamlit` module
    level instead, letting the rest of app.py's real upload-mode branch (temp JRP file round-trip,
    build_dashboard_rows_from_uploads call, session-state wiring, error handling) execute for real.
    """

    def __init__(self, name: str, data: bytes) -> None:
        self.name = name
        self._data = data

    def read(self) -> bytes:
        return self._data


def _patched_file_uploader(resumes: list[_FakeUploadedFile] | None, jrp: _FakeUploadedFile | None):
    def fake_file_uploader(label: str, **kwargs: object) -> object:
        key = kwargs.get("key")
        if key == "uploaded_resumes":
            return resumes or []
        if key == "uploaded_jrp":
            return jrp
        raise AssertionError(f"unexpected st.file_uploader key: {key!r}")

    return mock.patch("streamlit.file_uploader", side_effect=fake_file_uploader)


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
    assert any(
        "enter a resumes folder path" in e.value for e in at.error
    )
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


def test_selecting_the_second_of_two_identically_labeled_candidates_shows_its_own_score(
    tmp_path: Path,
) -> None:
    # Regression (round 6): the drill-down used to select by label string --
    # `next(row for row in rows if candidate_label(row.candidate) == selected_label)` -- which
    # always resolved to the *first* row sharing that label. Two submissions that both merge into
    # the same candidate identity (a real, if not yet reachable through today's shipped channel
    # adapters, outcome of IdentityDedupService) are still independently scored, so a candidate
    # named e.g. "Jane Doe" can legitimately appear as two distinct rows with two distinct scores.
    # Selection must be by row index, not by the (potentially colliding) label text.
    jrp_path = tmp_path / "backend-engineer.yaml"
    jrp_path.write_text(_JRP_CONFIG, encoding="utf-8")
    jrp = load_jrp_from_yaml(jrp_path)

    weak_dir = tmp_path / "weak"
    weak_dir.mkdir()
    (weak_dir / "candidate.pdf").write_bytes(
        b"Skills:\nCOBOL programming and mainframe systems\n\n"
        b"Working Experience:\nOne year as a junior mainframe operator\n\n"
        b"Education:\nHigh school diploma\n"
    )
    strong_dir = tmp_path / "strong"
    strong_dir.mkdir()
    (strong_dir / "candidate.pdf").write_bytes(_STRONG_RESUME)

    weak_rows, _ = build_dashboard_rows(weak_dir, jrp, InMemoryAuditLog())
    strong_rows, _ = build_dashboard_rows(strong_dir, jrp, InMemoryAuditLog())
    weak_row, strong_row = weak_rows[0], strong_rows[0]
    # Force both rows onto the identical candidate identity/label, exactly as two submissions
    # that both merged via IdentityDedupService would -- while keeping each row's own distinct,
    # independently-computed score, matching the real bug scenario.
    strong_row_same_candidate = dataclasses.replace(strong_row, candidate=weak_row.candidate)
    assert weak_row.score.total_score != strong_row_same_candidate.score.total_score

    at = AppTest.from_file(_APP_PATH)
    at.session_state["dashboard_rows"] = [weak_row, strong_row_same_candidate]
    at.session_state["dashboard_manual_review_queue"] = None
    at.run(timeout=_RUN_TIMEOUT)

    # Select the *second* dropdown entry (index 1) -- the strong-scoring row.
    at.selectbox(key="selected_candidate").set_value(1)
    at.run(timeout=_RUN_TIMEOUT)

    assert not at.exception
    assert f"{strong_row_same_candidate.score.total_score:.2f}" in at.metric[0].value
    assert f"{weak_row.score.total_score:.2f}" not in at.metric[0].value


def test_uploading_resume_and_jrp_files_scores_a_candidate() -> None:
    resumes = [_FakeUploadedFile("candidate.pdf", _STRONG_RESUME)]
    jrp_file = _FakeUploadedFile("backend-engineer.yaml", _JRP_CONFIG.encode("utf-8"))

    with _patched_file_uploader(resumes, jrp_file):
        at = AppTest.from_file(_APP_PATH)
        at.run(timeout=_RUN_TIMEOUT)
        at.button[0].click()
        at.run(timeout=_RUN_TIMEOUT)

    assert not at.exception
    assert not at.session_state["dashboard_run_error"]
    assert len(at.session_state["dashboard_rows"]) == 1
    assert at.session_state["dashboard_rows"][0].score.total_score == 100.0
    assert "100.0" in at.metric[0].value


def test_uploading_only_a_jrp_file_shows_a_clean_error_not_a_crash() -> None:
    # Uploads take priority over the folder-path fallback the moment either upload widget has a
    # file in it (`use_uploads = bool(uploaded_resumes or uploaded_jrp)`) -- so a JRP-only upload
    # must not silently fall through to scanning the (empty) folder-path fields.
    jrp_file = _FakeUploadedFile("backend-engineer.yaml", _JRP_CONFIG.encode("utf-8"))

    with _patched_file_uploader(None, jrp_file):
        at = AppTest.from_file(_APP_PATH)
        at.run(timeout=_RUN_TIMEOUT)
        at.button[0].click()
        at.run(timeout=_RUN_TIMEOUT)

    assert not at.exception
    assert any("upload at least one resume file" in e.value for e in at.error)
    assert at.session_state["dashboard_rows"] == []


def test_uploading_only_resumes_without_a_jrp_shows_a_clean_error_not_a_crash() -> None:
    resumes = [_FakeUploadedFile("candidate.pdf", _STRONG_RESUME)]

    with _patched_file_uploader(resumes, None):
        at = AppTest.from_file(_APP_PATH)
        at.run(timeout=_RUN_TIMEOUT)
        at.button[0].click()
        at.run(timeout=_RUN_TIMEOUT)

    assert not at.exception
    assert any("upload a JRP YAML config file" in e.value for e in at.error)
    assert at.session_state["dashboard_rows"] == []


def test_an_invalid_uploaded_jrp_shows_a_clean_error_not_a_crash() -> None:
    resumes = [_FakeUploadedFile("candidate.pdf", _STRONG_RESUME)]
    jrp_file = _FakeUploadedFile("broken.yaml", b"not: [valid, jrp, config")

    with _patched_file_uploader(resumes, jrp_file):
        at = AppTest.from_file(_APP_PATH)
        at.run(timeout=_RUN_TIMEOUT)
        at.button[0].click()
        at.run(timeout=_RUN_TIMEOUT)

    assert not at.exception
    assert any("Error loading JRP config" in e.value for e in at.error)
    assert at.session_state["dashboard_rows"] == []


def test_uploaded_resumes_take_priority_over_a_filled_in_folder_path(tmp_path: Path) -> None:
    # A power user who previously used the folder-path fallback and then also uploads a file
    # (without clearing the folder-path fields) must get the upload result, not a silent scan of
    # the leftover folder path -- `use_uploads` is keyed only on whether an upload widget has a
    # file, never on whether the folder-path fields happen to be non-empty too.
    weak_dir = tmp_path / "weak"
    weak_dir.mkdir()
    (weak_dir / "candidate.pdf").write_bytes(
        b"Skills:\nCOBOL programming and mainframe systems\n\n"
        b"Working Experience:\nOne year as a junior mainframe operator\n\n"
        b"Education:\nHigh school diploma\n"
    )
    jrp_path = tmp_path / "backend-engineer.yaml"
    jrp_path.write_text(_JRP_CONFIG, encoding="utf-8")

    resumes = [_FakeUploadedFile("candidate.pdf", _STRONG_RESUME)]
    jrp_file = _FakeUploadedFile("backend-engineer.yaml", _JRP_CONFIG.encode("utf-8"))

    with _patched_file_uploader(resumes, jrp_file):
        at = AppTest.from_file(_APP_PATH)
        at.run(timeout=_RUN_TIMEOUT)
        at.text_input(key="resumes_path").set_value(str(weak_dir))
        at.text_input(key="jrp_path").set_value(str(jrp_path))
        at.button[0].click()
        at.run(timeout=_RUN_TIMEOUT)

    assert not at.exception
    assert len(at.session_state["dashboard_rows"]) == 1
    assert at.session_state["dashboard_rows"][0].score.total_score == 100.0
