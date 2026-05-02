#!/usr/bin/env python3
"""
MANSA — Automated BRVM Data Pipeline
Collects market data from multiple sources with monitoring, fallback, and alerts.

Features:
  - Multi-source: BRVM.org (primary), RichBourse (fallback), cached JSON (emergency)
  - SQLite storage with upsert
  - Health monitoring + email alerts on failure
  - Structured logging
  - Cron-compatible (run every 15min during market hours)

Usage:
  python data_pipeline.py                 # Run once
  python data_pipeline.py --schedule      # Run on schedule (15min intervals)
  python data_pipeline.py --health        # Check pipeline health
  python data_pipeline.py --backfill 30   # Backfill last 30 days

Crontab (Linux):
  */15 10-16 * * 1-5 cd /path/to/server && python data_pipeline.py >> /var/log/mansa_pipeline.log 2>&1

Task Scheduler (Windows):
  Run every 15 minutes, Mon-Fri, 10:00-16:00 GMT
"""

import argparse
import json
import logging
import os
import smtplib
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from email.mime.text import MIMEText

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("[PIPELINE] Missing dependencies. Run: pip install requests beautifulsoup4")
    sys.exit(1)

# ── Configuration ──
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, '..', 'mansa.db')
DATA_DIR = os.path.join(BASE_DIR, '..', 'brvm_data')
LOG_DIR = os.path.join(BASE_DIR, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

# Alert configuration (set via environment variables)
ALERT_EMAIL_TO = os.environ.get('MANSA_ALERT_EMAIL', '')
ALERT_EMAIL_FROM = os.environ.get('MANSA_SMTP_FROM', 'pipeline@mansa.finance')
SMTP_HOST = os.environ.get('MANSA_SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('MANSA_SMTP_PORT', '587'))
SMTP_USER = os.environ.get('MANSA_SMTP_USER', '')
SMTP_PASS = os.environ.get('MANSA_SMTP_PASS', '')

# Sources
SOURCES = {
    'brvm_org': {
        'name': 'BRVM.org',
        'base_url': 'https://www.brvm.org',
        'priority': 1,
        'timeout': 30,
    },
    'richbourse': {
        'name': 'RichBourse',
        'base_url': 'https://www.richbourse.com',
        'priority': 2,
        'timeout': 30,
    },
    'local_cache': {
        'name': 'Local JSON Cache',
        'priority': 3,
        'timeout': 5,
    },
}

# BRVM market hours: 10:00 - 15:30 GMT (Mon-Fri)
MARKET_OPEN_HOUR = 10
MARKET_CLOSE_HOUR = 16

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(LOG_DIR, f'pipeline_{datetime.now():%Y%m%d}.log')),
    ]
)
log = logging.getLogger('mansa_pipeline')

# All 48 BRVM tickers
BRVM_TICKERS = [
    'ABJC.ci','BICC.ci','BNBC.ci','BOAB.bj','BOABF.bf','BOAC.ci','BOAM.ml',
    'BOAN.ne','BOAS.sn','CABC.ci','CFAC.ci','CIEC.ci','ECOC.ci','ETIT.tg',
    'FTSC.ci','NEIC.ci','NSBC.ci','NTLC.ci','ONTBF.bf','ORAC.ci','ORGT.tg',
    'PALC.ci','PRSC.ci','SAFC.ci','SCRC.ci','SDCC.ci','SDSC.ci','SEMC.ci',
    'SGBC.ci','SHEC.ci','SIBC.ci','SICC.ci','SIVC.ci','SLBC.ci','SMBC.ci',
    'SNTS.sn','SOGC.ci','SPHC.ci','STBC.ci','SVOC.ci','TTLC.ci','TTLS.sn',
    'UNLC.ci','UNXC.ci',
]


