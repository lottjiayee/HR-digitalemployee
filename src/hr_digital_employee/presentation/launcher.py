"""Console-script entry point: `hr-digital-employee-dashboard` launches the Streamlit
comparison-table/drill-down dashboard.

Streamlit apps are started with `streamlit run <file>`, not a plain Python entry point -- this
wraps that invocation so HR gets one memorable command instead of needing to know app.py's path.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_APP_PATH = Path(__file__).parent / "app.py"


def main() -> int:
    # Security: `streamlit run` with no --server.address binds every network interface by
    # default, not just localhost (see jrp_editor/launcher.py -- the same fix applies here).
    # app.py's Run form takes an arbitrary filesystem path with no authentication in front of it,
    # so leaving this at the default would let anyone on the LAN (or further, if the port is
    # reachable) read any resume/JRP file this process can reach.
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(_APP_PATH),
            "--server.address",
            "127.0.0.1",
        ]
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
