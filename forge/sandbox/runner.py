"""Sandbox execution dispatcher — handles Rust engine with Python fallback."""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import tempfile
import time
from typing import Any

logger = logging.getLogger(__name__)

# Dynamic import of the Rust engine
try:
    import forge_sandbox  # type: ignore
    _HAS_RUST = True
    logger.info("FORGE: Rust sandbox engine detected and loaded.")
except ImportError:
    _HAS_RUST = False
    logger.warning("FORGE: Rust sandbox NOT found. Falling back to subprocess runner.")


def _parse_pytest_output(stdout: str, stderr: str) -> list[dict[str, Any]]:
    """Common parser for pytest output across both execution paths."""
    tests = []
    combined = f"{stdout}\n{stderr}"

    # Extract test statuses
    pattern = r"(?m)^(\S+?)::(\S+)\s+(PASSED|FAILED|ERROR|SKIPPED)"
    for match in re.finditer(pattern, combined):
        tests.append({
            "name": f"{match.group(1)}::{match.group(2)}",
            "status": match.group(3).lower(),
            "message": "",
            "duration_ms": 0,
        })

    # Extract failure details
    fail_pattern = r"(?s)_{3,}\s+(test\S+)\s+_{3,}\n(.*?)(?=_{3,}|\={3,}|\z)"
    for match in re.finditer(fail_pattern, combined):
        name = match.group(1)
        block = match.group(2)
        msg_lines = [
            line.lstrip("E ").lstrip("E\t")
            for line in block.splitlines()
            if line.startswith(("E ", "E\t", "> "))
        ]
        for t in tests:
            if t["name"].endswith(name):
                t["message"] = "\n".join(msg_lines)

    return tests


def _run_python_fallback(
    source_files: dict[str, str],
    test_files: dict[str, str],
    timeout_secs: int,
) -> dict[str, Any]:
    """Hardened subprocess fallback for environments without Rust/PyO3."""
    with tempfile.TemporaryDirectory(prefix="forge_fallback_") as tmpdir:
        # Write files
        for name, content in {**source_files, **test_files}.items():
            p = os.path.join(tmpdir, name)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write(content)

        # Ensure package structure
        with open(os.path.join(tmpdir, "__init__.py"), "w") as f:
            pass

        cmd = ["python3", "-m", "pytest", "-v", "--tb=short", "--no-header"] + list(test_files.keys())
        env = {
            **os.environ,
            "PYTHONPATH": tmpdir,
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONUNBUFFERED": "1",
        }

        start = time.monotonic()
        try:
            proc = subprocess.run(
                cmd,
                cwd=tmpdir,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout_secs,
            )
            stdout, stderr, exit_code = proc.stdout, proc.stderr, proc.returncode
            timed_out = False
        except subprocess.TimeoutExpired:
            stdout, stderr, exit_code = "", "Execution timed out", -1
            timed_out = True

        elapsed_ms = int((time.monotonic() - start) * 1000)

        return {
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr,
            "tests": _parse_pytest_output(stdout, stderr),
            "total_duration_ms": elapsed_ms,
            "timed_out": timed_out,
        }


def run_sandbox(
    source_files: dict[str, str],
    test_files: dict[str, str],
    timeout_secs: int = 30,
    max_memory_mb: int = 512,
) -> dict[str, Any]:
    """Primary entry point for code execution."""
    if _HAS_RUST:
        try:
            raw_report = forge_sandbox.execute_sandbox(
                source_files, test_files, timeout_secs, max_memory_mb
            )
            return json.loads(raw_report)
        except Exception as exc:
            logger.error("Rust sandbox encountered a runtime error: %s", exc)
            # Fall through to Python if Rust fails

    return _run_python_fallback(source_files, test_files, timeout_secs)
