"""Command-line entry point: score every resume in a folder against a JRP defined in a YAML file.

A temporary, minimal bridge so the pipeline is usable by *someone* right now, without Module 5's
real dashboard/JRP-configuration UI (not built yet -- see ASSUMPTIONS.md). Run as:

    hr-digital-employee --resumes ./resumes --jrp ./backend-engineer.yaml
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from pathlib import Path

from hr_digital_employee.governance_audit.audit_log import InMemoryAuditLog
from hr_digital_employee.governance_audit.interfaces import AuditLog
from hr_digital_employee.governance_audit.sqlite_audit_log import SqliteAuditLog
from hr_digital_employee.intake_extraction.manual_review_queue import ManualReviewQueue
from hr_digital_employee.intake_extraction.text_extraction_log import TextExtractionLog
from hr_digital_employee.pipeline import candidate_label, run_pipeline
from hr_digital_employee.scoring_engine.jrp_config import JRPConfigError, load_jrp_from_yaml
from hr_digital_employee.scoring_engine.models import JRP, Score


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hr-digital-employee",
        description=(
            "Score every resume in a folder against a JRP defined in a YAML file. A temporary "
            "command-line bridge -- Module 5's real dashboard/JRP-configuration UI is not built "
            "yet (see ASSUMPTIONS.md)."
        ),
    )
    parser.add_argument(
        "--resumes", type=Path, required=True, help="Folder of resume files (PDF/JPEG/PNG/...)"
    )
    parser.add_argument("--jrp", type=Path, required=True, help="Path to a JRP YAML config file")
    parser.add_argument(
        "--audit-db",
        type=Path,
        default=None,
        help="SQLite file to persist the audit log to (default: in-memory, not persisted)",
    )
    parser.add_argument(
        "--text-log",
        type=Path,
        default=None,
        help="Optional file to append every extracted resume's raw text to",
    )
    return parser


def run(
    resumes_folder: Path,
    jrp: JRP,
    audit_log: AuditLog,
    text_log: TextExtractionLog | None = None,
) -> tuple[list[tuple[str, Score]], ManualReviewQueue]:
    """Run the intake -> extraction -> scoring pipeline once against every file currently in
    `resumes_folder`. Returns (candidate label, Score) pairs sorted by total_score descending,
    plus the manual-review queue for anything that never made it to a Score."""
    pipeline_results, manual_review_queue = run_pipeline(resumes_folder, jrp, audit_log, text_log)
    results = [(candidate_label(result.candidate), result.score) for result in pipeline_results]
    return results, manual_review_queue


_CONTROL_CHAR_PATTERN = re.compile("[\x00-\x1f\x7f]")


def _print_report(
    jrp: JRP, results: list[tuple[str, Score]], manual_review_queue: ManualReviewQueue
) -> None:
    print(f"JRP: {jrp.role_name} ({jrp.jrp_id}, v{jrp.version})")
    print(f"Scored: {len(results)}   Routed to manual review: {len(manual_review_queue)}")
    print()

    if results:
        print(f"{'Candidate':<30} {'Score':>7}  {'Tier':<13} Must-have")
        print("-" * 70)
        for raw_label, score in results:
            # Candidate-supplied (untrusted): a newline would otherwise forge what looks like a
            # second, standalone row in the printed table, and a raw ANSI escape sequence (ESC,
            # \x1b) could spoof console output (screen-clear, fake colored "success" text) --
            # every control character is replaced, not just \n/\r. `candidate_label()` already
            # does this too; re-applied here since `results` is a plain list of (str, Score) this
            # function has no guarantee was built via `candidate_label()`.
            label = _CONTROL_CHAR_PATTERN.sub(" ", raw_label)
            if score.passed_must_have:
                must_have = "pass"
                tier_display = score.tier.value
            else:
                must_have = f"FAIL: {'; '.join(score.failed_must_have_labels)}"
                tier_display = f"{score.tier.value}*"
            # Two decimals, not one: `engine.py` already rounds `total_score` to 2 places, and a
            # value like 79.95 displayed at 1 decimal ("80.0") sits right next to its correctly-
            # classified "mid_match" tier looking like a tier-classification bug on a skim.
            print(f"{label:<30} {score.total_score:>7.2f}  {tier_display:<13} {must_have}")
        if any(not score.passed_must_have for _, score in results):
            print()
            print("* must-have requirement(s) not met -- see Must-have column; HR reviews before")
            print("  advancing (score/tier shown per SOP 2.2.2/2.2.4, never auto-rejected).")

    if len(manual_review_queue) > 0:
        print()
        print("Manual review queue:")
        for item in manual_review_queue.items():
            print(f"  - {item.submission.display_identifier}: {item.reason.value} ({item.detail})")


def main(argv: list[str] | None = None) -> int:
    # A candidate name/label containing CJK characters or an emoji otherwise crashes the whole
    # report with `UnicodeEncodeError` under a legacy (e.g. Windows cp1252) console encoding --
    # replacing what can't be displayed keeps the report printing instead of aborting the batch.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")

    args = build_argument_parser().parse_args(argv)

    try:
        jrp = load_jrp_from_yaml(args.jrp)
    except JRPConfigError as error:
        print(f"Error loading JRP config: {error}", file=sys.stderr)
        return 1

    if not args.resumes.is_dir():
        # Without this, a typo'd/nonexistent --resumes path (or accidentally passing the JRP
        # path to --resumes) silently produced a clean-looking but completely empty report
        # ("Scored: 0   Routed to manual review: 0") instead of any error -- LocalFolderChannel
        # Adapter treats a missing folder the same as an empty one (channel_adapters.py), and a
        # path pointing at a file rather than a directory hits the same silent-empty outcome via
        # iterdir() raising NotADirectoryError, caught there too. Indistinguishable from "this
        # folder genuinely has no resumes in it right now" -- matching the dashboard's own
        # folder-path validation (app.py) rather than leaving the CLI silently weaker.
        print(
            f"Error: --resumes path not found or not a directory: {args.resumes}",
            file=sys.stderr,
        )
        return 1

    try:
        audit_log: AuditLog = SqliteAuditLog(args.audit_db) if args.audit_db else InMemoryAuditLog()
        text_log = TextExtractionLog(args.text_log) if args.text_log else None

        results, manual_review_queue = run(args.resumes, jrp, audit_log, text_log)
    except sqlite3.Error as error:
        # Two distinct failure shapes, both from --audit-db pointing at something incompatible:
        # a path that exists but isn't a SQLite file at all (fails immediately, constructing
        # SqliteAuditLog), or a SQLite file whose audit_events table doesn't have this schema
        # (CREATE TABLE IF NOT EXISTS no-ops silently, so this only surfaces on the first actual
        # record() call, mid-pipeline). Either way, a raw traceback isn't an actionable message.
        print(f"Error using --audit-db {args.audit_db}: {error}", file=sys.stderr)
        return 1

    _print_report(jrp, results, manual_review_queue)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
