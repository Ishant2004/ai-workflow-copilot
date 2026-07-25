"""CLI entrypoint for the eval harness — a CI quality gate.

    python -m app.eval

Prints a JSON report and exits non-zero when the overall pass-rate is below
``EVAL_MIN_PASS_RATE``, so it can fail a CI pipeline on quality/grounding regressions.
"""

from __future__ import annotations

import asyncio
import json
import sys

from app.config import get_settings
from app.eval.runner import run_eval
from app.logging_config import configure_logging


def main() -> int:
    settings = get_settings()
    configure_logging(settings.log_level)

    report = asyncio.run(run_eval(settings))
    print(json.dumps(report.to_dict(), indent=2))

    gate = settings.eval_min_pass_rate
    if report.pass_rate < gate:
        print(
            f"FAIL: pass rate {report.pass_rate:.2%} < gate {gate:.2%}",
            file=sys.stderr,
        )
        return 1
    print(f"PASS: {report.passed_count}/{report.total} cases (rate {report.pass_rate:.2%})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
