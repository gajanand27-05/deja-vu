"""Environment setup for Cognee — pin data dirs to the repo, disable multi-user.

Cognee 1.0+ defaults to backend access control + multi-tenant auth. For a
single-user hackathon demo we want neither — they add ceremony that muddies the
demo without helping the story. Toggled off here before cognee imports elsewhere.
"""

from __future__ import annotations

import os
from pathlib import Path


def prepare_cognee_env(data_dir: Path) -> None:
    """Set env vars + cognee config to point at a repo-local data root.

    Idempotent — safe to call at every command entry point.
    """
    data_dir = data_dir.resolve()
    data_dir.mkdir(parents=True, exist_ok=True)

    # Disable multi-user access control before cognee loads its auth chain.
    os.environ.setdefault("ENABLE_BACKEND_ACCESS_CONTROL", "false")
    os.environ.setdefault("CACHING", "false")

    # Pin cognee's data + system root to our repo so seed/wipe is self-contained.
    system_root = data_dir / "system"
    data_root = data_dir / "data"
    system_root.mkdir(parents=True, exist_ok=True)
    data_root.mkdir(parents=True, exist_ok=True)

    import cognee

    cognee.config.system_root_directory(str(system_root))
    cognee.config.data_root_directory(str(data_root))
