#!/usr/bin/env python
# SPDX-FileCopyrightText: 2026 The Botanu Authors
# SPDX-License-Identifier: Apache-2.0

"""Pre-publish red/green check for botanu-sdk-python.

Runs the full build → install → import → smoke-test chain in an isolated
venv so you know whether `git tag vX.Y.Z && git push --tags` is safe to do.

Usage (from repo root):

    python scripts/pre_publish_check.py

Exits 0 (GREEN) if everything passes. Exits 1 (RED) with a summary of
failures otherwise. Safe to re-run -- cleans up its own artifacts.

What it checks (in order):
    1. Working tree is clean (warning only, not a hard fail)
    2. Old dist/ and build/ artifacts removed
    3. `python -m build` produces sdist + wheel
    4. `twine check` passes on both artifacts
    5. Wheel installs cleanly into a fresh venv
    6. Version string is non-empty and not "0.0.0"
    7. All names in `botanu.__all__` are importable
    8. `enable()` initializes without raising
    9. `@botanu_workflow` with static ids decorates and runs a function
   10. `@botanu_workflow` with callable ids decorates and runs a function
   11. `emit_outcome("success", ...)` inside a decorated function works
   12. `emit_outcome` rejects invalid status with ValueError
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = REPO_ROOT / "dist"
BUILD_DIR = REPO_ROOT / "build"


# ---------------------------------------------------------------------------
# Output helpers -- ASCII only so they work on Windows cp1252 consoles.
# Colours are used only when stdout is a TTY that supports ANSI.
# ---------------------------------------------------------------------------

_USE_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None
if os.name == "nt":
    # Try to enable ANSI on modern Windows terminals; fall back to plain text.
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        _USE_COLOR = False


def _c(code: str) -> str:
    return code if _USE_COLOR else ""


GREEN = _c("\033[92m")
RED = _c("\033[91m")
YELLOW = _c("\033[93m")
BLUE = _c("\033[94m")
DIM = _c("\033[2m")
BOLD = _c("\033[1m")
RESET = _c("\033[0m")


def step(n: int, total: int, label: str) -> None:
    print(f"{BLUE}[{n}/{total}]{RESET} {label}...", flush=True)


def ok(msg: str = "") -> None:
    suffix = f" {DIM}{msg}{RESET}" if msg else ""
    print(f"      {GREEN}[OK]{RESET}{suffix}", flush=True)


def fail(msg: str) -> None:
    print(f"      {RED}[FAIL]{RESET} {msg}", flush=True)


def warn(msg: str) -> None:
    print(f"      {YELLOW}[WARN]{RESET} {msg}", flush=True)


def run(
    cmd: List[str],
    cwd: Path | None = None,
    env: dict | None = None,
    capture: bool = True,
) -> Tuple[int, str, str]:
    """Run a command and return (returncode, stdout, stderr)."""
    result = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=env,
        capture_output=capture,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


def cleanup(venv_dir: Path | None = None) -> None:
    """Remove build artifacts and the temp venv."""
    for d in (DIST_DIR, BUILD_DIR):
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
    for egg in REPO_ROOT.glob("*.egg-info"):
        shutil.rmtree(egg, ignore_errors=True)
    if venv_dir and venv_dir.exists():
        shutil.rmtree(venv_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def check_git_clean() -> bool:
    """Warn if uncommitted changes. Non-blocking."""
    code, out, _ = run(["git", "status", "--porcelain"], cwd=REPO_ROOT)
    if code != 0:
        warn("not a git repo or git unavailable -- skipping clean check")
        return True
    if out.strip():
        warn("working tree has uncommitted changes:")
        for line in out.strip().split("\n")[:5]:
            warn(f"  {line}")
        warn("the build will use git-derived version -- you may get a .devN suffix")
    else:
        ok()
    return True


def check_build() -> bool:
    """Run python -m build to produce sdist + wheel."""
    code, out, err = run(
        [sys.executable, "-m", "build"],
        cwd=REPO_ROOT,
    )
    if code != 0:
        fail("python -m build failed")
        print(DIM + (err or out)[-2000:] + RESET)
        return False
    # Confirm exactly one sdist and one wheel
    sdists = list(DIST_DIR.glob("*.tar.gz"))
    wheels = list(DIST_DIR.glob("*.whl"))
    if len(sdists) != 1 or len(wheels) != 1:
        fail(f"expected 1 sdist and 1 wheel in dist/, got {len(sdists)} sdists and {len(wheels)} wheels")
        return False
    ok(f"built {sdists[0].name} and {wheels[0].name}")
    return True


def check_twine() -> bool:
    """Validate package metadata with twine check."""
    artifacts = sorted(DIST_DIR.glob("*"))
    if not artifacts:
        fail("no artifacts in dist/")
        return False
    code, out, err = run(
        [sys.executable, "-m", "twine", "check"] + [str(a) for a in artifacts],
        cwd=REPO_ROOT,
    )
    if code != 0 or "PASSED" not in out:
        fail("twine check failed")
        print(DIM + (out or err)[-1500:] + RESET)
        return False
    ok()
    return True


def make_venv() -> Path:
    """Create a temp venv and return its path."""
    venv_dir = Path(tempfile.mkdtemp(prefix="botanu_prepublish_"))
    code, _, err = run([sys.executable, "-m", "venv", str(venv_dir)])
    if code != 0:
        raise RuntimeError(f"failed to create venv: {err}")
    return venv_dir


def venv_python(venv: Path) -> Path:
    """Return path to python inside the venv."""
    if os.name == "nt":
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


def check_install(venv: Path) -> bool:
    """Install the built wheel into the clean venv."""
    wheels = list(DIST_DIR.glob("*.whl"))
    if not wheels:
        fail("no wheel to install")
        return False
    py = venv_python(venv)
    code, out, err = run(
        [str(py), "-m", "pip", "install", "--quiet", str(wheels[0])],
        cwd=REPO_ROOT,
    )
    if code != 0:
        fail("pip install failed")
        print(DIM + (err or out)[-2000:] + RESET)
        return False
    ok(f"installed {wheels[0].name}")
    return True


def check_version(venv: Path) -> bool:
    """Import the package and print its version. Refuse empty or 0.0.0."""
    py = venv_python(venv)
    code, out, err = run(
        [str(py), "-c", "import botanu; print(botanu.__version__)"],
    )
    if code != 0:
        fail("failed to import botanu")
        print(DIM + (err or out)[-1500:] + RESET)
        return False
    version = out.strip()
    if not version or version in ("0.0.0", "unknown"):
        fail(f"version string is invalid: {version!r}")
        return False
    ok(f"version = {version}")
    return True


def check_api_surface(venv: Path) -> bool:
    """Import every name in botanu.__all__."""
    py = venv_python(venv)
    code, out, err = run(
        [
            str(py),
            "-c",
            (
                "import botanu; "
                "missing = [n for n in botanu.__all__ if not hasattr(botanu, n)]; "
                "print('MISSING:' + ','.join(missing) if missing else 'ALL OK'); "
                "print('EXPORTS:' + str(len(botanu.__all__)))"
            ),
        ],
    )
    if code != 0:
        fail("import failed")
        print(DIM + (err or out)[-1500:] + RESET)
        return False
    if "MISSING:" in out and "ALL OK" not in out:
        missing_line = [line for line in out.split("\n") if "MISSING:" in line][0]
        fail(missing_line)
        return False
    exports = [line for line in out.split("\n") if line.startswith("EXPORTS:")]
    count = exports[0].split(":")[1] if exports else "?"
    ok(f"all {count} names in __all__ importable")
    return True


SMOKE_TEST_SCRIPT = """
import logging
logging.getLogger('opentelemetry').setLevel(logging.CRITICAL)
logging.getLogger('botanu').setLevel(logging.CRITICAL)

