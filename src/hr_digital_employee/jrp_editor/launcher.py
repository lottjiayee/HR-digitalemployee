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
    # Security: `streamlit run` with no --server.address binds every network interface by
    # default, not just localhost (confirmed -- its own startup banner prints a LAN "Network URL"
    # and a public "External URL"). app.py's Load/Save fields take an arbitrary filesystem path
    # with no authentication in front of them, so leaving this at the default would turn "read/
    # write any file this process can reach" into something anyone on the LAN (or the internet, if
    # the port is reachable) could do with no login. Restricted to loopback-only; see
    # ASSUMPTIONS.md for what a real network-facing deployment would need to add first.
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
