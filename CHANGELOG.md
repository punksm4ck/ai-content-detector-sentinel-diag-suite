# Changelog

## [1.0.0] — 2026-04-08

### Added
- `sentinel-diag live` — Qt GUI motion emulator (replaces `watcher_diagnostics.py`)
  - Downloads test image from Sightengine example assets
  - Oscillates image to trigger ContentWatcher motion detection
  - Validates API credentials and scores test asset in real time
  - Auto-detects and recovers missing watcher process
  - Live color-coded log console with timestamps
  - Status indicators: CONFIG / API / WATCHER
- `sentinel-diag report` — headless system health reporter (replaces `auto_diagnostic_reporter.py`)
  - Checks config across all known sentinel config paths
  - Validates API auth and reports latency + test asset score
  - Enumerates running watcher processes with PID/CPU/MEM
  - Auto-relaunches watcher if dead and script is locatable
  - Inspects snapshot archive and detection SQLite database
  - Saves timestamped `.txt` report to `~/Scripts/sentinel_reports/`
- `sentinel-diag batch` — batch directory scanner (replaces `safe_backend_processor.py`)
  - Scans arbitrary directory of images via Sightengine genai model
  - Quarantines AI-detected files with collision-safe naming
  - `--dry-run` flag: simulate without moving files
  - `--threshold` override: per-run confidence threshold
  - Rate-limiting: 2s pause every 25 files to protect API quota
  - Saves timestamped JSON telemetry report
- `sentinel-diag all` — runs report then opens live GUI
- Unified config discovery across all known sentinel config locations
- Structured logging to `~/Scripts/sentinel_reports/diagnostics.log`
