# ShellPort

Cross-platform shell command compatibility analyzer. Catches non-portable command flags **before** your CI breaks.

## Problem

macOS uses BSD coreutils, Linux uses GNU coreutils. Flags like `sed -i`, `grep -P`, `readlink -f` behave differently or don't exist across platforms. These bugs hide in shell scripts, Dockerfiles, Makefiles, and CI YAML until 2 AM.

## Usage

```bash
# Scan current directory for all platforms
python shellport.py scan .

# Scan with specific target platforms
python shellport.py scan --target linux,macos .

# JSON output for CI integration
python shellport.py scan --format json .
```

## Example Output

```
deploy.sh:12  ⚠️  `grep -P`  missing on: macos
  💡 Use grep -E (ERE) or install ripgrep for PCRE
Makefile:8    ⚠️  `sed -i`   missing on: macos
  💡 sed -i.bak 's/.../' f && rm f.bak  (works on both GNU & BSD)
```

## Supported File Types

| Type | Extraction |
|------|------------|
| `.sh` `.bash` `.zsh` | All lines |
| `Dockerfile` | `RUN` instructions |
| `Makefile` / `Justfile` | Tab-indented recipe lines |
| `.yml` / `.yaml` | `run:` block contents |

## Covered Commands

sed, grep, readlink, date, mktemp, stat, find, sort, tar, xargs, cp, ln, install — 40+ flags across GNU, BSD, and busybox.

## How It Differs From ShellCheck

ShellCheck focuses on shell **syntax** bugs. ShellPort focuses on **command-level cross-platform portability** — the flag compatibility gap between GNU, BSD, and busybox coreutils.

## Run Tests

```bash
pip install -r requirements.txt
pytest test_shellport.py -v
```

## License

MIT
