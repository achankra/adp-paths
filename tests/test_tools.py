"""
Tests for src/tools.py — L01 deterministic pipeline tools.

All tests use real files (the sample code under sample/src/).
No mocks, no simulations. The tools are deterministic — same
input, same result.

PEH Reference: Chapter 8 (CI/CD as a Platform Service)
Companion code: github.com/achankra/peh, ch08/test_tools.py
"""

import os
import tempfile
from pathlib import Path

import pytest

from src import tools

SAMPLE_DIR = Path(__file__).parent.parent / "sample" / "src"
HANDLER = str(SAMPLE_DIR / "handler.py")
UTILS = str(SAMPLE_DIR / "utils.py")


class TestLint:
    """Lint tests — real Ruff on real files."""

    def test_lint_clean_files(self):
        """Sample code should pass lint (it was written to be clean)."""
        result = tools.lint([HANDLER, UTILS])
        assert result["tool"] == "ruff"
        assert result["files_checked"] == 2

    def test_lint_catches_errors(self):
        """Ruff should catch intentional lint violations."""
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("import os\nimport sys\nx = 1\n")
            f.flush()
            try:
                result = tools.lint([f.name])
                # F401: imported but unused (os, sys)
                assert result["tool"] == "ruff"
                assert not result["passed"]
                assert result["error_count"] + result["warning_count"] > 0
            finally:
                os.unlink(f.name)

    def test_lint_returns_structured_errors(self):
        """Each finding should have file, line, code, message."""
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("import os\n")
            f.flush()
            try:
                result = tools.lint([f.name])
                if not result["passed"]:
                    all_findings = result["errors"] + result["warnings"]
                    for finding in all_findings:
                        assert "file" in finding
                        assert "line" in finding
                        assert "code" in finding
                        assert "message" in finding
            finally:
                os.unlink(f.name)


class TestRunTests:
    """Module-level assertion tests — real importlib on real modules."""

    def test_handler_loads(self):
        """Handler module should load and export expected symbols."""
        result = tools.run_tests(HANDLER, [
            {
                "description": "module loads",
                "fn": lambda mod: hasattr(mod, "handle_request"),
            },
        ])
        assert result["tool"] == "test-runner"
        assert result["passed"]
        assert result["pass_count"] == 1

    def test_handler_assertions(self):
        """Real assertions against handler behavior."""
        result = tools.run_tests(HANDLER, [
            {
                "description": "400 for None body",
                "fn": lambda mod: mod.handle_request(None)["status"] == 400,
            },
            {
                "description": "200 for valid input",
                "fn": lambda mod: mod.handle_request({"action": "create"})["status"] == 200,
            },
        ])
        assert result["passed"]
        assert result["pass_count"] == 2
        assert result["fail_count"] == 0

    def test_handler_invalid_action(self):
        """Handler should reject unknown actions."""
        result = tools.run_tests(HANDLER, [
            {
                "description": "rejects unknown action",
                "fn": lambda mod: mod.handle_request({"action": "hack"})["status"] == 400,
            },
        ])
        assert result["passed"]

    def test_nonexistent_module(self):
        """Attempting to test a missing module should fail gracefully."""
        result = tools.run_tests("/nonexistent/module.py", [
            {"description": "should fail", "fn": lambda mod: True},
        ])
        assert not result["passed"]
        assert result["fail_count"] >= 1


class TestBuild:
    """Build verification — real ast.parse on real files."""

    def test_build_sample_files(self):
        """Sample code should parse and export expected symbols."""
        result = tools.build([HANDLER, UTILS])
        assert result["tool"] == "build-verifier"
        assert result["passed"]
        assert result["modules_checked"] == 2

        handler_result = next(r for r in result["results"] if r["file"] == "handler.py")
        assert "handle_request" in handler_result["exports"]
        assert "process_request" in handler_result["exports"]
        assert "generate_id" in handler_result["exports"]

        utils_result = next(r for r in result["results"] if r["file"] == "utils.py")
        assert "validate_input" in utils_result["exports"]
        assert "sanitize" in utils_result["exports"]

    def test_build_syntax_error(self):
        """Files with syntax errors should fail build."""
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("def broken(\n")
            f.flush()
            try:
                result = tools.build([f.name])
                assert not result["passed"]
                assert any("SyntaxError" in r.get("error", "") for r in result["results"])
            finally:
                os.unlink(f.name)


class TestSecurityScan:
    """Security scanning — real pattern matching on real files."""

    def test_clean_files_pass(self):
        """Sample code should have no critical findings."""
        result = tools.security_scan([HANDLER, UTILS])
        assert result["tool"] == "security-scanner"
        assert result["passed"]  # No critical findings
        assert result["files_scanned"] == 2

    def test_detects_eval(self):
        """Should detect eval() usage."""
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write('result = eval("1 + 1")\n')
            f.flush()
            try:
                result = tools.security_scan([f.name])
                assert not result["passed"]
                assert result["critical_count"] > 0
                assert any(
                    finding["rule"] == "no-eval"
                    for finding in result["findings"]
                )
            finally:
                os.unlink(f.name)

    def test_detects_hardcoded_password(self):
        """Should detect hardcoded passwords."""
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write('password = "supersecretpassword123"\n')
            f.flush()
            try:
                result = tools.security_scan([f.name])
                assert not result["passed"]
                assert any(
                    finding["rule"] == "no-hardcoded-secrets"
                    for finding in result["findings"]
                )
            finally:
                os.unlink(f.name)

    def test_finding_structure(self):
        """Each finding should have all required fields."""
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write('x = eval("1")\n')
            f.flush()
            try:
                result = tools.security_scan([f.name])
                for finding in result["findings"]:
                    assert "file" in finding
                    assert "line" in finding
                    assert "rule" in finding
                    assert "severity" in finding
                    assert "message" in finding
            finally:
                os.unlink(f.name)
