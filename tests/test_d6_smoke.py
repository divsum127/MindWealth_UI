"""D6 smoke tests — runnable via pytest."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def test_d6_smoke_suite_all_pass():
    from testing.macro_th_exp.run_d6_smoke_tests import run_smoke_tests

    report = run_smoke_tests()
    assert report["all_pass"], report["results"]
