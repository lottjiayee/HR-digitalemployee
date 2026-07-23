"""Module 5's read-only candidate comparison table + drill-down dashboard (SOP 2.4.2-2.4.3,
design.md §3.8). Presents already-computed scores/summaries for ranking and review only.

This is a first, narrow slice of Module 5 -- deliberately scoped to just the comparison table and
drill-down (module-5 doc §7's first two checklist items). It does NOT include filtering, skill-gap
visualizations, or the Pass/Reject action (design.md §3.8's "only component with a write path to
candidate status" -- not built yet, see ASSUMPTIONS.md). Deliberately has no "hide below X score"
control of any kind: design.md §3.8 requires the UI must not imply or enable automatic
filtering-out of low scorers.

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
    build_dashboard_rows_from_uploads,
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

# ── session state ──────────────────────────────────────────────────────────────────────────────
if "dashboard_rows" not in st.session_state:
    st.session_state.dashboard_rows = []
if "dashboard_manual_review_queue" not in st.session_state:
    st.session_state.dashboard_manual_review_queue = None
if "dashboard_run_error" not in st.session_state:
    st.session_state.dashboard_run_error = None

# ── input section ──────────────────────────────────────────────────────────────────────────────
st.subheader("Upload files")

col_resumes, col_jrp = st.columns([2, 1])

with col_resumes:
    uploaded_resumes = st.file_uploader(
        "Resume files (PDF, JPEG, PNG, GIF, BMP, WEBP)",
        type=["pdf", "jpg", "jpeg", "png", "gif", "bmp", "webp"],
        accept_multiple_files=True,
        key="uploaded_resumes",
        help="Select one or more resume files. Files are processed in-memory -- nothing is saved.",
    )

with col_jrp:
    uploaded_jrp = st.file_uploader(
        "JRP YAML config",
        type=["yaml", "yml"],
        accept_multiple_files=False,
        key="uploaded_jrp",
        help="Upload the job requirements profile (JRP) YAML file for this role.",
    )

# ── optional folder-path fallback (power users) ───────────────────────────────────────────────
with st.expander("Or point at a local folder instead (advanced)", expanded=False):
    st.caption(
        "Use this if your resumes are already on disk. Leave both upload widgets above empty "
        "when using this mode."
    )
    folder_resumes_path = st.text_input("Resumes folder path", key="resumes_path")
    folder_jrp_path = st.text_input("JRP YAML file path", key="jrp_path")

# ── run button ─────────────────────────────────────────────────────────────────────────────────
if st.button("Run", type="primary"):
    st.session_state.dashboard_run_error = None

    # Decide which input mode to use: uploaded files take priority over folder paths.
    use_uploads = bool(uploaded_resumes or uploaded_jrp)

    if use_uploads:
        # ── upload mode ────────────────────────────────────────────────────────────────────────
        if not uploaded_resumes:
            st.session_state.dashboard_run_error = (
                "Please upload at least one resume file."
            )
        elif not uploaded_jrp:
            st.session_state.dashboard_run_error = (
                "Please upload a JRP YAML config file."
            )
        else:
            try:
                jrp_bytes = uploaded_jrp.read()
                # load_jrp_from_yaml expects a Path; write JRP bytes to a temp in-memory approach
                # by saving to a NamedTemporaryFile -- YAML is small so this is fine.
                import tempfile

                with tempfile.NamedTemporaryFile(
                    suffix=".yaml", delete=False
                ) as tmp_jrp:
                    tmp_jrp.write(jrp_bytes)
                    tmp_jrp_path = Path(tmp_jrp.name)

                jrp = load_jrp_from_yaml(tmp_jrp_path)
                tmp_jrp_path.unlink(missing_ok=True)

                uploads = [(f.name, f.read()) for f in uploaded_resumes]
                new_rows, new_manual_review_queue = build_dashboard_rows_from_uploads(
                    uploads, jrp, InMemoryAuditLog()
                )
                st.session_state.dashboard_rows = new_rows
                st.session_state.dashboard_manual_review_queue = new_manual_review_queue
            except JRPConfigError as error:
                st.session_state.dashboard_run_error = f"Error loading JRP config: {error}"
            except OSError as error:
                st.session_state.dashboard_run_error = f"Error reading uploaded files: {error}"
    else:
        # ── folder-path mode ───────────────────────────────────────────────────────────────────
        if not folder_resumes_path.strip():
            st.session_state.dashboard_run_error = (
                "Upload resume files above, or enter a resumes folder path."
            )
        else:
            try:
                resumes_folder = Path(folder_resumes_path)
                if not resumes_folder.is_dir():
                    st.session_state.dashboard_run_error = (
                        f"Resumes folder not found: {folder_resumes_path}"
                    )
                else:
                    jrp = load_jrp_from_yaml(Path(folder_jrp_path))
                    new_rows, new_manual_review_queue = build_dashboard_rows(
                        resumes_folder, jrp, InMemoryAuditLog()
                    )
                    st.session_state.dashboard_rows = new_rows
                    st.session_state.dashboard_manual_review_queue = new_manual_review_queue
            except JRPConfigError as error:
                st.session_state.dashboard_run_error = f"Error loading JRP config: {error}"
            except OSError as error:
                st.session_state.dashboard_run_error = f"Error reading resumes folder: {error}"

# ── error banner ───────────────────────────────────────────────────────────────────────────────
if st.session_state.dashboard_run_error:
    st.error(st.session_state.dashboard_run_error)

# ── results ────────────────────────────────────────────────────────────────────────────────────
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

    # Selection is keyed by row *index*, not by the label string: two different candidates can
    # share the identical label (e.g. two submissions that both merged into a candidate named
    # "John Smith" -- confirmed reachable via IdentityDedupService's MERGED_INTO_EXISTING outcome).
    # `next(row for row in rows if candidate_label(row.candidate) == selected_label)` always
    # resolved to the *first* row with that label regardless of which dropdown entry was actually
    # picked, silently showing the wrong candidate's score/summary/interview questions.
    labels = [candidate_label(row.candidate) for row in rows]
    selected_index = st.selectbox(
        "Drill into a candidate",
        options=range(len(rows)),
        format_func=lambda index: labels[index],
        key="selected_candidate",
    )
    selected_row = rows[selected_index]
    selected_label = labels[selected_index]

    st.subheader(f"Candidate detail: {selected_label}")
    st.metric(
        "Overall score",
        f"{selected_row.score.total_score:.2f}",
        selected_row.score.tier.value.replace("_", " "),
        # A tier label isn't a change-over-time value, and st.metric otherwise defaults an
        # unrecognized (non-numeric, no leading "-") delta string to a green "up" arrow --
        # which rendered Low Match, the worst tier, with the same positive-looking indicator
        # as High Match. delta_color="off" shows the tier as plain text, no arrow or color.
        delta_color="off",
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
