#!/usr/bin/env python3
"""Audit AutoResearchClaw batch outputs for operational and scientific readiness."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


RISK_TERMS = (
    "不一致",
    "conflict",
    "mismatch",
    "not trustworthy",
    "truncated",
    "截断",
    "failed",
    "N/A",
    "不可采信",
    "cannot support",
    "无法支持",
    "疑似编造",
)


@dataclass
class Finding:
    level: str
    item: str
    detail: str


@dataclass
class RunAudit:
    run_dir: Path
    findings: list[Finding] = field(default_factory=list)

    def add(self, level: str, item: str, detail: str) -> None:
        self.findings.append(Finding(level, item, detail))

    @property
    def hard_failures(self) -> list[Finding]:
        return [f for f in self.findings if f.level == "FAIL"]


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"__json_error__": str(exc)}


def scalar_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def audit_run(run_dir: Path, quality_threshold: float, profile: str) -> RunAudit:
    audit = RunAudit(run_dir=run_dir)

    summary = load_json(run_dir / "pipeline_summary.json")
    if not summary:
        audit.add("FAIL", "pipeline_summary", "missing")
    elif summary.get("__json_error__"):
        audit.add("FAIL", "pipeline_summary", summary["__json_error__"])
    else:
        if summary.get("final_status") != "done":
            audit.add("FAIL", "pipeline_summary", f"final_status={summary.get('final_status')}")
        if summary.get("stages_failed", 0) != 0:
            audit.add("FAIL", "pipeline_summary", f"stages_failed={summary.get('stages_failed')}")
        if summary.get("degraded"):
            audit.add("FAIL", "pipeline_summary", "degraded=true")

    stages_by_profile = {
        "screening": (9,),
        "pilot": (9, 10, 12),
        "full": (9, 10, 12, 20, 23),
    }
    for stage in stages_by_profile[profile]:
        health = load_json(run_dir / f"stage-{stage:02d}" / "stage_health.json")
        if not health:
            audit.add("FAIL", f"stage-{stage:02d}", "stage_health.json missing")
        elif health.get("__json_error__"):
            audit.add("FAIL", f"stage-{stage:02d}", health["__json_error__"])
        elif health.get("status") != "done":
            audit.add("FAIL", f"stage-{stage:02d}", f"status={health.get('status')}")

    if profile == "screening" and (run_dir / "stage-10").exists():
        audit.add("FAIL", "screening_boundary", "stage-10 exists; run did not stop at Stage09")

    if profile in {"pilot", "full"}:
        stage12_run = load_json(run_dir / "stage-12" / "runs" / "run-1.json")
        if not stage12_run:
            audit.add("FAIL", "stage-12/run-1", "missing")
        elif stage12_run.get("__json_error__"):
            audit.add("FAIL", "stage-12/run-1", stage12_run["__json_error__"])
        else:
            if stage12_run.get("status") != "completed":
                audit.add("FAIL", "stage-12/run-1", f"status={stage12_run.get('status')}")
            metrics = stage12_run.get("metrics") or {}
            if not metrics:
                audit.add("FAIL", "stage-12/run-1", "metrics empty")

        results = load_json(run_dir / "stage-12" / "runs" / "results.json")
        if not results:
            audit.add("FAIL", "stage-12/results", "results.json missing")
        elif results.get("__json_error__"):
            audit.add("FAIL", "stage-12/results", results["__json_error__"])
        elif not (results.get("metrics") or {}):
            audit.add("FAIL", "stage-12/results", "metrics empty")

    recovery = run_dir / "stage-10" / "code_agent_recovery.json"
    if recovery.exists():
        audit.add("WARN", "stage-10", "used code_agent_recovery.json")

    if profile == "full":
        quality = load_json(run_dir / "stage-20" / "quality_report.json")
        if not quality:
            audit.add("FAIL", "stage-20/quality", "quality_report.json missing")
        elif quality.get("__json_error__"):
            audit.add("FAIL", "stage-20/quality", quality["__json_error__"])
        else:
            score = quality.get("score_1_to_10")
            if not isinstance(score, (int, float)):
                audit.add("FAIL", "stage-20/quality", "score_1_to_10 missing")
            elif score < quality_threshold:
                audit.add("FAIL", "stage-20/quality", f"score={score} < {quality_threshold}")
            text = scalar_text(
                {
                    "verdict": quality.get("verdict"),
                    "weaknesses": quality.get("weaknesses"),
                    "required_actions": quality.get("required_actions"),
                }
            )
            for term in RISK_TERMS:
                if term.lower() in text.lower():
                    audit.add("FAIL", "stage-20/quality", f"risk term found: {term}")
                    break

        deliverables = run_dir / "deliverables"
        for name in ("paper.pdf", "paper_final.md", "manifest.json", "verification_report.json"):
            if not (deliverables / name).exists():
                audit.add("FAIL", "deliverables", f"{name} missing")

        refs = deliverables / "references.bib"
        if not refs.exists():
            audit.add("FAIL", "deliverables", "references.bib missing")
        elif refs.stat().st_size < 200:
            audit.add("FAIL", "deliverables", f"references.bib unusually small ({refs.stat().st_size} bytes)")

    return audit


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output_root", type=Path)
    parser.add_argument("--prefix", required=True)
    parser.add_argument(
        "--profile",
        choices=("screening", "pilot", "full"),
        default="full",
        help="screening=Stage09 only, pilot=through Stage12, full=final paper readiness",
    )
    parser.add_argument("--quality-threshold", type=float, default=4.0)
    args = parser.parse_args()

    run_dirs = sorted(args.output_root.glob(f"{args.prefix}_*"))
    if not run_dirs:
        print(f"No run dirs found for prefix {args.prefix}", flush=True)
        return 2

    all_audits = [
        audit_run(path, args.quality_threshold, args.profile)
        for path in run_dirs
        if path.is_dir()
    ]
    failed = 0
    for audit in all_audits:
        idx = audit.run_dir.name.split("_")[1] if "_" in audit.run_dir.name else "?"
        status = "FAIL" if audit.hard_failures else "PASS"
        if audit.hard_failures:
            failed += 1
        print(f"[{idx}] {status} {audit.run_dir.name}")
        for finding in audit.findings:
            print(f"  {finding.level:4} {finding.item}: {finding.detail}")

    print(f"\nSummary: {len(all_audits) - failed}/{len(all_audits)} pass")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