import sys
errors = []

try:
    from botanu import enable, botanu_workflow, emit_outcome
except Exception as e:
    print(f"IMPORT_FAILED: {e!r}")
    sys.exit(1)

# Test 1: enable() does not raise
try:
    enable(service_name='prepublish-smoke-test')
except Exception as e:
    errors.append(f"enable() raised: {e!r}")

# Test 2: decorator with static ids
try:
    @botanu_workflow('smoke_static', event_id='evt-1', customer_id='cust-1')
    def _s(x):
        return x * 2
    assert _s(21) == 42, f"static decorator returned wrong value"
except Exception as e:
    errors.append(f"static decorator: {e!r}")

# Test 3: decorator with callable ids
try:
    @botanu_workflow(
        'smoke_callable',
        event_id=lambda req: req['id'],
        customer_id=lambda req: req['cust'],
    )
    def _c(req):
        return req['id']
    assert _c({'id': 'evt-2', 'cust': 'c-2'}) == 'evt-2', "callable decorator returned wrong value"
except Exception as e:
    errors.append(f"callable decorator: {e!r}")

# Test 4: emit_outcome inside a decorated function
try:
    @botanu_workflow('smoke_outcome', event_id='evt-3', customer_id='cust-3')
    def _o():
        emit_outcome('success', value_type='items', value_amount=1.0)
        return True
    assert _o() is True, "outcome flow returned wrong value"
