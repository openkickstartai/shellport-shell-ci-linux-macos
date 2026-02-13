"""Tests for ShellPort."""
import tempfile
from pathlib import Path

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


def test_scan_yaml_ci_file():
    """YAML run: blocks should be scanned — this is a documented feature."""
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "ci.yml"
        p.write_text(
            "name: CI\n"
            "on: push\n"
            "jobs:\n"
            "  build:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - run: |\n"
            "          grep -P 'test' output.log\n"
        )
        results = scan(d, {"linux", "macos"})
        assert len(results) == 1
        assert results[0]["command"] == "grep"
        assert results[0]["flag"] == "-P"


def test_scan_empty_directory():
    """Empty directory = zero findings, not a crash."""
    with tempfile.TemporaryDirectory() as d:
        results = scan(d, {"linux", "macos", "alpine"})
        assert results == []


def test_scan_portable_script_clean():
    """Fully portable script should produce zero findings."""
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "safe.sh"
        p.write_text("#!/bin/sh\ngrep -E 'foo' bar\necho done\n")
        results = scan(d, {"linux", "macos", "alpine"})
        assert results == []


def test_extract_semicolon_chained():
    """Semicolon-chained commands should all be parsed."""
    result = extract_commands("mkdir -p /tmp/x; readlink -f /tmp/x")
    assert ("readlink", ["-f"]) in result


def test_extract_subshell_commands():
    """Commands inside $() subshells should be extracted."""
    result = extract_commands("echo $(date -d '1 day ago')")
    assert ("date", ["-d"]) in result


def test_compat_unknown_command_is_ignored():
    """Commands not in compat_db should produce no findings."""
    findings = check_compat("my_custom_tool", ["--foo"], {"linux", "macos"})
    assert findings == []
