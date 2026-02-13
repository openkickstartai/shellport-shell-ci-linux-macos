"""Compatibility database: command flags across GNU / BSD / busybox."""

PLATFORMS = {"linux", "macos", "alpine"}

FLAG_COMPAT = {
    "sed": {
        "-i": {"linux", "alpine"},
        "-r": {"linux", "alpine"},
        "-E": {"linux", "macos", "alpine"},
    },
    "grep": {
        "-P": {"linux"},
        "-E": {"linux", "macos", "alpine"},
        "-o": {"linux", "macos", "alpine"},
        "-r": {"linux", "macos"},
        "-R": {"linux", "macos", "alpine"},
        "-w": {"linux", "macos", "alpine"},
    },
    "readlink": {
        "-f": {"linux", "alpine"},
        "-e": {"linux", "alpine"},
    },
    "date": {
        "-d": {"linux", "alpine"},
        "-j": {"macos"},
        "-I": {"linux", "alpine"},
    },
    "mktemp": {
        "-d": {"linux", "macos", "alpine"},
        "--tmpdir": {"linux", "alpine"},
    },
    "stat": {
        "-c": {"linux", "alpine"},
        "-f": {"macos"},
    },
    "find": {
        "-regextype": {"linux", "alpine"},
        "-maxdepth": {"linux", "macos", "alpine"},
        "-print0": {"linux", "macos", "alpine"},
    },
    "sort": {
        "-V": {"linux", "alpine"},
        "-h": {"linux", "alpine"},
        "-R": {"linux"},
    },
    "tar": {
        "--wildcards": {"linux", "alpine"},
        "--exclude": {"linux", "macos", "alpine"},
    },
    "xargs": {
        "-r": {"linux", "alpine"},
        "-0": {"linux", "macos", "alpine"},
    },
    "cp": {
        "--reflink": {"linux"},
        "-a": {"linux", "macos", "alpine"},
    },
    "ln": {
        "-r": {"linux", "alpine"},
    },
    "install": {
        "-D": {"linux", "alpine"},
    },
}

FIXES = {
    ("sed", "-i"): "sed -i.bak 's/.../' f && rm f.bak  (portable across GNU & BSD)",
    ("sed", "-r"): "Use sed -E instead (portable extended regex)",
    ("grep", "-P"): "Use grep -E (ERE) or install ripgrep for PCRE",
    ("readlink", "-f"): "Use: cd $(dirname $0) && pwd -P  (POSIX alternative)",
    ("readlink", "-e"): "Use: cd $(dirname $0) && pwd -P  (POSIX alternative)",
    ("date", "-d"): "Use python3/perl for portable date arithmetic",
    ("date", "-j"): "Use python3/perl for portable date arithmetic",
    ("date", "-I"): "Use: date '+%Y-%m-%d'  (POSIX format string)",
    ("stat", "-c"): "Write a wrapper: stat -c on Linux, stat -f on macOS",
    ("stat", "-f"): "Write a wrapper: stat -c on Linux, stat -f on macOS",
    ("sort", "-V"): "Use sort -t. -k1,1n -k2,2n for version-like sorting",
    ("sort", "-R"): "Use: awk 'BEGIN{srand()}{print rand(),$0}' | sort -n | cut -d' ' -f2-",
    ("xargs", "-r"): "Guard with: if [ -n \"$input\" ]; then ... fi",
    ("cp", "--reflink"): "Use plain cp -a (loses reflink optimization)",
    ("ln", "-r"): "Compute relative path manually with realpath",
    ("install", "-D"): "mkdir -p $(dirname dest) && cp src dest",
    ("find", "-regextype"): "Use -name with glob patterns instead",
    ("tar", "--wildcards"): "Omit --wildcards (default on BSD tar)",
}
