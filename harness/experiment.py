"""Fail closed if a scored Phase 2 ablation drifts from its preregistration."""
import hashlib
import json
import os

from . import ROOT


def core_digest():
    from .bench import CORE_FILES
    digest = hashlib.sha256()
    for name in sorted(CORE_FILES):
        digest.update(name.encode() + b"\0" + (ROOT / "harness" / name).read_bytes())
    return digest.hexdigest()


def validate_experiment(config, identity, suite, subset, steps, task_timeout, features):
    from .bench import digest_tree
    path = ROOT / "research/phase2-experiment.json"
    spec = json.loads(path.read_text())
    actual = {"model": config.model, "model_digest": identity.get("digest"),
              "suite_sha256": digest_tree(suite), "subset": subset, "steps": steps,
              "task_timeout_s": task_timeout, "max_tokens": config.max_tokens,
              "temperature": config.temperature, "seed": config.seed,
              "base_url": config.base_url, "request_timeout_s": config.request_timeout}
    for key, value in spec["fixed"].items():
        if actual.get(key) != value:
            raise ValueError(f"Phase 2 invariant changed: {key}; expected {value!r}, got {actual.get(key)!r}")
    if os.getenv("HARNESS_REASONING_EFFORT", "none") != "none":
        raise ValueError("Phase 2 keeps reasoning_effort=none")
    if core_digest() != spec["frozen_core_sha256"]:
        raise ValueError("Phase 2 core changed after preregistration; do not silently mix revisions. "
                         "Check out the `phase2-results` tag to reproduce those runs.")
    return {"spec_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "reference_run": spec["reference_run"], "features": sorted(features),
            "frozen_core_sha256": spec["frozen_core_sha256"],
            "selection_policy": spec["selection_policy"]}
