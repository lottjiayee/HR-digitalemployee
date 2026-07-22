"""Console-script entry point: `hr-digital-employee-jrp-editor` launches the Streamlit JRP form.

Streamlit apps are started with `streamlit run <file>`, not a plain Python entry point -- this
wraps that invocation so HR gets one memorable command instead of needing to know app.py's path.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_APP_PATH = Path(__file__).parent / "app.py"


def main() -> int:
    return subprocess.run([sys.executable, "-m", "streamlit", "run", str(_APP_PATH)]).returncode


if __name__ == "__main__":
    raise SystemExit(main())
