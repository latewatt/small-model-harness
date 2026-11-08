"""Print (never silently launch) an official Harbor reference run command."""
import argparse
import json
import os
import shlex
from . import ROOT


def command(subset, model=None):
    runner = [str(ROOT / ".venv-harbor/bin/python"), str(ROOT / "scripts/harbor_local.py"), "run"]
    if subset == "tb2-fast15":
        spec = json.loads((ROOT / "subsets/tb2-fast15.json").read_text())
        runner += ["-d", spec["dataset"]]
        for task in spec["tasks"]:
            runner += ["-i", f"terminal-bench/{task}"]
        attempts = "1"
    elif subset == "tb2-full":
        spec = json.loads((ROOT / "subsets/tb2-fast15.json").read_text())
        runner += ["-d", spec["dataset"]]
        attempts = "5"
    else:
        raise ValueError("use SUBSET=tb2-fast15 or SUBSET=tb2-full; see RESEARCH.md for the current GPU-based 4.0 track")
    runner += ["-e", "docker", "-a", "terminus-2", "-m", "openai/" + (model or "qwen3.5:4b-q4_K_M"),
               "--base-url", "http://127.0.0.1:11435/v1", "-n", "1", "-k", attempts,
               "-o", str(ROOT / "runs/harbor"), "--ak", "temperature=0", "--ak", "reasoning_effort=none",
               "--ak", "proactive_summarization_threshold=2048",
               "--ak", "model_info=" + json.dumps({"max_input_tokens":8192,"max_output_tokens":1024,
                     "input_cost_per_token":0.0,"output_cost_per_token":0.0,"litellm_provider":"openai","mode":"chat"}, separators=(",", ":"))]
    if subset == "tb2-fast15":
        runner += ["--ak", "max_turns=16"]
    return runner


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--subset", default="tb2-fast15")
    args = parser.parse_args()
    print("# Official Terminus 2 reference command. Not executed by this planner.")
    print("# First start Docker yourself and confirm docker info succeeds.")
    print("# The local baseline measured tonight is mini-SWE-agent, not Terminus 2.")
    print("OPENAI_API_KEY=local " + shlex.join(command(args.subset, os.environ.get("MODEL"))))


if __name__ == "__main__": main()
