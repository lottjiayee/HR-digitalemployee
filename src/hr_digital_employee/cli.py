"""Command-line entry point: score every resume in a folder against a JRP defined in a YAML file.

A temporary, minimal bridge so the pipeline is usable by *someone* right now, without Module 5's
real dashboard/JRP-configuration UI (not built yet -- see ASSUMPTIONS.md). Run as:

    hr-digital-employee --resumes ./resumes --jrp ./backend-engineer.yaml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from hr_digital_employee.governance_audit.audit_log import InMemoryAuditLog
from hr_digital_employee.governance_audit.interfaces import AuditLog
from hr_digital_employee.governance_audit.sqlite_audit_log import SqliteAuditLog
from hr_digital_employee.intake_extraction.channel_adapters import LocalFolderChannelAdapter
from hr_digital_employee.intake_extraction.dedup import IdentityDedupService
from hr_digital_employee.intake_extraction.extraction import ExtractionService
from hr_digital_employee.intake_extraction.gateway import IngestionGateway
from hr_digital_employee.intake_extraction.manual_review_queue import ManualReviewQueue
from hr_digital_employee.intake_extraction.text_extraction_log import TextExtractionLog
from hr_digital_employee.scoring_engine.engine import ScoringEngine
from hr_digital_employee.scoring_engine.jrp_config import JRPConfigError, load_jrp_from_yaml
from hr_digital_employee.scoring_engine.models import JRP, Score
from hr_digital_employee.scoring_engine.profile_adapter import build_candidate_profile


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
    manual_review_queue = ManualReviewQueue()
    gateway = IngestionGateway(
        channel_adapters=[LocalFolderChannelAdapter(resumes_folder)],
        extraction_service=ExtractionService(),
        dedup_service=IdentityDedupService(),
        manual_review_queue=manual_review_queue,
        audit_log=audit_log,
        text_log=text_log,
    )

    results: list[tuple[str, Score]] = []
    for candidate, extracted in gateway.run_once():
        profile = build_candidate_profile(extracted)
        score = ScoringEngine().score(profile, jrp, extracted.parser_version)
        label = candidate.name or candidate.email or candidate.phone or candidate.candidate_id
        results.append((label, score))

    results.sort(key=lambda pair: pair[1].total_score, reverse=True)
    return results, manual_review_queue


def _print_report(
    jrp: JRP, results: list[tuple[str, Score]], manual_review_queue: ManualReviewQueue
) -> None:
    print(f"JRP: {jrp.role_name} ({jrp.jrp_id}, v{jrp.version})")
    print(f"Scored: {len(results)}   Routed to manual review: {len(manual_review_queue)}")
    print()

    if results:
        print(f"{'Candidate':<30} {'Score':>7}  {'Tier':<12} Must-have")
        print("-" * 70)
        for label, score in results:
            must_have = (
                "pass" if score.passed_must_have else f"FAIL: {score.failed_must_have_label}"
            )
            print(f"{label:<30} {score.total_score:>7.1f}  {score.tier.value:<12} {must_have}")

    if len(manual_review_queue) > 0:
        print()
        print("Manual review queue:")
        for item in manual_review_queue.items():
            print(f"  - {item.submission.display_identifier}: {item.reason.value} ({item.detail})")


def main(argv: list[str] | None = None) -> int:
    args = build_argument_parser().parse_args(argv)

    try:
        jrp = load_jrp_from_yaml(args.jrp)
    except JRPConfigError as error:
        print(f"Error loading JRP config: {error}", file=sys.stderr)
        return 1

    audit_log: AuditLog = SqliteAuditLog(args.audit_db) if args.audit_db else InMemoryAuditLog()
    text_log = TextExtractionLog(args.text_log) if args.text_log else None

    results, manual_review_queue = run(args.resumes, jrp, audit_log, text_log)
    _print_report(jrp, results, manual_review_queue)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
