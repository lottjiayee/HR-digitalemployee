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


_SCORE_SPECIFIC_FIELDS = frozenset(
    {"total_score", "passed_must_have", "failed_must_have_labels", "scoring_engine_version"}
)
"""Field names distinctive enough to `Score` (models.py) that a `dataclasses.replace(x,
total_score=...)` call setting one of them is never plausibly about some other dataclass -- used to
tell an actual Score mutation apart from a legitimate `dataclasses.replace` on an unrelated type
(e.g. `AccessRequest`/`ConsentRecord`, which this module also has real, allowed uses for)."""


def _constructs_or_mutates_a_score(py_file: Path) -> bool:
    """AST-based, not a `"Score("` substring search -- a substring search is defeated by
    `dataclasses.replace(score, total_score=100.0, ...)`, which builds a genuinely different
    `Score` (confirmed: executed, LOW_MATCH/12.0 -> HIGH_MATCH/100.0) while containing zero
    occurrences of the literal text `"Score("`. Checks for (a) any call to a name/attribute
    literally called `Score`, and (b) any call to `dataclasses.replace`/bare `replace` (only when
    imported from `dataclasses`, so an ordinary `some_string.replace(...)` is never a false
    positive) whose keyword arguments touch a Score-specific field."""
    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    bare_replace_imported = any(
        isinstance(node, ast.ImportFrom)
        and node.module == "dataclasses"
        and any(alias.name == "replace" for alias in node.names)
        for node in ast.walk(tree)
    )
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == "Score":
            return True
        if isinstance(func, ast.Attribute) and func.attr == "Score":
            return True
        is_dataclasses_replace = (
            isinstance(func, ast.Attribute)
            and func.attr == "replace"
            and isinstance(func.value, ast.Name)
            and func.value.id == "dataclasses"
        ) or (isinstance(func, ast.Name) and func.id == "replace" and bare_replace_imported)
        if is_dataclasses_replace and any(
            keyword.arg in _SCORE_SPECIFIC_FIELDS for keyword in node.keywords
        ):
            return True
    return False


def test_the_checker_catches_a_dataclasses_replace_score_bypass(tmp_path: Path) -> None:
    # Proves the tripwire actually works: `dataclasses.replace(score, total_score=100.0, ...)`
    # builds a genuinely different Score (confirmed by executing it: LOW_MATCH/12.0 ->
    # HIGH_MATCH/100.0) while containing zero occurrences of the literal text "Score(" -- the
    # substring search this replaced would have missed it entirely.
    offender = tmp_path / "offender.py"
    offender.write_text(
        "import dataclasses\n"
        "def cheat(score):\n"
        "    return dataclasses.replace(score, total_score=100.0)\n",
        encoding="utf-8",
    )
    assert _constructs_or_mutates_a_score(offender) is True


def test_the_checker_ignores_dataclasses_replace_on_an_unrelated_type(tmp_path: Path) -> None:
    # Regression: an early version of this checker banned *any* `dataclasses.replace` call,
    # which broke on this package's own legitimate uses (e.g. `access_requests.py` updating an
    # AccessRequest's status, `consent.py` marking a ConsentRecord withdrawn).
    innocent = tmp_path / "innocent.py"
    innocent.write_text(
        "import dataclasses\n"
        "def update_status(request, new_status):\n"
        "    return dataclasses.replace(request, status=new_status)\n",
        encoding="utf-8",
    )
    assert _constructs_or_mutates_a_score(innocent) is False


def test_the_checker_ignores_an_ordinary_string_replace_call(tmp_path: Path) -> None:
    plain = tmp_path / "plain.py"
    plain.write_text('def clean(label):\n    return label.replace("\\n", " ")\n', encoding="utf-8")
    assert _constructs_or_mutates_a_score(plain) is False


def test_ai_content_never_constructs_or_mutates_a_score() -> None:
    # md/prompt.md §2 invariant 1's second half: no function in ai_content may write a
    # score/tier field. ai_content is allowed to *read* an existing Score (for question
    # targeting) but must never construct or mutate one -- that stays Module 2's job alone.
    ai_content_dir = _SRC_ROOT / "ai_content"
    offending_files = [
        str(py_file.relative_to(_SRC_ROOT))
        for py_file in ai_content_dir.rglob("*.py")
        if _constructs_or_mutates_a_score(py_file)
    ]
    assert offending_files == [], (
        f"ai_content must never construct or mutate a Score, but found one in: {offending_files}"
    )


def test_fairness_compliance_never_constructs_or_mutates_a_score() -> None:
    # Same wall as above, on the same fairness_compliance/explainability.py which is equally
    # documented (module-4 doc §4, FR-25) as read-only against an existing Score.
    fairness_compliance_dir = _SRC_ROOT / "fairness_compliance"
    offending_files = [
        str(py_file.relative_to(_SRC_ROOT))
        for py_file in fairness_compliance_dir.rglob("*.py")
        if _constructs_or_mutates_a_score(py_file)
    ]
    assert offending_files == [], (
        "fairness_compliance must never construct or mutate a Score, but found one in: "
        f"{offending_files}"
    )
