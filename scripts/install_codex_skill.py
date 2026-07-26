from __future__ import annotations

import os
from pathlib import Path


root = Path(__file__).resolve().parent.parent
source = root / "skills" / "create-tech-motion"
codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
target = codex_home / "skills" / "create-tech-motion"

target.parent.mkdir(parents=True, exist_ok=True)
if target.is_symlink() and target.resolve() == source:
    print(f"Already installed: {target} -> {source}")
elif target.exists() or target.is_symlink():
    raise SystemExit(f"Refusing to replace existing path: {target}")
else:
    target.symlink_to(source, target_is_directory=True)
    print(f"Installed: {target} -> {source}")
