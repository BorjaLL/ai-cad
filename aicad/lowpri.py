"""Run a command at low priority on half the CPU cores, with a timeout and
(on Windows) a memory cap for the whole process tree.

    python -m aicad.lowpri [--timeout SEC] [--mem-gb GB] -- <command> [args...]

Why: boolean-heavy mesh checks and slicing used every core and made a
16-core desktop unusable (2026-09-29); later one run paged 32 GB RAM plus
the page file until the machine hard-froze (2026-10-22). Idle priority alone
does not stop that, so on Windows the tree runs in a Job Object with a
committed-memory limit: past it allocations fail (MemoryError or a native
crash) instead of freezing the machine. On Linux / macOS: nice 19, half the
cores for BLAS / OpenMP threads, timeout, no memory cap.

Exit code: the command's, or 124 on timeout (the whole tree is killed).
"""
from __future__ import annotations

import os
import subprocess
import sys

IDLE_PRIORITY_CLASS = 0x40
TIMEOUT_EXIT = 124


def _thread_env(n: int) -> dict:
    env = dict(os.environ, OMP_NUM_THREADS=str(n), OPENBLAS_NUM_THREADS=str(n),
               MKL_NUM_THREADS=str(n), NUMEXPR_NUM_THREADS=str(n))
    env.setdefault("PYTHONIOENCODING", "utf-8:replace")
    return env


def _posix(args, timeout):
    import signal
    half = max(1, (os.cpu_count() or 2) // 2)
    print(f"[lowpri] nice 19, {half} threads, timeout {timeout}s, no memory cap", flush=True)
    proc = subprocess.Popen(args, env=_thread_env(half), start_new_session=True,
                            preexec_fn=lambda: os.nice(19))
    try:
        return proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        print(f"[lowpri] TIMEOUT after {timeout}s: {' '.join(args)}", flush=True)
        return TIMEOUT_EXIT


def _windows(args, timeout, mem_gb):
    import ctypes
    from ctypes import wintypes

    k32 = ctypes.windll.kernel32
    k32.GetCurrentProcess.restype = ctypes.c_void_p
    k32.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    k32.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    h = k32.GetCurrentProcess()
    n = os.cpu_count() or 2
    half = max(1, n // 2)
    # priority class and affinity are inherited by child processes
    if not k32.SetPriorityClass(h, IDLE_PRIORITY_CLASS):
        raise OSError("SetPriorityClass failed")
    if not k32.SetProcessAffinityMask(h, (1 << half) - 1):
        raise OSError("SetProcessAffinityMask failed")

    class _Io(ctypes.Structure):
        _fields_ = [(f, ctypes.c_ulonglong) for f in ("r", "w", "o", "rb", "wb", "ob")]

    class _Basic(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong), ("PerJobUserTimeLimit", ctypes.c_longlong),
                    ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD)]

    class _Ext(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", _Basic), ("IoInfo", _Io),
                    ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

    job = None
    if mem_gb > 0:
        k32.CreateJobObjectW.restype = ctypes.c_void_p
        k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
        k32.SetInformationJobObject.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        k32.AssignProcessToJobObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        k32.QueryInformationJobObject.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p,
                                                  wintypes.DWORD, ctypes.c_void_p]
        job = k32.CreateJobObjectW(None, None)
        lim = _Ext()
        # job memory limit + kill-on-close: if this process dies, the tree goes with it
        lim.BasicLimitInformation.LimitFlags = 0x200 | 0x2000
        lim.JobMemoryLimit = int(mem_gb * (1 << 30))
        if not (job and k32.SetInformationJobObject(job, 9, ctypes.byref(lim), ctypes.sizeof(lim))):
            raise OSError("SetInformationJobObject failed")
        if not k32.AssignProcessToJobObject(job, h):   # children inherit the job
            raise OSError("AssignProcessToJobObject failed")

    def peak_gb():
        lim = _Ext()
        k32.QueryInformationJobObject(job, 9, ctypes.byref(lim), ctypes.sizeof(lim), None)
        return lim.PeakJobMemoryUsed / (1 << 30)

    cap = f"{mem_gb:g} GB" if job else "no"
    print(f"[lowpri] idle priority, {half}/{n} cores, timeout {timeout}s, {cap} memory cap", flush=True)
    proc = subprocess.Popen(args, env=_thread_env(half))
    try:
        rc = proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
        print(f"[lowpri] TIMEOUT after {timeout}s: {' '.join(args)}", flush=True)
        return TIMEOUT_EXIT
    if job and peak_gb() > 0.95 * mem_gb:
        print(f"[lowpri] hit the {mem_gb:g} GB memory cap (peak {peak_gb():.1f} GB): a MemoryError or "
              "crash above is the cap; shrink the job or raise --mem-gb", flush=True)
    # Windows reports negative exit codes as unsigned: pass the signed value through
    return rc - (1 << 32) if rc >= (1 << 31) else rc


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    timeout, mem_gb = 900, float(os.environ.get("LOWPRI_MEM_GB", "12"))
    while args[:1] in (["--timeout"], ["--mem-gb"]):
        if args[0] == "--timeout":
            timeout = int(args[1])
        else:
            mem_gb = float(args[1])
        args = args[2:]
    if args[:1] == ["--"]:
        args = args[1:]
    if not args:
        print(__doc__, file=sys.stderr)
        return 2
    if os.name == "nt":
        return _windows(args, timeout, mem_gb)
    return _posix(args, timeout)


if __name__ == "__main__":
    sys.exit(main())
