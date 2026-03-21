"""Entry point for the ``scutl-agent`` console script.

This module re-exports :func:`main` from the standalone helper script so that
``pip install scutl-sdk`` places ``scutl-agent`` on ``$PATH``.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

# The canonical implementation lives in skills/scutl/scripts/scutl-agent.py.
# We load it at import time so the console_scripts entry point works whether
# the package was installed from wheel (shared-data) or from a source checkout.

_SCRIPT_LOCATIONS = [
    # Source checkout / sdist
    Path(__file__).resolve().parents[2] / "skills" / "scutl" / "scripts" / "scutl-agent.py",
    # Installed wheel (shared-data lands under sys.prefix)
    Path(sys.prefix) / "share" / "scutl-sdk" / "skills" / "scutl" / "scripts" / "scutl-agent.py",
]


def _find_script() -> Path:
    for p in _SCRIPT_LOCATIONS:
        if p.exists():
            return p
    raise FileNotFoundError(
        "Cannot find scutl-agent.py. Searched:\n"
        + "\n".join(f"  {p}" for p in _SCRIPT_LOCATIONS)
    )


def _load_module():  # type: ignore[no-untyped-def]
    script = _find_script()
    spec = importlib.util.spec_from_file_location("scutl_agent", script)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_mod = _load_module()
main = _mod.main
build_parser = _mod.build_parser
