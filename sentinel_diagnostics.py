"© 2026 Punksm4ck. All rights reserved."
"© 2026 Punksm4ck. All rights reserved."
#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  AI SENTINEL PRO  ·  Diagnostic & Validation Suite  v1.0.0                  ║
║                                                                              ║
║  Three tools unified in one enterprise-grade CLI + GUI harness:             ║
║                                                                              ║
║  sentinel-diag live     — Qt GUI: live motion emulator + watcher trigger     ║
║  sentinel-diag report   — Headless: full system health report                ║
║  sentinel-diag batch    — Batch scanner: scan directory, quarantine AI       ║
║  sentinel-diag all      — Run report then open live GUI                      ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

# ─── Standard Library ────────────────────────────────────────────────────────
import sys, os, json, time, shutil, argparse, subprocess, datetime
import concurrent.futures, threading, logging, hashlib, uuid, traceback
from pathlib import Path
from typing import Optional, List, Dict, Tuple

# ─── Third-party ─────────────────────────────────────────────────────────────
import requests

# ══════════════════════════════════════════════════════════════════════════════
#  PATHS & CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════
APP_NAME    = "AI Sentinel Diagnostics"
APP_VERSION = "1.0.0"

# Config file locations — searched in order, first hit wins
CONFIG_SEARCH_PATHS = [
    Path.home() / ".config" / "ai_sentinel_pro"  / "config.json",
    Path.home() / ".config" / "ai_sentinel"       / "config.json",
    Path.home() / ".config" / "ai_watcher_enterprise.json",
    Path.home() / ".config" / "ai_sentinel.json",
]

QUARANTINE_DIR = Path.home() / ".config" / "ai_sentinel_pro" / "quarantine"
REPORTS_DIR    = Path.home() / "Scripts" / "sentinel_reports"
API_URL        = "https://api.sightengine.com/1.0/check.json"
MAX_BATCH_THREADS = 2

# Test image — publicly available example known to score high on genai
TEST_IMAGE_URL  = "https://sightengine.com/assets/img/examples/example-prop-c1.jpg"
TEST_IMAGE_ALT  = "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3f/JPEG_example_flower.jpg/640px-JPEG_example_flower.jpg"

# Watcher process patterns
WATCHER_SCRIPT_PATTERNS = [
    "ai_sentinel.py", "ai_sentinel_pro.py", "ai_watcher_enterprise.py",
    "ai_watcher_enterprise_v5.py",
]
WATCHER_SCRIPT_PATHS = [
    Path.home() / "Scripts" / "AIContentDetector" / "ai_sentinel.py",
    Path.home() / "Scripts" / "ai_sentinel.py",
    Path.home() / "Scripts" / "ai_watcher_enterprise.py",
    Path.home() / "Scripts" / "ai_watcher_enterprise_v5.py",
]

# ══════════════════════════════════════════════════════════════════════════════
#  LOGGING
# ══════════════════════════════════════════════════════════════════════════════
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
_log_path = REPORTS_DIR / "diagnostics.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(_log_path, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger("sentinel.diag")

# ══════════════════════════════════════════════════════════════════════════════
#  CONFIG LOADER
# ══════════════════════════════════════════════════════════════════════════════
def find_config() -> Tuple[Optional[Path], dict]:
    """Search known locations for sentinel config. Returns (path, data)."""
    for p in CONFIG_SEARCH_PATHS:
        if p.exists():
            try:
                data = json.loads(p.read_text())
                log.info(f"Config found: {p}")
                return p, data
            except Exception as e:
                log.warning(f"Config at {p} unreadable: {e}")
    return None, {}

# ══════════════════════════════════════════════════════════════════════════════
#  WATCHER PROCESS UTILS
# ══════════════════════════════════════════════════════════════════════════════
def find_watcher_processes() -> List[dict]:
    """Return list of dicts with pid/cmd for running watcher processes."""
    found = []
    try:
        out = subprocess.check_output(["ps", "aux"], text=True, timeout=5)
        for line in out.splitlines():
            if "python" not in line.lower():
                continue
            if any(pat in line for pat in WATCHER_SCRIPT_PATTERNS):
                # Skip this script itself
                if "sentinel_diagnostics" in line or "auto_diagnostic" in line:
                    continue
                parts = line.split()
                found.append({
                    "pid": parts[1],
                    "cmd": " ".join(parts[10:])[:80],
                    "user": parts[0],
                    "cpu": parts[2],
                    "mem": parts[3],
                })
    except Exception as e:
        log.warning(f"Process scan failed: {e}")
    return found

