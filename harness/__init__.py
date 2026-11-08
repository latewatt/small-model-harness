"""Small-model harness: local inference, reproducible tasks, inspectable traces."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Configure dependencies before importing them; never load a user's global keys
# or create global library caches as a side effect of a benchmark.
for key, value in {
    "MSWEA_GLOBAL_CONFIG_DIR": str(ROOT / ".cache/mini-swe"),
    "MSWEA_SILENT_STARTUP": "1",
    "MSWEA_MODEL_RETRY_STOP_AFTER_ATTEMPT": "1",
    "LITELLM_LOCAL_MODEL_COST_MAP": "True",
    "LITELLM_LOG": "ERROR",
    "HF_HOME": str(ROOT / ".cache/huggingface"),
    "TIKTOKEN_CACHE_DIR": str(ROOT / ".cache/tiktoken"),
    "XDG_CACHE_HOME": str(ROOT / ".cache"),
    "PYTHONDONTWRITEBYTECODE": "1",
}.items():
    os.environ[key] = value

__version__ = "0.1.0"
