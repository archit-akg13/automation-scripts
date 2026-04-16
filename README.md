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