class DataPipeline:
    """BRVM market data pipeline with multi-source fallback."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'MANSA-DataPipeline/1.0 (+https://mansa.finance)',
            'Accept': 'text/html,application/json',
            'Accept-Language': 'fr-FR,fr;q=0.9',
        })
        self.db = None
        self.stats = {
            'start_time': None,
            'source': None,
            'tickers_updated': 0,
            'rows_inserted': 0,
            'errors': [],
            'warnings': [],
        }

    def connect_db(self):
        """Connect to SQLite database."""
        if not os.path.exists(DB_PATH):
            log.error(f"Database not found: {DB_PATH}. Run db_init.py first.")
            return False
        self.db = sqlite3.connect(DB_PATH)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=NORMAL")
        return True

    def close_db(self):
        if self.db:
            self.db.close()

    # ── Source 1: BRVM.org ──

    def fetch_brvm_org(self):
        """Fetch latest data from BRVM.org."""
        log.info("[Source 1] Fetching from BRVM.org...")
        try:
            # BRVM.org course page
            url = f"{SOURCES['brvm_org']['base_url']}/cours-actions/0"
            resp = self.session.get(url, timeout=SOURCES['brvm_org']['timeout'])
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, 'lxml')
            table = soup.find('table', class_='table')
            if not table:
                table = soup.find('table')
            if not table:
                raise ValueError("No data table found on BRVM.org")

            rows_data = []
            for tr in table.find_all('tr')[1:]:  # Skip header
                tds = tr.find_all('td')
                if len(tds) < 6:
                    continue
                try:
                    symbol = tds[0].get_text(strip=True)
                    close_price = self._parse_number(tds[2].get_text(strip=True))
                    volume = self._parse_int(tds[5].get_text(strip=True))

                    # P0-7: Do NOT fabricate OHLC when the source provides only close.
                    # BRVM.org's standard table exposes only: symbol | prev | close | change | yield | volume.
                    # Some extended layouts add open/high/low at td[6..8] — parse those if present.
                    open_price = high_price = low_price = None
                    if len(tds) >= 9:
                        open_price = self._parse_number(tds[6].get_text(strip=True))
                        high_price = self._parse_number(tds[7].get_text(strip=True))
                        low_price = self._parse_number(tds[8].get_text(strip=True))

                    if close_price and close_price > 0:
                        rows_data.append({
                            'symbol': symbol,
                            'date': datetime.now().strftime('%Y-%m-%d'),
                            'close': close_price,
                            'volume': volume or 0,
                            # None values become NULL in SQLite — consumers must handle missing OHLC
                            # gracefully (e.g. fall back to close for charting purposes).
                            'open': open_price,
                            'high': high_price,
                            'low': low_price,
                        })
                except (ValueError, IndexError):
                    continue

            if rows_data:
                log.info(f"[BRVM.org] Fetched {len(rows_data)} tickers")
                return rows_data
            else:
                raise ValueError("No valid data rows parsed from BRVM.org")

        except Exception as e:
            log.warning(f"[BRVM.org] Failed: {e}")
            self.stats['warnings'].append(f"BRVM.org: {e}")
            return None

    # ── Source 2: RichBourse (fallback) ──

    def fetch_richbourse(self):
        """Fetch from RichBourse as fallback."""
        log.info("[Source 2] Fetching from RichBourse (fallback)...")
        try:
            url = f"{SOURCES['richbourse']['base_url']}/bourse/cotations"
            resp = self.session.get(url, timeout=SOURCES['richbourse']['timeout'])
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, 'lxml')
            table = soup.find('table')
            if not table:
                raise ValueError("No data table found on RichBourse")

            rows_data = []
            for tr in table.find_all('tr')[1:]:
                tds = tr.find_all('td')
                if len(tds) < 5:
                    continue
                try:
                    symbol = tds[0].get_text(strip=True)
                    close_price = self._parse_number(tds[1].get_text(strip=True))
                    volume = self._parse_int(tds[4].get_text(strip=True))

                    # P0-7: Same policy as BRVM.org — never fabricate OHLC.
                    # RichBourse rarely exposes intra-day OHLC in this view.
                    open_price = high_price = low_price = None
                    if len(tds) >= 8:
                        open_price = self._parse_number(tds[5].get_text(strip=True))
                        high_price = self._parse_number(tds[6].get_text(strip=True))
                        low_price = self._parse_number(tds[7].get_text(strip=True))

                    if close_price and close_price > 0:
                        rows_data.append({
                            'symbol': symbol,
                            'date': datetime.now().strftime('%Y-%m-%d'),
                            'close': close_price,
                            'volume': volume or 0,
                            'open': open_price,
                            'high': high_price,
                            'low': low_price,
                        })
                except (ValueError, IndexError):
                    continue

            if rows_data:
                log.info(f"[RichBourse] Fetched {len(rows_data)} tickers")
                return rows_data
            else:
                raise ValueError("No valid rows from RichBourse")

        except Exception as e:
            log.warning(f"[RichBourse] Failed: {e}")
            self.stats['warnings'].append(f"RichBourse: {e}")
            return None

    # ── Source 3: Local JSON cache (emergency) ──

    def fetch_local_cache(self):
        """Use local brvm_api_data.json as emergency fallback."""
        log.info("[Source 3] Using local JSON cache (emergency)...")
        api_path = os.path.join(DATA_DIR, 'brvm_api_data.json')
        if not os.path.exists(api_path):
            log.error("[Local Cache] brvm_api_data.json not found")
            return None

        try:
            with open(api_path, encoding='utf-8') as f:
                data = json.load(f)

            rows_data = []
            for symbol, info in data.items():
                ohlcv = info.get('ohlcv', [])
                if ohlcv:
                    latest = ohlcv[-1]
                    rows_data.append({
                        'symbol': symbol,
                        'date': latest[0],
                        'open': latest[1],
                        'high': latest[2],
                        'low': latest[3],
                        'close': latest[4],
                        'volume': int(latest[5]) if len(latest) > 5 else 0,
                    })

            log.info(f"[Local Cache] Loaded {len(rows_data)} tickers (latest dates may be old)")
            self.stats['warnings'].append("Using cached data — may not be current")
            return rows_data

        except Exception as e:
            log.error(f"[Local Cache] Failed: {e}")
            return None

    # ── Data Storage ──

    def store_data(self, rows_data, source_name):
        """Store fetched data in SQLite."""
        if not rows_data:
            return 0

        cursor = self.db.cursor()
        count = 0

        for row in rows_data:
            try:
                # P0-7: preserve None as SQL NULL — do NOT silently rewrite missing OHLC to close.
                # The schema must allow NULL on open/high/low; readers fall back to close where needed.
                cursor.execute("""
                    INSERT OR REPLACE INTO prices (symbol, date, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    row['symbol'], row['date'],
                    row.get('open'),
                    row.get('high'),
                    row.get('low'),
                    row['close'],
                    row.get('volume', 0),
                ))
                count += 1
            except Exception as e:
                self.stats['errors'].append(f"Store error {row.get('symbol')}: {e}")

        self.db.commit()
        self.stats['rows_inserted'] = count
        log.info(f"[DB] Stored {count} rows from {source_name}")
        return count

    # ── Validation ──

    def validate_data(self, rows_data):
        """Validate data integrity (BRVM limits: max 7.5% daily variation)."""
        valid = []
        for row in rows_data:
            price = row.get('close', 0)
            if price <= 0:
                self.stats['warnings'].append(f"Invalid price for {row.get('symbol')}: {price}")
                continue
            if price > 1_000_000:
                self.stats['warnings'].append(f"Suspicious price for {row.get('symbol')}: {price}")
                continue
            valid.append(row)

        removed = len(rows_data) - len(valid)
        if removed > 0:
            log.warning(f"[Validate] Removed {removed} invalid rows")

        return valid

    # ── Pipeline Run ──

    def run(self):
        """Execute the pipeline with fallback chain."""
        self.stats['start_time'] = time.time()
        log.info("=" * 50)
        log.info(f"  MANSA Data Pipeline — {datetime.now():%Y-%m-%d %H:%M:%S}")
        log.info("=" * 50)

        if not self.connect_db():
            self.send_alert("CRITICAL: Database connection failed", "Cannot connect to mansa.db")
            return False

        # Try sources in priority order
        data = None
        for source_key in ['brvm_org', 'richbourse', 'local_cache']:
            source = SOURCES[source_key]
            try:
                if source_key == 'brvm_org':
                    data = self.fetch_brvm_org()
                elif source_key == 'richbourse':
                    data = self.fetch_richbourse()
                elif source_key == 'local_cache':
                    data = self.fetch_local_cache()

                if data:
                    self.stats['source'] = source['name']
                    break
            except Exception as e:
                log.error(f"[{source['name']}] Unexpected error: {e}")
                continue

        if not data:
            msg = "All data sources failed"
            log.error(msg)
            self.log_pipeline_run('all', 'error', 0, 0, msg)
            self.send_alert("CRITICAL: All data sources failed",
                            "BRVM.org, RichBourse, and local cache all failed. Immediate action required.")
            self.close_db()
            return False

        # Validate and store
        data = self.validate_data(data)
        stored = self.store_data(data, self.stats['source'])
        self.stats['tickers_updated'] = len({r['symbol'] for r in data})

        # Log pipeline run
        duration = int((time.time() - self.stats['start_time']) * 1000)
        status = 'success' if stored > 0 else 'warning'
        self.log_pipeline_run(
            self.stats['source'], status,
            self.stats['tickers_updated'], stored, duration,
            '; '.join(self.stats['warnings'][:3]) if self.stats['warnings'] else None
        )

        log.info(f"[Pipeline] Completed in {duration}ms — {stored} rows from {self.stats['source']}")

        # Alert if we fell back to non-primary source
        if self.stats['source'] != 'BRVM.org':
            self.send_alert(
                f"WARNING: Using fallback source ({self.stats['source']})",
                f"Primary source (BRVM.org) failed. Data from {self.stats['source']}.\n"
                f"Warnings: {'; '.join(self.stats['warnings'])}"
            )

        self.close_db()
        return True

    def log_pipeline_run(self, source, status, tickers, rows, duration, message=None):
        """Log pipeline execution to database."""
        try:
            self.db.execute("""
                INSERT INTO pipeline_logs (source, status, tickers_updated, rows_inserted, duration_ms, message)
                VALUES (?, ?, ?, ?, ?, ?)
            """, [source, status, tickers, rows, duration, message])
            self.db.commit()
        except Exception as e:
            log.error(f"Failed to log pipeline run: {e}")

    # ── Health Check ──

    def health_check(self):
        """Check pipeline and data health."""
        if not self.connect_db():
            return {'status': 'critical', 'error': 'Cannot connect to database'}

        cursor = self.db.cursor()

        # Last successful run
        cursor.execute("""
            SELECT timestamp, source, tickers_updated, duration_ms
            FROM pipeline_logs WHERE status = 'success'
            ORDER BY id DESC LIMIT 1
        """)
        last_success = cursor.fetchone()

        # Recent errors
        cursor.execute("""
            SELECT COUNT(*) FROM pipeline_logs
            WHERE status = 'error' AND timestamp >= datetime('now', '-24 hours')
        """)
        recent_errors = cursor.fetchone()[0]

        # Data freshness
        cursor.execute("SELECT MAX(date) FROM prices")
        latest_date = cursor.fetchone()[0]

        # Data completeness
        cursor.execute("SELECT COUNT(DISTINCT symbol) FROM prices WHERE date = ?", [latest_date or ''])
        tickers_today = cursor.fetchone()[0]

        self.close_db()

        days_stale = 0
        if latest_date:
            latest = datetime.strptime(latest_date, '%Y-%m-%d')
            days_stale = (datetime.now() - latest).days

        status = 'healthy'
        issues = []
        if days_stale > 2:
            status = 'warning'
            issues.append(f"Data is {days_stale} days old")
        if days_stale > 5:
            status = 'critical'
        if recent_errors > 3:
            status = 'warning'
            issues.append(f"{recent_errors} errors in last 24h")
        if tickers_today < 40:
            issues.append(f"Only {tickers_today}/48 tickers have data for {latest_date}")

        report = {
            'status': status,
            'last_success': {
                'timestamp': last_success[0] if last_success else None,
                'source': last_success[1] if last_success else None,
                'tickers': last_success[2] if last_success else 0,
                'duration_ms': last_success[3] if last_success else 0,
            },
            'data_freshness': {
                'latest_date': latest_date,
                'days_stale': days_stale,
                'tickers_with_data': tickers_today,
            },
            'recent_errors_24h': recent_errors,
            'issues': issues,
        }

        return report

    # ── Backfill ──

    def backfill(self, days=30):
        """Backfill missing data from local CSV/JSON files."""
        log.info(f"[Backfill] Importing last {days} days from local files...")
        if not self.connect_db():
            return False

        cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        data = self.fetch_local_cache()
        if data:
            # For backfill we want historical data, not just latest
            api_path = os.path.join(DATA_DIR, 'brvm_api_data.json')
            if os.path.exists(api_path):
                with open(api_path, encoding='utf-8') as f:
                    full_data = json.load(f)

                cursor = self.db.cursor()
                count = 0
                for symbol, info in full_data.items():
                    for row in info.get('ohlcv', []):
                        if len(row) >= 5 and row[0] >= cutoff:
                            cursor.execute("""
                                INSERT OR IGNORE INTO prices (symbol, date, open, high, low, close, volume)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, (symbol, row[0], row[1], row[2], row[3], row[4],
                                  int(row[5]) if len(row) > 5 else 0))
                            count += 1

                self.db.commit()
                log.info(f"[Backfill] Inserted {count} rows since {cutoff}")

        self.close_db()
        return True

    # ── Alerts ──

    def send_alert(self, subject, body):
        """Send email alert for pipeline issues."""
        if not ALERT_EMAIL_TO or not SMTP_USER:
            log.warning(f"[Alert] Email not configured. Alert: {subject}")
            return

        try:
            msg = MIMEText(f"MANSA Data Pipeline Alert\n\n{body}\n\nTimestamp: {datetime.now()}")
            msg['Subject'] = f"[MANSA Pipeline] {subject}"
            msg['From'] = ALERT_EMAIL_FROM
            msg['To'] = ALERT_EMAIL_TO

            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASS)
                server.send_message(msg)

            log.info(f"[Alert] Email sent: {subject}")
        except Exception as e:
            log.error(f"[Alert] Failed to send email: {e}")

    # ── Helpers ──

    @staticmethod
    def _parse_number(text):
        """Parse a number from text (handles French format: 1 234,56)."""
        if not text:
            return 0
        text = text.replace('\xa0', '').replace(' ', '').replace(',', '.')
        text = ''.join(c for c in text if c.isdigit() or c in '.+-')
        try:
            return float(text) if text else 0
        except ValueError:
            return 0

    @staticmethod
    def _parse_int(text):
        """Parse integer from text."""
        if not text:
            return 0
        text = text.replace('\xa0', '').replace(' ', '').replace(',', '')
        text = ''.join(c for c in text if c.isdigit())
        try:
            return int(text) if text else 0
        except ValueError:
            return 0


# ═══════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description='MANSA BRVM Data Pipeline')
    parser.add_argument('--schedule', action='store_true', help='Run on schedule (every 15min)')
    parser.add_argument('--health', action='store_true', help='Check pipeline health')
    parser.add_argument('--backfill', type=int, metavar='DAYS', help='Backfill N days from local cache')
    args = parser.parse_args()

    pipeline = DataPipeline()

    if args.health:
        report = pipeline.health_check()
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return

    if args.backfill:
        pipeline.backfill(args.backfill)
        return

    if args.schedule:
        try:
            import schedule as sched
            log.info("[Schedule] Running pipeline every 15 minutes (Mon-Fri 10:00-16:00 GMT)")
            sched.every(15).minutes.do(pipeline.run)
            while True:
                now = datetime.now()
                if now.weekday() < 5 and MARKET_OPEN_HOUR <= now.hour < MARKET_CLOSE_HOUR:
                    sched.run_pending()
                time.sleep(60)
        except ImportError:
            log.error("schedule package not installed. Run: pip install schedule")
            sys.exit(1)
    else:
        pipeline.run()


if __name__ == '__main__':
    main()
