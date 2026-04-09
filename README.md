# AI Sentinel — Diagnostic Suite

Companion toolset for [AI Sentinel Pro](https://github.com/punksm4ck/ai-content-detector-sentinel). Three diagnostic tools unified in one script.

## Tools

| Command | Description |
|---|---|
| `sentinel-diag live` | Qt GUI — downloads test image, oscillates it to trigger the watcher, logs results live |
| `sentinel-diag report` | Headless health report — config, API auth, watcher process, snapshot archive, detection DB |
| `sentinel-diag batch` | Batch scan a directory, quarantine AI-detected images, generate JSON telemetry |
| `sentinel-diag all` | Run report then open live GUI |

## Install

```bash
git clone https://github.com/punksm4ck/ai-sentinel-diagnostics.git
cd ai-sentinel-diagnostics
pip install -r requirements.txt
```

## Usage

```bash
# Live motion emulator — keep window visible, watcher should badge within 3–5s
python sentinel_diagnostics.py live

# Full system health report
python sentinel_diagnostics.py report

# Batch scan ~/Pictures, quarantine anything above 80% confidence
python sentinel_diagnostics.py batch --source ~/Pictures --threshold 0.80

# Dry run — shows what would be quarantined without moving files
python sentinel_diagnostics.py batch --source ~/Pictures --dry-run

# Report + GUI
python sentinel_diagnostics.py all
```

## Config

Automatically reads credentials from the AI Sentinel config. Searches these locations in order:

1. `~/.config/ai_sentinel_pro/config.json`
2. `~/.config/ai_sentinel/config.json`
3. `~/.config/ai_watcher_enterprise.json`
4. `~/.config/ai_sentinel.json`

No separate config needed.

## Reports

- Health reports: `~/Scripts/sentinel_reports/health_report_YYYYMMDD_HHMMSS.txt`
- Batch reports: `~/Scripts/sentinel_reports/batch_report_YYYYMMDD_HHMMSS.json`
- Quarantine dir: `~/.config/ai_sentinel_pro/quarantine/`

## Requirements

- Python 3.9+
- PyQt5 (live mode only)
- requests

## Related

- [ai-content-detector-sentinel](https://github.com/punksm4ck/ai-content-detector-sentinel) — main watcher
