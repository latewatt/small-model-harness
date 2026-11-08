"""Run pinned Harbor with caches/auth state confined to this workspace.

Harbor 0.25.0 hardcodes several expanded home paths. Rebind those constants
before importing its CLI rather than changing HOME or modifying the package.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import harness  # configure workspace-local dependency caches
import harbor.constants as paths

cache = ROOT / ".cache/harbor"
for key, value in {
    "CACHE_DIR": cache, "TASK_CACHE_DIR": cache / "tasks",
    "PACKAGE_CACHE_DIR": cache / "tasks/packages", "DATASET_CACHE_DIR": cache / "datasets",
    "NOTIFICATIONS_PATH": cache / "notifications.json",
}.items():
    setattr(paths, key, value)
import harbor.auth.constants as auth
auth.CREDENTIALS_DIR = ROOT / ".runtime/harbor-auth"
auth.CREDENTIALS_PATH = auth.CREDENTIALS_DIR / "credentials.json"
auth.OAUTH_PENDING_PATH = auth.CREDENTIALS_DIR / "oauth-pending.json"
os.environ["HARBOR_TELEMETRY"] = "0"
from harbor.cli.main import app

if __name__ == "__main__": app()
