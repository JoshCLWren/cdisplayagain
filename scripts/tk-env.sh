#!/usr/bin/env bash
# Print TCL_LIBRARY/TK_LIBRARY assignments for shells that need them, else nothing.
#
# uv installs python-build-standalone, which keeps Tcl/Tk under the interpreter
# prefix. Tk probes for init.tcl relative to the *venv* prefix, finds nothing,
# and every Tk() call dies with "Can't find a usable init.tcl". Homebrew and
# system pythons resolve it themselves, so this stays silent for them.
set -euo pipefail

[ "$(uname)" = "Darwin" ] || exit 0

python_bin=${PYTHON:-.venv/bin/python}
[ -x "$python_bin" ] || exit 0

"$python_bin" - <<'PY'
import shlex
import sys
from pathlib import Path

prefix = Path(sys.base_prefix)
tcl_library = prefix / "lib" / "tcl8.6"
tk_library = prefix / "lib" / "tk8.6"
if (tcl_library / "init.tcl").exists() and tk_library.is_dir():
    print(
        f"TCL_LIBRARY={shlex.quote(str(tcl_library))} "
        f"TK_LIBRARY={shlex.quote(str(tk_library))}"
    )
PY
