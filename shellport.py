#!/usr/bin/env python3
"""ShellPort - Cross-platform shell command compatibility analyzer."""
import argparse
import json
import os
import re
import sys
from pathlib import Path

from compat_db import FLAG_COMPAT, FIXES, PLATFORMS

SCAN_EXTS = {".sh", ".bash", ".zsh", ".yml", ".yaml", ".mk"}
SCAN_NAMES = {"Makefile", "Justfile", "Dockerfile"}


def extract_commands(line):
    """Extract (command, [flags]) tuples from a shell command line."""
    line = re.sub(r"#.*$", "", line).strip()
    if not line:
        return []
    results = []
    for part in re.split(r"[|;&]+", line):
        tokens = part.split()
        if not tokens:
            continue
        cmd = os.path.basename(tokens[0])
        flags = [t for t in tokens[1:] if t.startswith("-")]
        if cmd in FLAG_COMPAT:
            results.append((cmd, flags))
    return results


def parse_file(filepath):
    """Yield (line_number, shell_line) from supported file types."""
    try:
        lines = Path(filepath).read_text(errors="ignore").splitlines()
    except OSError:
        return
    name = os.path.basename(filepath)
    ext = Path(filepath).suffix
    if ext in (".sh", ".bash", ".zsh"):
        for i, line in enumerate(lines, 1):
            yield i, line
    elif name == "Dockerfile":
        for i, line in enumerate(lines, 1):
            s = line.strip()
            if s.upper().startswith("RUN "):
                yield i, s[4:]
    elif name in ("Makefile", "Justfile"):
        for i, line in enumerate(lines, 1):
            if line.startswith("\t"):
                yield i, line.strip()
    elif ext in (".yml", ".yaml"):
        in_run = False
        for i, line in enumerate(lines, 1):
            s = line.strip()
            if re.match(r"run\s*:\s*\|?\s*$", s):
                in_run = True
            elif in_run and s and not re.match(r"^\w[\w-]*:", s):
                yield i, s
            elif re.match(r"^\w[\w-]*:", s):
                in_run = False


def check_compat(cmd, flags, targets):
    """Return findings for incompatible flags."""
    findings = []
    db = FLAG_COMPAT.get(cmd, {})
    for flag in flags:
        if flag in db:
            supported = db[flag]
            missing = targets - supported
            if missing:
                findings.append({
                    "command": cmd, "flag": flag,
                    "supported": sorted(supported & targets),
                    "unsupported": sorted(missing),
                    "fix": FIXES.get((cmd, flag), "Check POSIX spec for portable alternative"),
                })
    return findings


def scan(root, targets):
    """Scan a directory tree and return all compatibility findings."""
    results = []
    for path in sorted(Path(root).rglob("*")):
        if not path.is_file() or ".git" in path.parts:
            continue
        if path.suffix in SCAN_EXTS or path.name in SCAN_NAMES:
            for lineno, line in parse_file(str(path)):
                for cmd, flags in extract_commands(line):
                    for f in check_compat(cmd, flags, targets):
                        f.update(file=str(path.relative_to(root)), line=lineno)
                        results.append(f)
    return results


def format_text(results):
    """Format results as human-readable text."""
    if not results:
        return "No portability issues found."
    out = []
    for r in results:
        label = "WARNING" if r["supported"] else "ERROR"
        out.append(
            f'{r["file"]}:{r["line"]}  [{label}]  `{r["command"]} {r["flag"]}`'
            f'  missing on: {", ".join(r["unsupported"])}'
        )
        out.append(f'  -> {r["fix"]}')
    return "\n".join(out)


def main():
    p = argparse.ArgumentParser(prog="shellport", description="Shell command portability analyzer")
    p.add_argument("command", choices=["scan"])
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("--target", default="linux,macos,alpine")
    p.add_argument("--format", choices=["text", "json"], default="text", dest="fmt")
    args = p.parse_args()
    targets = set(args.target.split(","))
    invalid = targets - PLATFORMS
    if invalid:
        sys.exit(f"Unknown platforms: {invalid}. Valid: {sorted(PLATFORMS)}")
    results = scan(args.path, targets)
    print(json.dumps(results, indent=2) if args.fmt == "json" else format_text(results))
    sys.exit(1 if results else 0)


if __name__ == "__main__":
    main()
