"""Architectural invariants that must hold regardless of which module last changed
(md/prompt.md §2, "Non-Negotiable Constraints" -- not a style preference, a correctness property).
"""

from __future__ import annotations

import ast
from pathlib import Path

_SRC_ROOT = Path(__file__).resolve().parent.parent / "src" / "hr_digital_employee"


def _imported_top_level_packages(py_file: Path) -> set[str]:
    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    packages: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            packages.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            packages.add(node.module.split(".")[0])
    return packages


def test_scoring_engine_never_imports_from_ai_content() -> None:
    # design.md §1/FR-9, md/prompt.md §2 invariant 1: the scoring package must have zero import
    # dependency on the AI-content package. The reverse (ai_content reading scoring_engine's Score
    # for question targeting, per module-3 doc's own Dependencies section) is expected and fine --
    # this check is one-directional.
    scoring_engine_dir = _SRC_ROOT / "scoring_engine"
    offending_files = [
        str(py_file.relative_to(_SRC_ROOT))
        for py_file in scoring_engine_dir.rglob("*.py")
        if "hr_digital_employee.ai_content" in py_file.read_text(encoding="utf-8")
        or "ai_content" in _imported_top_level_packages(py_file)
    ]
    assert offending_files == [], (
        f"scoring_engine must never import ai_content, but found imports in: {offending_files}"
    )


def test_scoring_engine_never_imports_from_fairness_compliance() -> None:
    # FR-21/test.md T4.3: demographic data (fairness_compliance.models.DemographicRecord) must
    # never reach the Scoring Engine. fairness_compliance importing scoring_engine (e.g.
    # explainability.py reading Score) is the expected, allowed direction -- this check is the
    # other one-directional wall, same shape as the ai_content check above.
    scoring_engine_dir = _SRC_ROOT / "scoring_engine"
    offending_files = [
        str(py_file.relative_to(_SRC_ROOT))
        for py_file in scoring_engine_dir.rglob("*.py")
        if "hr_digital_employee.fairness_compliance" in py_file.read_text(encoding="utf-8")
        or "fairness_compliance" in _imported_top_level_packages(py_file)
    ]
    assert offending_files == [], (
        "scoring_engine must never import fairness_compliance, but found imports in: "
        f"{offending_files}"
    )


def test_ai_content_never_constructs_a_score() -> None:
    # md/prompt.md §2 invariant 1's second half: no function in ai_content may write a
    # score/tier field. ai_content is allowed to *read* an existing Score (for question
    # targeting) but must never construct one -- that stays Module 2's job alone.
    ai_content_dir = _SRC_ROOT / "ai_content"
    offending_files = [
        str(py_file.relative_to(_SRC_ROOT))
        for py_file in ai_content_dir.rglob("*.py")
        if "Score(" in py_file.read_text(encoding="utf-8")
    ]
    assert offending_files == [], (
        "ai_content must never construct a Score, but found a Score(...) call in: "
        f"{offending_files}"
    )
