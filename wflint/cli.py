import argparse
import json
import sys
from pathlib import Path

from .lint import lint_workflow


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="workflow-lint",
        description="Static reliability checks for n8n-style workflow JSON exports.")
    ap.add_argument("files", nargs="+", help="workflow JSON files")
    ap.add_argument("--json", action="store_true", help="print findings as JSON")
    ap.add_argument("--fail-on", choices=["high", "medium", "low"], default="high",
                    help="exit 1 if a finding at this level or worse exists (default: high)")
    args = ap.parse_args(argv)

    order = {"high": 0, "medium": 1, "low": 2}
    worst = 99
    report = {}
    for f in args.files:
        try:
            wf = json.loads(Path(f).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"{f}: cannot read ({e})", file=sys.stderr)
            return 2
        findings = lint_workflow(wf)
        report[f] = [x.to_dict() for x in findings]
        for x in findings:
            worst = min(worst, order[x.severity])
        if not args.json:
            print(f"{f}: {len(findings)} finding(s)")
            for x in findings:
                print(f"  [{x.severity}] {x.rule} @ {x.node}: {x.message}")
    if args.json:
        print(json.dumps(report, indent=2))
    return 1 if worst <= order[args.fail_on] else 0


if __name__ == "__main__":
    sys.exit(main())