def find_watcher_script() -> Optional[Path]:
    """Locate the best available watcher script."""
    for p in WATCHER_SCRIPT_PATHS:
        if p.exists():
            return p
    return None

def launch_watcher(script: Path) -> Optional[int]:
    """Launch watcher as a detached background process. Returns PID or None."""
    try:
        proc = subprocess.Popen(
            [sys.executable, str(script)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        time.sleep(2)
        log.info(f"Watcher launched: PID {proc.pid}  script={script}")
        return proc.pid
    except Exception as e:
        log.error(f"Watcher launch failed: {e}")
        return None

# ══════════════════════════════════════════════════════════════════════════════
#  SIGHTENGINE API
# ══════════════════════════════════════════════════════════════════════════════
def api_check_url(url: str, api_user: str, api_secret: str,
                  timeout: int = 12) -> dict:
    """Check a remote URL via Sightengine genai model."""
    r = requests.get(API_URL, params={
        "models": "genai",
        "api_user": api_user,
        "api_secret": api_secret,
        "url": url,
    }, timeout=timeout)
    return r.json()

def api_check_file(file_path: str, api_user: str, api_secret: str,
                   timeout: int = 14) -> dict:
    """Check a local file via Sightengine genai model."""
    with open(file_path, "rb") as f:
        r = requests.post(API_URL, files={
            "media": (os.path.basename(file_path), f, "image/jpeg")
        }, data={
            "models": "genai",
            "api_user": api_user,
            "api_secret": api_secret,
        }, timeout=timeout)
    return r.json()

# ══════════════════════════════════════════════════════════════════════════════
#  TOOL 2: HEADLESS SYSTEM REPORT
# ══════════════════════════════════════════════════════════════════════════════
class SystemReporter:
    """
    Generates a comprehensive plain-text + JSON health report.
    Checks: config, credentials, API auth, watcher process, snapshots.
    Auto-recovers missing watcher process if script is locatable.
    """

    def __init__(self):
        self.ts        = datetime.datetime.now()
        self.lines     = []
        self.sections  = {}
        self.api_user  = ""
        self.api_secret= ""
        self.config_path = None
        self.config_data = {}

    def _h(self, title: str):
        self.lines.append("")
        self.lines.append("=" * 80)
        self.lines.append(f"  {title}")
        self.lines.append("=" * 80)

    def _pass(self, detail: str):
        self.lines.append(f"  STATUS  : PASS")
        self.lines.append(f"  DETAIL  : {detail}")

    def _fail(self, detail: str):
        self.lines.append(f"  STATUS  : FAIL")
        self.lines.append(f"  DETAIL  : {detail}")

    def _warn(self, detail: str):
        self.lines.append(f"  STATUS  : WARN")
        self.lines.append(f"  DETAIL  : {detail}")

    def _skip(self, detail: str):
        self.lines.append(f"  STATUS  : SKIP")
        self.lines.append(f"  DETAIL  : {detail}")

    def _info(self, key: str, val: str):
        self.lines.append(f"  {key:<16}: {val}")

    def run(self) -> Path:
        self._banner()
        self._check_config()
        self._check_api()
        self._check_process()
        self._check_snapshots()
        self._check_db()
        self._footer()
        return self._save()

    def _banner(self):
        self.lines += [
            "=" * 80,
            "        AI SENTINEL PRO  —  SYSTEM HEALTH REPORT",
            "=" * 80,
            f"  TIMESTAMP  : {self.ts.strftime('%Y-%m-%d %H:%M:%S')}",
            f"  HOST       : {os.uname().nodename}  ({os.uname().sysname} {os.uname().release})",
            f"  USER       : {os.environ.get('USER', os.environ.get('USERNAME', '?'))}",
            f"  PYTHON     : {sys.version.split()[0]}",
            f"  REPORT_VER : {APP_VERSION}",
        ]

    def _check_config(self):
        self._h("[1]  CONFIGURATION PAYLOAD")
        self.config_path, self.config_data = find_config()
        if not self.config_path:
            self._fail("No config file found. Run AI Sentinel and configure API credentials.")
            return
        self._info("CONFIG_FILE", str(self.config_path))
        self.api_user   = self.config_data.get("api_user",   "")
        self.api_secret = self.config_data.get("api_secret", "")
        # Handle encrypted secret fallback
        if not self.api_secret and self.config_data.get("api_secret_enc"):
            self._info("NOTE", "API secret is encrypted; raw value unavailable from report tool.")
        threshold = self.config_data.get("threshold", "?")
        monitor   = self.config_data.get("monitor_index", "?")
        self._info("API_USER",    self.api_user if self.api_user else "— not set —")
        self._info("THRESHOLD",   str(threshold))
        self._info("MONITOR_IDX", str(monitor))
        if self.api_user and (self.api_secret or self.config_data.get("api_secret_enc")):
            self._pass("Config loaded. Credentials present (secret may be encrypted).")
        else:
            self._fail("API credentials missing from config payload.")

    def _check_api(self):
        self._h("[2]  SIGHTENGINE API CONNECTIVITY")
        if not self.api_user or not self.api_secret:
            self._skip("Skipped — API credentials not available in plaintext.")
            return
        try:
            t0   = time.time()
            data = api_check_url(TEST_IMAGE_URL, self.api_user, self.api_secret)
            ms   = int((time.time() - t0) * 1000)
            if data.get("status") == "success":
                score = data.get("type", {}).get("ai_generated", 0)
                self._pass(
                    f"API authenticated. Test asset scored {score*100:.1f}% AI.  "
                    f"Latency: {ms}ms"
                )
                self._info("TEST_SCORE", f"{score*100:.1f}%")
                self._info("API_LATENCY",f"{ms} ms")
            else:
                msg = data.get("error", {}).get("message", "Unknown")
                self._fail(f"API error response: {msg}")
        except requests.Timeout:
            self._fail("Request timed out (>12s). Check network / firewall.")
        except requests.ConnectionError:
            self._fail("Connection refused or no network.")
        except Exception as e:
            self._fail(f"Unexpected error: {e}")

    def _check_process(self):
        self._h("[3]  WATCHER PROCESS STATUS")
        procs = find_watcher_processes()
        if procs:
            self._pass(f"{len(procs)} watcher process(es) active.")
            for p in procs:
                self.lines.append(
                    f"             PID {p['pid']}  CPU {p['cpu']}%  MEM {p['mem']}%"
                    f"  {p['cmd']}")
        else:
            self._warn("No watcher processes detected. Attempting auto-recovery.")
            script = find_watcher_script()
            if script:
                pid = launch_watcher(script)
                if pid:
                    self.lines.append(f"  STATUS  : RECOVERED")
                    self.lines.append(f"  DETAIL  : Launched {script.name}  PID={pid}")
                else:
                    self._fail(f"Launch attempt failed for {script}")
            else:
                self._fail(
                    "No watcher script found. Searched:\n" +
                    "\n".join(f"             {p}" for p in WATCHER_SCRIPT_PATHS)
                )

    def _check_snapshots(self):
        self._h("[4]  SNAPSHOT ARCHIVE")
        snap_dir = Path.home() / ".config" / "ai_sentinel_pro" / "snapshots"
        if not snap_dir.exists():
            self._info("NOTE", "Snapshot archive not created yet (snapshots may be disabled).")
            return
        snaps = list(snap_dir.glob("*.jpg")) + list(snap_dir.glob("*.png"))
        total_mb = sum(s.stat().st_size for s in snaps) / 1_048_576
        self._info("SNAP_COUNT", str(len(snaps)))
        self._info("SNAP_SIZE",  f"{total_mb:.1f} MB")
        if snaps:
            newest = max(snaps, key=lambda p: p.stat().st_mtime)
            age_s  = time.time() - newest.stat().st_mtime
            self._info("NEWEST",     f"{newest.name}  ({int(age_s)}s ago)")
            self._pass(f"{len(snaps)} snapshot(s) on disk.")
        else:
            self._info("NOTE", "No snapshots yet (watcher has not fired, or snapshots disabled).")

    def _check_db(self):
        self._h("[5]  DETECTION DATABASE")
        db_path = Path.home() / ".config" / "ai_sentinel_pro" / "detections.db"
        if not db_path.exists():
            self._info("NOTE", "Detection DB not found (watcher not yet run or log disabled).")
            return
        try:
            import sqlite3
            con  = sqlite3.connect(str(db_path))
            cur  = con.cursor()
            total = cur.execute("SELECT COUNT(*) FROM detections").fetchone()[0]
            ai    = cur.execute("SELECT COUNT(*) FROM detections WHERE is_ai=1").fetchone()[0]
            avg   = cur.execute("SELECT AVG(score) FROM detections WHERE is_ai=1").fetchone()[0] or 0
            con.close()
            self._info("TOTAL_RECORDS", str(total))
            self._info("AI_CONFIRMED",  str(ai))
            self._info("AVG_SCORE",     f"{avg*100:.1f}%")
            self._pass("Database accessible and queryable.")
        except Exception as e:
            self._fail(f"DB query failed: {e}")

    def _footer(self):
        self.lines += [
            "",
            "=" * 80,
            "  END OF REPORT",
            "=" * 80,
            "",
        ]

    def _save(self) -> Path:
        ts_str = self.ts.strftime("%Y%m%d_%H%M%S")
        txt_path = REPORTS_DIR / f"health_report_{ts_str}.txt"
        txt_path.write_text("\n".join(self.lines), encoding="utf-8")
        log.info(f"Report saved: {txt_path}")
        # Print to stdout
        print("\n".join(self.lines))
        return txt_path

# ══════════════════════════════════════════════════════════════════════════════
#  TOOL 3: BATCH SCANNER
# ══════════════════════════════════════════════════════════════════════════════
class BatchScanner:
    """
    Scans a directory of images against Sightengine genai model.
    Quarantines files above threshold. Generates JSON telemetry report.
    """

    VALID_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}

    def __init__(self, source_dir: str, threshold: Optional[float] = None,
                 dry_run: bool = False, max_threads: int = MAX_BATCH_THREADS):
        self.source_dir  = Path(source_dir).expanduser().resolve()
        self.dry_run     = dry_run
        self.max_threads = max_threads
        self.results: List[dict] = []
        self.api_user    = ""
        self.api_secret  = ""
        self.threshold   = threshold  # if None, read from config

        _, config = find_config()
        self.api_user   = config.get("api_user",   "")
        self.api_secret = config.get("api_secret", "")
        if self.threshold is None:
            raw = config.get("threshold", 40)
            # Config stores threshold as 0-1 float or 0-100 int
            self.threshold = raw if raw <= 1.0 else raw / 100.0

        if not self.api_user or not self.api_secret:
            log.error("Sightengine API credentials missing from configuration.")
            sys.exit(1)

        QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)

    def _collect_files(self) -> List[Path]:
        if not self.source_dir.exists():
            log.error(f"Source directory not found: {self.source_dir}")
            sys.exit(1)
        return [
            p for p in self.source_dir.iterdir()
            if p.is_file() and p.suffix.lower() in self.VALID_EXT
        ]

    def _scan_one(self, path: Path) -> dict:
        try:
            t0   = time.time()
            data = api_check_file(str(path), self.api_user, self.api_secret)
            ms   = int((time.time() - t0) * 1000)
            if data.get("status") == "success":
                score = data.get("type", {}).get("ai_generated", 0.0)
                result = {
                    "file":        str(path),
                    "filename":    path.name,
                    "status":      "success",
                    "score":       round(score, 4),
                    "score_pct":   round(score * 100, 1),
                    "latency_ms":  ms,
                    "quarantined": False,
                }
                if score >= self.threshold:
                    if not self.dry_run:
                        dest = QUARANTINE_DIR / path.name
                        # Avoid collisions
                        if dest.exists():
                            dest = QUARANTINE_DIR / f"{path.stem}_{uuid.uuid4().hex[:6]}{path.suffix}"
                        shutil.move(str(path), str(dest))
                        result["quarantined"] = True
                        result["quarantine_path"] = str(dest)
                    else:
                        result["quarantined"]      = False
                        result["would_quarantine"] = True
                return result
            else:
                msg = data.get("error", {}).get("message", "Unknown API error")
                return {"file": str(path), "filename": path.name,
                        "status": "api_error", "error": msg}
        except Exception as e:
            return {"file": str(path), "filename": path.name,
                    "status": "exception", "error": str(e)}

    def run(self):
        files = self._collect_files()
        total = len(files)
        if total == 0:
            log.warning(f"No image files found in {self.source_dir}")
            return

        mode = "[DRY RUN] " if self.dry_run else ""
        log.info(
            f"{mode}Batch scan starting | "
            f"files={total}  threshold={self.threshold*100:.0f}%  "
            f"threads={self.max_threads}  source={self.source_dir}"
        )

        try:
            os.nice(15)
        except AttributeError:
            pass

        t_start  = time.time()
        done     = 0
        lock     = threading.Lock()

        def process(path: Path):
            nonlocal done
            result = self._scan_one(path)
            with lock:
                self.results.append(result)
                done += 1
                if done % 5 == 0 or done == total:
                    pct = done / total * 100
                    q   = sum(1 for r in self.results if r.get("quarantined"))
                    log.info(f"  {pct:5.1f}%  {done}/{total}  quarantined={q}")
                # Rate-limit: pause every 25 to avoid burning API quota
                if done % 25 == 0:
                    time.sleep(2)

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_threads) as ex:
            list(ex.map(process, files))

        duration = time.time() - t_start
        self._report(duration)

    def _report(self, duration: float):
        ai_count  = sum(1 for r in self.results if r.get("quarantined") or r.get("would_quarantine"))
        err_count = sum(1 for r in self.results if r["status"] != "success")
        avg_score = (
            sum(r["score"] for r in self.results if r["status"] == "success") /
            max(1, sum(1 for r in self.results if r["status"] == "success"))
        )

        report = {
            "meta": {
                "tool":        APP_NAME,
                "version":     APP_VERSION,
                "timestamp":   datetime.datetime.now().isoformat(),
                "dry_run":     self.dry_run,
                "source_dir":  str(self.source_dir),
                "threshold":   self.threshold,
            },
            "telemetry": {
                "execution_time_seconds":    round(duration, 2),
                "total_assets_scanned":      len(self.results),
                "ai_detections":             ai_count,
                "errors":                    err_count,
                "average_score":             round(avg_score, 4),
            },
            "results": self.results,
        }

        ts_str      = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = REPORTS_DIR / f"batch_report_{ts_str}.json"
        report_path.write_text(json.dumps(report, indent=2))

        print("\n" + "=" * 72)
        print(f"  BATCH SCAN COMPLETE")
        print(f"  Duration    : {duration:.1f}s")
        print(f"  Scanned     : {len(self.results)}")
        print(f"  AI detected : {ai_count}  {'(dry run — not moved)' if self.dry_run else '(quarantined)'}")
        print(f"  Errors      : {err_count}")
        print(f"  Avg score   : {avg_score*100:.1f}%")
        print(f"  Report      : {report_path}")
        print("=" * 72)
        log.info(f"Batch report saved: {report_path}")

