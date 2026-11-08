import argparse
import json
import os
import subprocess
import sys

from . import ROOT


def main():
    parser = argparse.ArgumentParser(description="Small-model harness measurement rig")
    parser.add_argument("command", choices=["bench", "report", "view", "doctor"])
    args = parser.parse_args()
    if args.command == "bench":
        from .bench import run_bench
        run_bench(model=os.getenv("MODEL", "qwen3.5:4b-q4_K_M"),
                  agent=os.getenv("AGENT", "v0"), subset=os.getenv("SUBSET", "mini10"),
                  base_url=os.getenv("BASE_URL", "http://127.0.0.1:11435/v1"),
                  steps=int(os.getenv("STEPS", "16")), task_timeout=float(os.getenv("TASK_TIMEOUT", "240")),
                  max_tokens=int(os.getenv("MAX_TOKENS", "1024")))
    elif args.command == "report":
        from .report import report
        print(report())
    elif args.command == "view":
        paths = sorted((ROOT / "runs").glob("*/viewer.html"))
        if not paths:
            raise SystemExit("No complete runs; run make bench first")
        selected = os.getenv("RUN")
        path = (ROOT / "runs" / selected / "viewer.html") if selected else paths[-1]
        if not path.resolve().is_relative_to(ROOT / "runs"):
            raise SystemExit("RUN must name a run under runs/")
        subprocess.run(["open", str(path)], check=True)
    else:
        from .server import status
        print(status())
        for command in (["sysctl", "-n", "machdep.cpu.brand_string", "hw.memsize"], ["docker", "info", "--format", "{{json .ServerVersion}}"]):
            try:
                r = subprocess.run(command, capture_output=True, text=True, timeout=8)
                print(" ".join(command), r.stdout.strip() or r.stderr.strip())
            except (FileNotFoundError, subprocess.TimeoutExpired) as e:
                print(type(e).__name__)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, FileNotFoundError) as e:
        print(f"Error: {e}", file=sys.stderr)
        raise SystemExit(2)
