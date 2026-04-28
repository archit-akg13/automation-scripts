# automation-scripts

Collection of Python automation scripts — file organizer, PDF merger, email sender, web scraper, and more. Built for productivity.

## Scripts

| Script | Description |
|--------|-------------|
| `file_organizer.py` | Sort files into folders by extension with dry-run mode |
| `pdf_merger.py` | Merge and split PDFs with page range selection |
| `csv_data_cleaner.py` | Deduplicate, fill nulls, and normalize CSV data |
| `cron_scheduler.py` | Decorator-based task scheduler with cron expressions |
| `json_config_manager.py` | Manage JSON configs with dot-notation access and validation |
| `log_rotator.py` | Compress, archive, and rotate log files by size or age |
| `system_monitor.py` | Lightweight resource tracker with disk alerts and JSON output |
| `env_loader.py` | Dependency-free .env loader with type coercion and interpolation |

## Quick Start

```bash
git clone https://github.com/archit-akg13/automation-scripts.git
cd automation-scripts

# Run any script directly
python file_organizer.py --source ~/Downloads --dry-run
python system_monitor.py --json --alert 80
python csv_data_cleaner.py input.csv --output cleaned.csv
```

## Requirements

- Python 3.10+
- - No external dependencies (stdlib only)
 
  - ## License
 
  - MIT

## Roadmap

The next batch of scripts to land in this repo:

| Planned Script | Purpose |
|----------------|---------|
| `directory_diff.py` | Compare two directory trees by content hash and report drift |
| `env_validator.py` | Validate `.env` files against a declared schema with type checks |
| `bulk_renamer.py` | Pattern-based bulk file renaming with regex and dry-run preview |
| `secret_scanner.py` | Scan a repo or directory for committed credentials and API keys |
| `webhook_relay.py` | Lightweight HTTP relay that fans webhooks out to multiple targets |

## Design Principles

Every script in this repo follows a few rules so they stay easy to drop into any project:

1. **Stdlib only** — no `pip install` required for any script. If a script needs a third-party library, it ships in its own subdirectory with a local `requirements.txt`.
2. **CLI-first** — every script is runnable with `python script.py --help` and prints a real argparse usage string.
3. **Dry-run by default for destructive ops** — anything that moves, deletes, or rewrites files defaults to a preview unless `--apply` (or equivalent) is passed.
4. **Exit codes that mean something** — `0` for success, `1` for "ran but found issues", `2` for usage / setup errors. Pipeable.
5. **JSON output mode** — scripts that produce reports support `--json` so they compose with `jq`, log shippers, and other automation.

## Contributing

Pull requests welcome. Before submitting:

- Keep the script self-contained in a single `.py` file (or a small subdirectory if it needs assets).
- Add a row to the `## Scripts` table in this README.
- Include a module docstring with usage examples and exit codes.
- Run `python -m py_compile your_script.py` to confirm it parses cleanly.

## Status

![License](https://img.shields.io/github/license/archit-akg13/automation-scripts)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Last Commit](https://img.shields.io/github/last-commit/archit-akg13/automation-scripts)
![Repo Size](https://img.shields.io/github/repo-size/archit-akg13/automation-scripts)

## Why this repo exists

Most automation problems aren't novel — they're variations on patterns you've solved before but lost the code for. This repo is a stable home for those patterns. Each script is intentionally boring: stdlib only, one file, predictable CLI, exit codes you can branch on. The goal is that six months from now you can clone the repo, find the right script in 15 seconds, and run it without reading a tutorial.
