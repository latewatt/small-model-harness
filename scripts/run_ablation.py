"""Run the preregistered single-change variants sequentially, retaining output."""
import json
import os
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
spec = json.loads((root / "research/phase2-experiment.json").read_text())
requested = sys.argv[1:] or spec["single_variants"]
fixed = spec["fixed"]
with (root / ".runtime/phase2-queue.log").open("a") as log:
    for agent in requested:
        command = ["make", "bench", f"MODEL={fixed['model']}", f"AGENT={agent}",
                   f"SUBSET={fixed['subset']}", f"STEPS={fixed['steps']}",
                   f"TASK_TIMEOUT={fixed['task_timeout_s']:g}", f"MAX_TOKENS={fixed['max_tokens']}",
                   f"BASE_URL={fixed['base_url']}"]
        header = "Starting: " + " ".join(command) + "\n"
        print(header, end="", flush=True); log.write(header); log.flush()
        process = subprocess.Popen(command, cwd=root, env=os.environ.copy(),
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in process.stdout:
            print(line, end="", flush=True); log.write(line); log.flush()
        if process.wait():
            raise SystemExit(f"Benchmark infrastructure failed for {agent}; queue stopped, artifacts retained")