except Exception as e:
    errors.append(f"emit_outcome inside span: {e!r}")

# Test 5: emit_outcome rejects invalid status
try:
    raised = False
    try:
        @botanu_workflow('smoke_bad', event_id='e', customer_id='c')
        def _b():
            emit_outcome('this-is-not-a-real-status')
        _b()
    except ValueError:
        raised = True
    if not raised:
        errors.append("emit_outcome did NOT reject invalid status")
except Exception as e:
    errors.append(f"bad-status check raised wrong error: {e!r}")

if errors:
    print("SMOKE_FAILED")
    for e in errors:
        print(f"  {e}")
    sys.exit(1)

print("SMOKE_OK")
"""


def check_smoke_test(venv: Path) -> bool:
    """Run the end-to-end smoke test inside the venv."""
    py = venv_python(venv)
    env = {
        **os.environ,
        "BOTANU_API_KEY": "btnu_test_prepublish_smoke",
        # Prevent the SDK from trying to ship to ingest.botanu.ai during the test
        "OTEL_TRACES_EXPORTER": "console",
        "OTEL_LOGS_EXPORTER": "console",
        "OTEL_METRICS_EXPORTER": "none",
    }
    code, out, err = run([str(py), "-c", SMOKE_TEST_SCRIPT], env=env)
    if "SMOKE_OK" in out:
        ok("decorator + outcome + validation all pass")
        return True
    fail("smoke test failed")
    # Filter OTel noise but keep our own output
    for line in (out + err).split("\n"):
        if line and not line.startswith(("INFO:", "DEBUG:", "WARNING:opentelemetry", "ERROR:opentelemetry")):
            print(f"        {DIM}{line}{RESET}")
    return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print(f"\n{BOLD}botanu-sdk-python -- pre-publish check{RESET}\n")
    print(f"Repo:   {REPO_ROOT}")
    print(f"Python: {sys.version.split()[0]}")
    print()

    total = 8
    results: List[bool] = []
    venv_dir: Path | None = None

    try:
        step(1, total, "git working tree clean")
        results.append(check_git_clean())

        step(2, total, "clean previous build artifacts")
        cleanup()
        ok()
        results.append(True)

        step(3, total, "python -m build")
        if not check_build():
            return summarize(results + [False])
        results.append(True)

        step(4, total, "twine check")
        if not check_twine():
            return summarize(results + [False])
        results.append(True)

        step(5, total, "create clean venv + install wheel")
        try:
            venv_dir = make_venv()
        except RuntimeError as e:
            fail(str(e))
            return summarize(results + [False])
        if not check_install(venv_dir):
            return summarize(results + [False])
        results.append(True)

        step(6, total, "version string")
        if not check_version(venv_dir):
            return summarize(results + [False])
        results.append(True)

        step(7, total, "public API surface (__all__)")
        if not check_api_surface(venv_dir):
            return summarize(results + [False])
        results.append(True)

        step(8, total, "end-to-end smoke test")
        if not check_smoke_test(venv_dir):
            return summarize(results + [False])
        results.append(True)

    finally:
        cleanup(venv_dir)

    return summarize(results)


def summarize(results: List[bool]) -> int:
    print()
    if all(results):
        print(f"{BOLD}{GREEN}GREEN{RESET} -- safe to tag and publish.")
        print()
        print("Next steps:")
        print("  1. Pick the next version (follow semver)")
        print("  2. git tag vX.Y.Z && git push origin vX.Y.Z")
        print("  3. GitHub Actions will publish to PyPI via OIDC")
        print()
        return 0
    failed = sum(1 for r in results if not r)
    print(f"{BOLD}{RED}RED{RESET} -- {failed} check(s) failed. Do NOT publish.")
    print()
    return 1


if __name__ == "__main__":
    sys.exit(main())
