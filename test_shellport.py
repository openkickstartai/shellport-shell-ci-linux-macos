"""Tests for ShellPort."""
import tempfile
from pathlib import Path

import pytest

from shellport import extract_commands, check_compat, scan

from shellport import extract_commands, check_compat, scan


def test_extract_sed_flag():
    result = extract_commands("sed -i 's/foo/bar/' file.txt")
    assert result == [("sed", ["-i"])]


def test_extract_piped_commands():
    result = extract_commands("cat file | grep -P 'pattern' | sort -V")
    assert len(result) == 2
    assert ("grep", ["-P"]) in result
    assert ("sort", ["-V"]) in result


def test_extract_ignores_comments():
    assert extract_commands("# grep -P foo") == []
    assert extract_commands("") == []
    assert extract_commands("   ") == []


def test_extract_chained_commands():
    result = extract_commands("readlink -f /tmp && date -d '1 day'")
    assert len(result) == 2
    assert ("readlink", ["-f"]) in result
    assert ("date", ["-d"]) in result


def test_compat_gnu_only_flag():
    findings = check_compat("grep", ["-P"], {"linux", "macos"})
    assert len(findings) == 1
    assert "macos" in findings[0]["unsupported"]
    assert "linux" in findings[0]["supported"]


def test_compat_portable_flag():
    findings = check_compat("grep", ["-E"], {"linux", "macos", "alpine"})
    assert len(findings) == 0


def test_compat_bsd_only_flag():
    findings = check_compat("date", ["-j"], {"linux", "macos"})
    assert len(findings) == 1
    assert "linux" in findings[0]["unsupported"]
    assert "macos" in findings[0]["supported"]


def test_compat_includes_fix():
    findings = check_compat("sed", ["-i"], {"linux", "macos"})
    assert len(findings) == 1
    assert "portable" in findings[0]["fix"].lower() or "bak" in findings[0]["fix"]


def test_scan_shell_script():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "test.sh"
        p.write_text("#!/bin/bash\ngrep -P 'foo' bar\nreadlink -f /tmp\n")
        results = scan(d, {"linux", "macos", "alpine"})
        assert len(results) == 2
        cmds = {r["command"] for r in results}
        assert cmds == {"grep", "readlink"}


def test_scan_dockerfile():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "Dockerfile"
        p.write_text("FROM ubuntu\nRUN sed -i 's/a/b/' /etc/foo\nCOPY . .\n")
        results = scan(d, {"linux", "macos"})
        assert len(results) == 1
        assert results[0]["command"] == "sed"
        assert results[0]["flag"] == "-i"


def test_scan_makefile():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "Makefile"
        p.write_text("build:\n\tstat -c '%s' file\n\techo done\n")
        results = scan(d, {"linux", "macos"})
        assert len(results) == 1
        assert results[0]["command"] == "stat"


def test_scan_yaml_run_block():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "ci.yml"
        p.write_text("steps:\n  - name: test\n    run: |\n      grep -P 'x' f\n")
        results = scan(d, {"linux", "macos"})
        assert len(results) == 1
        assert results[0]["command"] == "grep"


def test_scan_clean_repo_no_issues():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "test.sh"
        p.write_text("#!/bin/bash\necho hello\nls -la\ngrep -E 'foo' bar\n")
        results = scan(d, {"linux", "macos", "alpine"})
        assert len(results) == 0


def test_scan_multiple_issues_in_one_file():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "deploy.sh"
        p.write_text("#!/bin/bash\nsed -i 's/x/y/' f\ngrep -P pat f\nsort -V list\n")
        results = scan(d, {"linux", "macos", "alpine"})
        assert len(results) == 3
        cmds = {r["command"] for r in results}
        assert cmds == {"sed", "grep", "sort"}


# ---------------------------------------------------------------------------
# YAML / CI file scanning
# ---------------------------------------------------------------------------

def test_scan_yaml_run_block():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "ci.yml"
        p.write_text(
            "name: CI\n"
            "jobs:\n"
            "  build:\n"
            "    steps:\n"
            "      - run: grep -P 'test' file\n"
        )
        results = scan(d, {"linux", "macos"})
        assert len(results) >= 1
        assert any(r["command"] == "grep" and r["flag"] == "-P" for r in results)


