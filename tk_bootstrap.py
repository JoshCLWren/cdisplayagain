"""Configure Tcl/Tk paths for relocatable Python distributions."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def configure_tk_library() -> None:
    """Point Python at bundled Tcl/Tk libraries when they are available."""
    python_prefix = Path(sys.base_prefix)
    tcl_library = python_prefix / "lib" / "tcl8.6"
    tk_library = python_prefix / "lib" / "tk8.6"
    if tcl_library.is_dir():
        os.environ.setdefault("TCL_LIBRARY", str(tcl_library))
    if tk_library.is_dir():
        os.environ.setdefault("TK_LIBRARY", str(tk_library))


configure_tk_library()
