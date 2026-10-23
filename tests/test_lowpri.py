"""aicad.lowpri passes the exit code through and kills a command on timeout.
Run: python tests/test_lowpri.py   (pytest also works)"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*args):
    return subprocess.run([sys.executable, "-m", "aicad.lowpri", *args], cwd=ROOT,
                          capture_output=True, text=True, timeout=60)


def test_exit_code_passes_through():
    r = run("--timeout", "30", "--mem-gb", "1", "--", sys.executable, "-c", "import sys; sys.exit(3)")
    assert r.returncode == 3, r
    assert "[lowpri]" in r.stdout


def test_timeout_kills_and_returns_124():
    r = run("--timeout", "2", "--", sys.executable, "-c", "import time; time.sleep(30)")
    assert r.returncode == 124 and "TIMEOUT" in r.stdout, r


if __name__ == "__main__":
    n = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            n += 1
            print("pass", name)
    print(f"{n} tests passed")
