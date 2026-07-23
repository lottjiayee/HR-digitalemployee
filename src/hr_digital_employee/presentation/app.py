"""Module 5's read-only candidate comparison table + drill-down dashboard (SOP 2.4.2-2.4.3,
design.md §3.8). Presents already-computed scores/summaries for ranking and review only.

This is a first, narrow slice of Module 5 -- deliberately scoped to just the comparison table and
drill-down (module-5 doc §7's first two checklist items). It does NOT include filtering, skill-gap
visualizations, the JRP configuration UI (see `jrp_editor/` instead), or the Pass/Reject action
(design.md §3.8's "only component with a write path to candidate status" -- not built yet, see
ASSUMPTIONS.md). Deliberately has no "hide below X score" control of any kind: design.md §3.8
requires the UI must not imply or enable automatic filtering-out of low scorers.

Run via the `hr-digital-employee-dashboard` console script (see launcher.py), or directly with
`streamlit run src/hr_digital_employee/presentation/app.py`.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from hr_digital_employee.governance_audit.audit_log import InMemoryAuditLog
from hr_digital_employee.pipeline import candidate_label
from hr_digital_employee.presentation.dashboard_data import (
    DashboardRow,
    build_dashboard_rows,
    summary_text,
)
from hr_digital_employee.scoring_engine.jrp_config import JRPConfigError, load_jrp_from_yaml

st.set_page_config(page_title="HR Digital Employee -- Candidate Dashboard", layout="wide")
st.title("Candidate Comparison Dashboard")
st.caption(
    "Scores rank and prioritize only -- nothing here removes, hides, or filters out a candidate "
    "(SOP 1.4/FR-13). Passing/rejecting a candidate is a separate, explicit HR action, not built "
    "in this view yet."
)

if "dashboard_rows" not in st.session_state:
    st.session_state.dashboard_rows = []
if "dashboard_manual_review_queue" not in st.session_state:
    st.session_state.dashboard_manual_review_queue = None
if "dashboard_run_error" not in st.session_state:
    st.session_state.dashboard_run_error = None

resumes_path = st.text_input("Resumes folder", key="resumes_path")
jrp_path = st.text_input("JRP YAML file", key="jrp_path")

if st.button("Run"):
    st.session_state.dashboard_run_error = None
    try:
        jrp = load_jrp_from_yaml(Path(jrp_path))
        new_rows, new_manual_review_queue = build_dashboard_rows(
            Path(resumes_path), jrp, InMemoryAuditLog()
        )
        st.session_state.dashboard_rows = new_rows
        st.session_state.dashboard_manual_review_queue = new_manual_review_queue
    except JRPConfigError as error:
        st.session_state.dashboard_run_error = f"Error loading JRP config: {error}"
    except OSError as error:
        st.session_state.dashboard_run_error = f"Error reading resumes folder: {error}"

if st.session_state.dashboard_run_error:
    st.error(st.session_state.dashboard_run_error)

rows: list[DashboardRow] = st.session_state.dashboard_rows
if rows:
    st.subheader(f"Candidates ({len(rows)})")
    table_rows = [
        {
            "Candidate": candidate_label(row.candidate),
            "Score": row.score.total_score,
            "Tier": row.score.tier.value + ("*" if not row.score.passed_must_have else ""),
            "Must-have": (
                "pass"
                if row.score.passed_must_have
                else "; ".join(row.score.failed_must_have_labels)
            ),
            "Summary": summary_text(row)[:120],
        }
        for row in rows
    ]
    st.dataframe(table_rows, hide_index=True)
    if any(not row.score.passed_must_have for row in rows):
        st.caption(
            "* must-have requirement(s) not met -- shown alongside the score, never auto-rejected "
            "(SOP 2.2.2/2.2.4); see the Must-have column."
        )

    labels = [candidate_label(row.candidate) for row in rows]
    selected_label = st.selectbox("Drill into a candidate", labels, key="selected_candidate")
    selected_row = next(row for row in rows if candidate_label(row.candidate) == selected_label)

    st.subheader(f"Candidate detail: {selected_label}")
    st.metric(
        "Overall score",
        f"{selected_row.score.total_score:.2f}",
        selected_row.score.tier.value.replace("_", " "),
    )
    if not selected_row.score.passed_must_have:
        st.warning(
            "Must-have requirement(s) not met: "
            + "; ".join(selected_row.score.failed_must_have_labels)
            + " -- shown alongside the score, not auto-rejected (SOP 2.2.2/2.2.4)."
        )

    st.markdown("**Matching analysis**")
    for dimension_result in selected_row.score.breakdown:
        st.write(
            f"- {dimension_result.dimension.value.replace('_', ' ').title()}: "
            f"{dimension_result.curve_score * 100:.0f}% match, "
            f"{dimension_result.contribution:.1f} of {dimension_result.weight:.0f} points"
        )

    st.markdown("**Summary**")
    st.write(summary_text(selected_row))

    st.markdown("**Suggested interview questions**")
    for question in selected_row.content.interview_questions:
        st.write(f"- ({question.angle.value}) {question.text}")

    if selected_row.content.red_flags:
        st.markdown("**Red flags**")
        for flag in selected_row.content.red_flags:
            st.write(f"- {flag.description}")

queue = st.session_state.dashboard_manual_review_queue
if queue is not None and len(queue) > 0:
    st.subheader("Manual review queue")
    for item in queue.items():
        st.write(f"- {item.submission.display_identifier}: {item.reason.value} ({item.detail})")
