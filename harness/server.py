"""Manage only the workspace-owned Ollama process, weights and logs."""
import argparse
import json
import os
import signal
import subprocess
import time
import urllib.request

from . import ROOT

URL = "http://127.0.0.1:11435"
STATE = ROOT / ".runtime/owned-server.json"


def request(path, payload=None, timeout=5):
    req = urllib.request.Request(URL + path, data=json.dumps(payload).encode() if payload is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


def fingerprint(pid):
    result = subprocess.run(["ps", "-p", str(pid), "-o", "lstart=", "-o", "command="], capture_output=True, text=True)
    return result.stdout.strip()


def owned_state():
    if not STATE.exists():
        return None
    state = json.loads(STATE.read_text())
    current = fingerprint(state["pid"])
    if current and current == state["fingerprint"] and "ollama" in current and "serve" in current:
        return state
    return None


def status():
    state = owned_state()
    try:
        return json.dumps({"owned": bool(state), "pid": state["pid"] if state else None,
                           "url": URL + "/v1", "version": request("/api/version"),
                           "loaded": request("/api/ps"), "models": request("/api/tags")}, indent=2)
    except OSError:
        return "Workspace Ollama is not responding. Run make serve."


def start():
    if owned_state():
        print(status()); return
    try:
        request("/api/version")
    except OSError:
        pass
    else:
        raise SystemExit("Port 11435 is in use by an unowned server; leaving it alone.")
    import shutil
    executable = shutil.which("ollama")
    if not executable:
        raise SystemExit("Ollama is not installed. Install Ollama first; no automatic system changes.")
    for p in (ROOT / ".runtime", ROOT / "models", ROOT / ".cache/tmp"):
        p.mkdir(parents=True, exist_ok=True)
    profile = ROOT / ".runtime/server.sb"
    profile.write_text('(version 1)\n(allow default)\n(deny file-write*)\n'
                       f'(allow file-write* (subpath {json.dumps(str(ROOT))}) (literal "/dev/null"))\n')
    env = os.environ.copy()
    env.update(OLLAMA_HOST="127.0.0.1:11435", OLLAMA_MODELS=str(ROOT / "models"),
               OLLAMA_CONTEXT_LENGTH="8192", OLLAMA_NUM_PARALLEL="1", OLLAMA_MAX_LOADED_MODELS="1",
               OLLAMA_FLASH_ATTENTION="1", OLLAMA_KV_CACHE_TYPE="q8_0", OLLAMA_KEEP_ALIVE="5m",
               OLLAMA_NO_CLOUD="1", TMPDIR=str(ROOT / ".cache/tmp"))
    with (ROOT / ".runtime/ollama.log").open("ab") as log:
        process = subprocess.Popen(["/usr/bin/sandbox-exec", "-f", str(profile), executable, "serve"],
                                   env=env, stdout=log, stderr=log, start_new_session=True)
    for _ in range(50):
        if process.poll() is not None:
            raise SystemExit("Ollama stopped; inspect .runtime/ollama.log")
        try:
            request("/api/version", timeout=1)
            break
        except OSError:
            time.sleep(0.1)
    else:
        process.terminate()
        raise SystemExit("Ollama did not become ready")
    STATE.write_text(json.dumps({"pid": process.pid, "fingerprint": fingerprint(process.pid)}, indent=2))
    (ROOT / ".runtime/server-config.json").write_text(json.dumps({k:v for k,v in env.items() if k.startswith("OLLAMA_")}, indent=2))
    print(status())


def stop():
    state = owned_state()
    if not state:
        raise SystemExit("No verified workspace-owned server to stop.")
    os.kill(state["pid"], signal.SIGTERM)
    STATE.unlink()
    print("Stopped workspace-owned Ollama.")


def pull(model):
    if not owned_state():
        raise SystemExit("Run make serve first; model downloads require the owned server.")
    # Registry sizes are checked BEFORE downloading any weights. Use explicit
    # tags, never 'latest', whose architecture/size can silently change.
    if ":" not in model or model.endswith(":latest") or "/" in model or "cloud" in model:
        raise SystemExit("Use an explicit local Ollama library tag, e.g. qwen3.5:4b-q4_K_M.")
    name, tag = model.split(":", 1)
    with urllib.request.urlopen(f"https://registry.ollama.ai/v2/library/{name}/manifests/{tag}", timeout=30) as response:
        manifest = json.load(response)
    size = sum(layer["size"] for layer in manifest["layers"])
    ram = int(subprocess.check_output(["sysctl", "-n", "hw.memsize"]))
    cap = min(4 * 1024**3, ram // 4)
    if size > cap:
        raise SystemExit(f"Model download {size} bytes exceeds the conservative {cap} byte cap.")
    print(f"Downloading {model}: {size} bytes into {ROOT / 'models'}", flush=True)
    req = urllib.request.Request(URL + "/api/pull", data=json.dumps({"model": model, "stream": True}).encode(), headers={"Content-Type":"application/json"})
    last = 0
    with urllib.request.urlopen(req, timeout=180) as response, (ROOT / ".runtime/pull.jsonl").open("a") as log:
        for line in response:
            item = json.loads(line); log.write(line.decode()); log.flush()
            if "error" in item: raise SystemExit(item["error"])
            if time.monotonic() - last > 15 or item.get("status") == "success":
                print(item, flush=True); last = time.monotonic()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["start", "stop", "status", "pull"])
    command = parser.parse_args().command
    if command == "status": print(status())
    elif command == "pull": pull(os.environ.get("MODEL", "qwen3.5:4b-q4_K_M"))
    else: globals()[command]()


if __name__ == "__main__": main()
