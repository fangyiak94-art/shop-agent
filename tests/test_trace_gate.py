"""The trace gate: every golden question must pass every check before a change can merge."""
import os

import pytest

from tests.golden import BUDGET, CASES, CUSTOMER
from tests.trace_harness import check, run_case

REPORT = os.environ.get("TRACE_GATE_REPORT", "trace-gate-report.md")


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_golden_question(case):
  tr = run_case(case["question"], CUSTOMER)
  violations = check(case, tr, BUDGET, CUSTOMER)
  if violations:
    detail = "\n".join(violations)
    with open(REPORT, "a") as f:
      f.write(f"### ❌ {case['id']}\n\n**Question:** {tr.question}\n\n**Answer:** {tr.answer}\n\n```\n{detail}\n\n{tr.render()}\n```\n\n")
    pytest.fail(f"\nTRACE GATE BLOCKED THIS CHANGE\nquestion: {tr.question}\nanswer:   {tr.answer}\n\n{detail}\n\ntrace:\n{tr.render()}\n", pytrace=False)
