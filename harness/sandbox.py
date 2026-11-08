"""macOS Seatbelt backend. No unconfined fallback for generated shell code."""
import json
import os
import platform
import selectors
import shlex
import signal
import subprocess
import time
from pathlib import Path

from . import ROOT


def quoted_path(path: Path):
    return json.dumps(str(path.resolve()))


class Sandbox:
    def __init__(self, work: Path, trace=None, deadline=None, readable=()):
        if platform.system() != "Darwin" or not Path("/usr/bin/sandbox-exec").exists():
            raise RuntimeError("local mini-suite requires macOS sandbox-exec; no unsafe fallback")
        self.work = work.resolve()
        self.trace, self.deadline = trace, deadline
        self.work.mkdir(parents=True, exist_ok=True)
        (self.work / ".tmp").mkdir(exist_ok=True)
        self.profile = self.work.parent / (self.work.name + ".sb")
        read_paths = ["/System", "/usr", "/bin", "/sbin", "/opt/homebrew", "/Library/Apple", "/private/etc", str(ROOT / ".venv"), str(self.work)]
        read_rules = " ".join(f"(subpath {json.dumps(p)})" for p in read_paths)
        read_rules += " ".join(f" (literal {quoted_path(Path(p))})" for p in readable)
        self.profile.write_text(
            '(version 1)\n(allow default)\n'
            '(deny file-write* network*)\n'
            '(deny file-read-data (subpath "/Users") (subpath "/Volumes"))\n'
            f'(allow file-read-data {read_rules})\n'
            '(allow file-read-data (literal "/dev/null") (literal "/dev/urandom") (literal "/dev/random"))\n'
            f'(allow file-write* (subpath {quoted_path(self.work)}) (literal "/dev/null"))\n'
        )

    def run(self, command: str, timeout: float = 12, max_output: int = 262144):
        if self.deadline is not None:
            timeout = min(timeout, max(0.01, self.deadline - time.monotonic()))
        env = {"PATH": f"{ROOT / '.venv/bin'}:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin",
               "TMPDIR": str(self.work / ".tmp"), "PYTHONDONTWRITEBYTECODE": "1",
               "PYTHONNOUSERSITE": "1", "PAGER": "cat", "LC_ALL": "en_US.UTF-8",
               "XDG_CACHE_HOME": str(self.work / ".tmp"), "GIT_CONFIG_NOSYSTEM": "1",
               "GIT_CONFIG_GLOBAL": "/dev/null"}
        # Preserve identity values (not keys). On macOS bash may call into
        # directory services and abort inside Seatbelt if HOME is absent.
        env.update({k: os.environ[k] for k in ("HOME", "USER", "LOGNAME", "SHELL") if k in os.environ})
        started = time.monotonic()
        # Bound individual file growth and CPU time as well as wall time/output.
        limited_command = "ulimit -f 16384; ulimit -t 15; " + command
        process = subprocess.Popen(["/usr/bin/sandbox-exec", "-f", str(self.profile), "/bin/bash", "--noprofile", "--norc", "-c", limited_command],
                                   cwd=self.work, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        chunks = bytearray()
        reason = ""
        try:
            while selector.get_map():
                if time.monotonic() - started >= timeout:
                    reason = "command timeout"
                    break
                for key, _ in selector.select(min(0.1, timeout)):
                    block = os.read(key.fileobj.fileno(), 8192)
                    if not block:
                        selector.unregister(key.fileobj)
                        break
                    chunks.extend(block)
                    if len(chunks) >= max_output:
                        reason = "command output limit"
                        break
                if reason:
                    break
        finally:
            if not reason:
                try:
                    process.wait(timeout=0.1)
                except subprocess.TimeoutExpired:
                    reason = "background process remained after output closed"
            # Also kill background children after successful foreground exit.
            # Background daemons must never outlive a tool invocation.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
            selector.close()
            process.stdout.close()
        result = {"output": bytes(chunks[:max_output]).decode("utf-8", "replace"),
                  "returncode": process.returncode if not reason else -1,
                  "exception_info": reason, "wall_s": time.monotonic() - started}
        if self.trace:
            self.trace.emit("tool", tool="shell", arguments={"command": command}, **result)
        return result

    def path(self, relative: str) -> Path:
        if not relative or Path(relative).is_absolute():
            raise ValueError("use a non-empty relative workspace path")
        resolved = (self.work / relative).resolve()
        if not resolved.is_relative_to(self.work):
            raise ValueError("path escapes task workspace (including symlinks)")
        return resolved

    def read(self, path: str, start: int = 1, lines: int = 100):
        target = self.path(path)
        if target.stat().st_size > 2 * 1024 * 1024:
            raise ValueError("file too large; use shell with a selective read")
        content = target.read_text().splitlines()
        return "\n".join(f"{i+1}: {line}" for i, line in enumerate(content) if start - 1 <= i < start - 1 + lines)

    def patch(self, path: str, old: str, new: str):
        target = self.path(path)
        if target.exists():
            text = target.read_text()
            if not old or text.count(old) != 1:
                raise ValueError("old text must match exactly once; read the file before patching")
            text = text.replace(old, new, 1)
        elif old:
            raise ValueError("new file requires empty old text")
        else:
            text = new
        if len(text.encode()) > 2 * 1024 * 1024:
            raise ValueError("patch exceeds file size limit")
        target.parent.mkdir(parents=True, exist_ok=True)
        # Use an exclusive temporary file, then atomic replacement. Reject any
        # symlink boundary again immediately before committing the write.
        import tempfile
        fd, name = tempfile.mkstemp(prefix=".patch-", dir=target.parent)
        try:
            with os.fdopen(fd, "w") as stream:
                stream.write(text)
            self.path(path)
            os.replace(name, target)
        finally:
            if os.path.exists(name):
                os.unlink(name)
        return f"patched {path}"

    def search(self, query: str, path: str = "."):
        self.path(path)
        # Fixed strings avoid pathological regexes; sandbox supplies timeout and
        # bounds. BSD grep is always present on the target Mac.
        return self.run(f"grep -R -n -F -- {shlex.quote(query)} {shlex.quote(path)}", timeout=5)