def test_scan_yaml_multiline_run():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "deploy.yaml"
        p.write_text(
            "steps:\n"
            "  - run: |\n"
            "      readlink -f /opt\n"
            "      date -d 'yesterday'\n"
        )
        results = scan(d, {"linux", "macos"})
        cmds = {r["command"] for r in results}
        assert "readlink" in cmds or "date" in cmds


# ---------------------------------------------------------------------------
# Parametrized compat-db coverage
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cmd,flag,unsupported_on", [
    ("grep", "-P", "macos"),
    ("sed", "-i", "macos"),
    ("readlink", "-f", "macos"),
    ("date", "-d", "macos"),
    ("date", "-j", "linux"),
    ("stat", "-c", "macos"),
])
def test_known_incompatible_flags(cmd, flag, unsupported_on):
    findings = check_compat(cmd, [flag], {"linux", "macos", "alpine"})
    assert len(findings) >= 1, f"{cmd} {flag} should be flagged"
    all_unsupported = set()
    for f in findings:
        all_unsupported.update(f["unsupported"])
    assert unsupported_on in all_unsupported


@pytest.mark.parametrize("cmd,flag", [
    ("grep", "-E"),
    ("grep", "-i"),
    ("grep", "-v"),
    ("sed", "-e"),
    ("sort", "-n"),
    ("sort", "-r"),
])
def test_known_portable_flags(cmd, flag):
    findings = check_compat(cmd, [flag], {"linux", "macos", "alpine"})
    assert len(findings) == 0, f"{cmd} {flag} should be portable"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_scan_empty_directory():
    with tempfile.TemporaryDirectory() as d:
        results = scan(d, {"linux", "macos"})
        assert results == []


def test_scan_nested_directories():
    with tempfile.TemporaryDirectory() as d:
        sub = Path(d) / "scripts"
        sub.mkdir()
        p = sub / "deploy.sh"
        p.write_text("#!/bin/bash\nreadlink -f /opt\n")
        results = scan(d, {"linux", "macos"})
        assert len(results) >= 1
        assert results[0]["command"] == "readlink"


def test_extract_semicolon_chained():
    result = extract_commands("grep -P 'foo' f; sed -i 's/a/b/' f")
    assert len(result) == 2
    assert ("grep", ["-P"]) in result
    assert ("sed", ["-i"]) in result


def test_extract_only_whitespace_and_empty():
    assert extract_commands("") == []
    assert extract_commands("   ") == []
    assert extract_commands("\t") == []
    assert extract_commands("\n") == []


def test_scan_ignores_non_target_files():
    """Binary / image files should not cause crashes."""
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "image.png"
        p.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)
        results = scan(d, {"linux", "macos"})
        assert results == []


# ---------------------------------------------------------------------------
# Structural guarantees — every finding MUST have a fix suggestion
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cmd,flags", [
    ("grep", ["-P"]),
    ("sed", ["-i"]),
    ("readlink", ["-f"]),
    ("date", ["-d"]),
    ("date", ["-j"]),
])
def test_all_findings_include_fix(cmd, flags):
    findings = check_compat(cmd, flags, {"linux", "macos"})
    for f in findings:
        assert "fix" in f, f"Missing 'fix' key for {cmd} {flags}"
        assert len(f["fix"]) > 0, f"Empty fix for {cmd} {flags}"


def test_finding_structure():
    """Verify the dict schema returned by check_compat."""
    findings = check_compat("grep", ["-P"], {"linux", "macos"})
    assert len(findings) == 1
    f = findings[0]
    required_keys = {"flag", "supported", "unsupported", "fix"}
    assert required_keys.issubset(f.keys()), f"Missing keys: {required_keys - f.keys()}"


def test_scan_result_has_location():
    """Each scan result should carry file path and line number."""
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "test.sh"
        p.write_text("#!/bin/bash\ngrep -P 'foo' bar\n")
        results = scan(d, {"linux", "macos"})
        assert len(results) == 1
        r = results[0]
        assert "file" in r or "path" in r, "Result missing file location"
        assert "line" in r or "lineno" in r, "Result missing line number"