# ══════════════════════════════════════════════════════════════════════════════
#  TOOL 1: LIVE MOTION EMULATOR GUI
# ══════════════════════════════════════════════════════════════════════════════
def run_live_gui():
    """Launch the Qt diagnostic GUI."""
    try:
        from PyQt5.QtWidgets import (
            QApplication, QMainWindow, QWidget, QLabel,
            QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
            QSplitter, QFrame, QProgressBar, QSizePolicy,
        )
        from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QSize
        from PyQt5.QtGui import QPixmap, QFont, QColor, QPalette, QIcon
    except ImportError:
        log.error("PyQt5 not installed. Run: pip install PyQt5")
        sys.exit(1)

    # ── Design tokens ────────────────────────────────────────────────────────
    BG0      = "#060610"
    BG1      = "#0d0d1f"
    BG2      = "#12122a"
    SURFACE  = "#16163a"
    BORDER   = "#1e1e40"
    TEXT     = "#c8d4f0"
    TEXT2    = "#6070a8"
    ACCENT   = "#5b6aff"
    OK       = "#00e08a"
    WARN     = "#ffa830"
    DANGER   = "#ff2060"
    INFO     = "#00c8f0"
    MONO     = "'JetBrains Mono', 'Cascadia Code', 'Fira Code', 'Consolas', monospace"

    STYLE = f"""
    QMainWindow, QWidget {{
        background: {BG0};
        color: {TEXT};
        font-family: {MONO};
        font-size: 12px;
    }}
    QTextEdit {{
        background: {BG1};
        color: {OK};
        border: 1px solid {BORDER};
        border-radius: 4px;
        padding: 10px;
        font-family: {MONO};
        font-size: 12px;
        selection-background-color: {ACCENT};
    }}
    QPushButton {{
        background: {ACCENT};
        color: #ffffff;
        border: none;
        border-radius: 6px;
        padding: 11px 24px;
        font-weight: bold;
        font-size: 13px;
        letter-spacing: 0.5px;
    }}
    QPushButton:hover  {{ background: #7c88ff; }}
    QPushButton:pressed {{ background: #3a47cc; }}
    QPushButton:disabled {{ background: #2a2a50; color: #4a5280; }}
    QProgressBar {{
        background: {BG2};
        border: 1px solid {BORDER};
        border-radius: 4px;
        text-align: center;
        color: {TEXT};
        font-size: 10px;
        max-height: 12px;
    }}
    QProgressBar::chunk {{
        background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
            stop:0 {ACCENT}, stop:1 #7c88ff);
        border-radius: 3px;
    }}
    QLabel {{ color: {TEXT}; background: transparent; }}
    QSplitter::handle {{ background: {BORDER}; }}
    QFrame[frameShape="4"] {{ color: {BORDER}; }}
    """

    # ── API worker ────────────────────────────────────────────────────────────
    class APICheckWorker(QThread):
        result = pyqtSignal(dict)
        error  = pyqtSignal(str)

        def __init__(self, url, api_user, api_secret):
            super().__init__()
            self.url        = url
            self.api_user   = api_user
            self.api_secret = api_secret

        def run(self):
            try:
                data = api_check_url(self.url, self.api_user, self.api_secret)
                self.result.emit(data)
            except Exception as e:
                self.error.emit(str(e))

    # ── Image download worker ─────────────────────────────────────────────────
    class ImageFetchWorker(QThread):
        done  = pyqtSignal(bytes)
        error = pyqtSignal(str)

        def __init__(self, url):
            super().__init__()
            self.url = url

        def run(self):
            for attempt, url in enumerate([self.url, TEST_IMAGE_ALT]):
                try:
                    r = requests.get(url, timeout=12)
                    if r.status_code == 200 and r.content:
                        self.done.emit(r.content)
                        return
                except Exception:
                    pass
            self.error.emit("All image sources failed.")

    # ── Main window ───────────────────────────────────────────────────────────
    class DiagWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle(f"AI Sentinel — Live Diagnostic Emulator  v{APP_VERSION}")
            self.setMinimumSize(1020, 620)
            self.setStyleSheet(STYLE)

            self._api_user   = ""
            self._api_secret = ""
            self._pixmap     = None
            self._shift      = False
            self._api_worker = None
            self._img_worker = None
            self._oscillating= False

            self._build_ui()
            self._load_config()

        def _build_ui(self):
            root = QWidget()
            self.setCentralWidget(root)
            outer = QHBoxLayout(root)
            outer.setContentsMargins(18, 18, 18, 18)
            outer.setSpacing(16)

            # ── Left: log console ─────────────────────────────────────────
            left = QWidget()
            lv   = QVBoxLayout(left)
            lv.setContentsMargins(0, 0, 0, 0)
            lv.setSpacing(10)

            hdr = QLabel("◈  DIAGNOSTIC CONSOLE")
            hdr.setStyleSheet(
                f"color:{TEXT2}; font-size:10px; letter-spacing:2px; font-weight:bold;")
            lv.addWidget(hdr)

            self._log = QTextEdit()
            self._log.setReadOnly(True)
            lv.addWidget(self._log, 1)

            self._progress = QProgressBar()
            self._progress.setRange(0, 0)  # indeterminate
            self._progress.setVisible(False)
            lv.addWidget(self._progress)

            self._btn = QPushButton("⚡  EXECUTE DIAGNOSTICS")
            self._btn.clicked.connect(self._run)
            lv.addWidget(self._btn)

            # ── Right: image panel ────────────────────────────────────────
            right = QWidget()
            right.setFixedWidth(380)
            rv = QVBoxLayout(right)
            rv.setContentsMargins(0, 0, 0, 0)
            rv.setSpacing(10)

            hdr2 = QLabel("◈  MOTION EMULATION TARGET")
            hdr2.setStyleSheet(
                f"color:{TEXT2}; font-size:10px; letter-spacing:2px; font-weight:bold;")
            rv.addWidget(hdr2)

            self._img_label = QLabel()
            self._img_label.setFixedSize(360, 360)
            self._img_label.setAlignment(Qt.AlignCenter)
            self._img_label.setStyleSheet(
                f"border: 2px dashed {BORDER}; background: {BG1}; "
                f"color: {TEXT2}; font-size: 11px;")
            self._img_label.setText("Awaiting asset download…")
            self._img_label.setWordWrap(True)
            rv.addWidget(self._img_label)

            self._score_label = QLabel()
            self._score_label.setAlignment(Qt.AlignCenter)
            self._score_label.setStyleSheet(f"color:{TEXT2}; font-size:11px;")
            rv.addWidget(self._score_label)

            rv.addStretch()

            # Status bar indicators
            self._status_row = QHBoxLayout()
            for attr, label, color in [
                ("_ind_config",  "CONFIG",  INFO),
                ("_ind_api",     "API",     INFO),
                ("_ind_watcher", "WATCHER", INFO),
            ]:
                lbl = QLabel(f"● {label}")
                lbl.setStyleSheet(f"color:{TEXT2}; font-size:10px;")
                self._status_row.addWidget(lbl)
                setattr(self, attr, lbl)
            rv.addLayout(self._status_row)

            # Oscillator
            self._osc = QTimer(self)
            self._osc.timeout.connect(self._oscillate)

            splitter = QSplitter(Qt.Horizontal)
            splitter.addWidget(left)
            splitter.addWidget(right)
            splitter.setStretchFactor(0, 2)
            splitter.setStretchFactor(1, 1)
            outer.addWidget(splitter)

        def _set_indicator(self, attr: str, state: str):
            """state: ok | fail | warn | idle"""
            colors = {"ok": OK, "fail": DANGER, "warn": WARN, "idle": TEXT2}
            lbl = getattr(self, attr, None)
            if lbl:
                color = colors.get(state, TEXT2)
                text  = lbl.text().split(" ", 1)[-1]
                lbl.setStyleSheet(f"color:{color}; font-size:10px;")

        def _log_msg(self, msg: str, color: str = TEXT):
            ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
            self._log.append(
                f'<span style="color:{TEXT2};">[{ts}]</span> '
                f'<span style="color:{color};">{msg}</span>'
            )
            from PyQt5.QtWidgets import QApplication
            QApplication.processEvents()

        def _load_config(self):
            self._log_msg("Loading sentinel configuration…", INFO)
            path, data = find_config()
            if not path:
                self._log_msg(
                    "FAIL: No config file found. Run AI Sentinel first.", DANGER)
                self._set_indicator("_ind_config", "fail")
                self._btn.setEnabled(False)
                return
            self._api_user   = data.get("api_user",   "")
            self._api_secret = data.get("api_secret", "")
            if not self._api_user or not self._api_secret:
                self._log_msg(
                    f"WARN: Credentials not in plaintext (may be encrypted). "
                    f"Config: {path}", WARN)
                self._set_indicator("_ind_config", "warn")
            else:
                self._log_msg(f"PASS: Config loaded — {path}", OK)
                self._set_indicator("_ind_config", "ok")

        def _run(self):
            self._log.clear()
            self._btn.setEnabled(False)
            self._progress.setVisible(True)
            self._osc.stop()
            self._score_label.clear()
            self._log_msg("INITIATING DIAGNOSTIC SEQUENCE…", ACCENT)

            # Step 1: check watcher
            procs = find_watcher_processes()
            if procs:
                self._log_msg(
                    f"PASS: {len(procs)} watcher process(es) active.", OK)
                self._set_indicator("_ind_watcher", "ok")
            else:
                self._log_msg(
                    "WARN: No watcher running. Attempting auto-recovery…", WARN)
                script = find_watcher_script()
                if script:
                    pid = launch_watcher(script)
                    if pid:
                        self._log_msg(
                            f"RECOVERED: Watcher launched — PID {pid}", OK)
                        self._set_indicator("_ind_watcher", "ok")
                    else:
                        self._log_msg("FAIL: Could not launch watcher.", DANGER)
                        self._set_indicator("_ind_watcher", "fail")
                else:
                    self._log_msg("FAIL: Watcher script not found.", DANGER)
                    self._set_indicator("_ind_watcher", "fail")

            # Step 2: API auth check
            if not self._api_user or not self._api_secret:
                self._log_msg(
                    "SKIP: API credentials not available (encrypted config). "
                    "Motion emulation will proceed without API validation.", WARN)
                self._set_indicator("_ind_api", "warn")
                self._fetch_image()
                return

            self._log_msg("Testing Sightengine API authentication…", INFO)
            self._api_worker = APICheckWorker(
                TEST_IMAGE_URL, self._api_user, self._api_secret)
            self._api_worker.result.connect(self._on_api_result)
            self._api_worker.error.connect(self._on_api_error)
            self._api_worker.start()

        def _on_api_result(self, data: dict):
            if data.get("status") == "success":
                score = data.get("type", {}).get("ai_generated", 0)
                self._log_msg(
                    f"PASS: API authenticated. Test asset → {score*100:.1f}% AI", OK)
                self._set_indicator("_ind_api", "ok")
                self._score_label.setText(
                    f"Test asset AI score: {score*100:.1f}%")
                color = DANGER if score > 0.8 else WARN if score > 0.5 else OK
                self._score_label.setStyleSheet(
                    f"color:{color}; font-size:13px; font-weight:bold;")
            else:
                msg = data.get("error", {}).get("message", "Unknown")
                self._log_msg(f"FAIL: API error — {msg}", DANGER)
                self._set_indicator("_ind_api", "fail")
            self._fetch_image()

        def _on_api_error(self, msg: str):
            self._log_msg(f"FAIL: API unreachable — {msg}", DANGER)
            self._set_indicator("_ind_api", "fail")
            self._fetch_image()

        def _fetch_image(self):
            self._log_msg("Downloading motion emulation asset…", INFO)
            self._img_worker = ImageFetchWorker(TEST_IMAGE_URL)
            self._img_worker.done.connect(self._on_image_ready)
            self._img_worker.error.connect(self._on_image_error)
            self._img_worker.start()

        def _on_image_ready(self, data: bytes):
            from PyQt5.QtGui import QPixmap
            pix = QPixmap()
            pix.loadFromData(data)
            self._pixmap = pix.scaled(
                350, 350, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self._img_label.setPixmap(self._pixmap)
            self._log_msg("PASS: Asset loaded into emulation matrix.", OK)
            self._start_oscillation()

        def _on_image_error(self, msg: str):
            self._log_msg(f"FAIL: Asset download failed — {msg}", DANGER)
            self._progress.setVisible(False)
            self._btn.setEnabled(True)

        def _start_oscillation(self):
            self._progress.setVisible(False)
            self._btn.setEnabled(True)
            self._oscillating = True
            self._log_msg("─" * 52, TEXT2)
            self._log_msg(
                "OSCILLATOR ACTIVE — Keep this window visible.", WARN)
            self._log_msg(
                "The background watcher should detect the moving image", TEXT)
            self._log_msg(
                "and deploy the AI badge within 3–5 seconds.", TEXT)
            self._log_msg("─" * 52, TEXT2)
            self._osc.start(700)

        def _oscillate(self):
            if not self._pixmap:
                return
            self._shift = not self._shift
            offset = 8 if self._shift else -8
            self._img_label.setContentsMargins(offset, offset, 0, 0)

        def closeEvent(self, event):
            self._osc.stop()
            if self._api_worker:
                self._api_worker.quit()
                self._api_worker.wait(1000)
            if self._img_worker:
                self._img_worker.quit()
                self._img_worker.wait(1000)
            super().closeEvent(event)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    win = DiagWindow()
    win.show()
    sys.exit(app.exec_())

# ══════════════════════════════════════════════════════════════════════════════
#  CLI ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(
        prog="sentinel-diag",
        description=f"AI Sentinel Diagnostic Suite v{APP_VERSION}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  live              Qt GUI — live motion emulator + watcher trigger test
  report            Headless health report (config, API, process, DB)
  batch             Batch-scan a directory, quarantine AI detections
  all               Run headless report then open live GUI

Examples:
  sentinel-diag live
  sentinel-diag report
  sentinel-diag batch --source ~/Pictures/downloads
  sentinel-diag batch --source ~/Pictures --threshold 0.75 --dry-run
        """
    )
    parser.add_argument("command", choices=["live", "report", "batch", "all"],
                        help="Diagnostic tool to run")
    parser.add_argument("-s", "--source",
                        default="~/.config/ai_sentinel_pro/snapshots",
                        help="[batch] Source directory to scan")
    parser.add_argument("-t", "--threshold", type=float, default=None,
                        help="[batch] AI score threshold 0.0–1.0 (default: from config)")
    parser.add_argument("--dry-run", action="store_true",
                        help="[batch] Simulate quarantine without moving files")
    parser.add_argument("--threads", type=int, default=MAX_BATCH_THREADS,
                        help=f"[batch] API worker threads (default: {MAX_BATCH_THREADS})")
    args = parser.parse_args()

    if args.command == "live":
        run_live_gui()

    elif args.command == "report":
        reporter = SystemReporter()
        path = reporter.run()
        print(f"\nReport saved: {path}")

    elif args.command == "batch":
        scanner = BatchScanner(
            source_dir=args.source,
            threshold=args.threshold,
            dry_run=args.dry_run,
            max_threads=args.threads,
        )
        scanner.run()

    elif args.command == "all":
        log.info("Running health report first…")
        reporter = SystemReporter()
        reporter.run()
        log.info("Opening live GUI…")
        run_live_gui()


if __name__ == "__main__":
    main()
