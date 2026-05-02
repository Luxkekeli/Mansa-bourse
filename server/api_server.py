#!/usr/bin/env python3
"""
MANSA — REST API Server (Flask + SQLite)
Serves BRVM market data for the MANSA platform.

Endpoints:
  GET /api/health              — Server health check
  GET /api/tickers             — All tickers with metadata
  GET /api/ticker/<symbol>     — Single ticker detail + recent prices
  GET /api/prices/<symbol>     — Full price history (with ?from=&to= filters)
  GET /api/indices             — BRVM indices (Composite, 30, Prestige)
  GET /api/screener            — Multi-criteria stock screener
  GET /api/sectors             — Sector aggregation
  GET /api/dividends/<symbol>  — Dividend history
  GET /api/search?q=           — Global search (tickers, names)
  GET /api/market/snapshot     — Latest market snapshot
  GET /api/analytics/report    — Admin: weekly analytics report
  POST /api/analytics/track    — Track user events
  POST /api/payment/initiate   — Initiate payment (Orange/Wave/MTN)
  POST /api/payment/webhook    — Payment confirmation webhook
  GET /api/subscription/status — Check subscription status

Usage:
  python api_server.py                    # Dev mode (port 5000)
  gunicorn -w 4 -b 0.0.0.0:5000 api_server:app  # Production

Requirements: flask, flask-cors, flask-limiter
"""

import hashlib
import hmac
import json
import os
import sqlite3
import sys
import uuid
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, g, jsonify, request
from flask_cors import CORS

# ── Configuration ──
DB_PATH = os.environ.get('MANSA_DB', os.path.join(os.path.dirname(__file__), '..', 'mansa.db'))
API_VERSION = '1.0.0'
MAX_RESULTS = 5000

# ── P0-6: Force strong secrets ──
# MANSA_SECRET signs Flask sessions and other app-level secrets.
# MANSA_ADMIN_TOKEN is an INDEPENDENT credential for /api/admin/* and /api/analytics/report.
# Both are required in production. In dev (FLASK_ENV=development) we tolerate auto-generated
# values but still refuse weak ones, so devs are forced to set their own.
FLASK_ENV = os.environ.get('FLASK_ENV', 'production').lower()
IS_DEV = FLASK_ENV == 'development'

SECRET_KEY = os.environ.get('MANSA_SECRET')
ADMIN_TOKEN = os.environ.get('MANSA_ADMIN_TOKEN')

if not SECRET_KEY or len(SECRET_KEY) < 32:
    if IS_DEV:
        # Dev fallback — still random per-process, never reused across runs.
        import secrets as _secrets
        SECRET_KEY = _secrets.token_urlsafe(48)
        print("[API] WARNING: MANSA_SECRET unset, generated ephemeral dev key. "
              "Set MANSA_SECRET in .env for stable sessions.")
    else:
        raise RuntimeError(
            "MANSA_SECRET must be set to a strong random value (>= 32 chars) in production. "
            "Generate one with: python -c \"import secrets;print(secrets.token_urlsafe(48))\""
        )

if not ADMIN_TOKEN or len(ADMIN_TOKEN) < 32:
    if IS_DEV:
        import secrets as _secrets
        ADMIN_TOKEN = _secrets.token_urlsafe(32)
        print(f"[API] WARNING: MANSA_ADMIN_TOKEN unset, generated ephemeral dev token: {ADMIN_TOKEN}")
    else:
        raise RuntimeError(
            "MANSA_ADMIN_TOKEN must be set to a strong random value (>= 32 chars) in production. "
            "Generate one with: python -c \"import secrets;print(secrets.token_urlsafe(32))\""
        )

app = Flask(
    __name__,
    static_folder=os.path.join(os.path.dirname(__file__), '..', 'frontend'),
    static_url_path='',
)
app.config['SECRET_KEY'] = SECRET_KEY
# Secure session cookies (used once we wire real auth in P0-2)
app.config['SESSION_COOKIE_SECURE'] = not IS_DEV
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'


# Frontend root: serve frontend/app.html at "/" (single-server model used in
# dev + Render. nginx in front of gunicorn does the same in prod.)
@app.route('/')
def _serve_root():
    return app.send_static_file('app.html')

# ── P0-5: Restrict CORS via env var ──
# In dev: localhost defaults. In prod: must be set explicitly.
_default_origins = 'http://localhost:8080,http://127.0.0.1:8080' if IS_DEV else ''
_origins_raw = os.environ.get('MANSA_ALLOWED_ORIGINS', _default_origins).strip()
if not _origins_raw:
    raise RuntimeError(
        "MANSA_ALLOWED_ORIGINS must be set in production "
        "(e.g. 'https://mansa.finance,https://www.mansa.finance')"
    )
ALLOWED_ORIGINS = [o.strip() for o in _origins_raw.split(',') if o.strip()]
CORS(app, resources={r"/api/*": {"origins": ALLOWED_ORIGINS}}, supports_credentials=True)

# ── P2: Optional Sentry integration ─────────────────────────────────────
# Set MANSA_SENTRY_DSN to enable. No-op otherwise (zero overhead).
_SENTRY_DSN = os.environ.get('MANSA_SENTRY_DSN', '')
if _SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.flask import FlaskIntegration
        sentry_sdk.init(
            dsn=_SENTRY_DSN,
            integrations=[FlaskIntegration()],
            traces_sample_rate=float(os.environ.get('MANSA_SENTRY_TRACES_RATE', '0.05')),
            environment=FLASK_ENV,
            release=f"mansa@{API_VERSION}",
            send_default_pii=False,  # don't ship cookies/IPs by default
        )
        print(f"[API] Sentry enabled (env={FLASK_ENV})")
    except ImportError:
        print("[API] MANSA_SENTRY_DSN set but sentry-sdk not installed — pip install 'sentry-sdk[flask]'")


# ── P1-3: Security headers via flask-talisman ──────────────────────────
# CSP, HSTS, X-Frame-Options, Referrer-Policy in one place.
#
# Notes on the policy:
# - 'unsafe-inline' on style-src is required because the frontend uses heavy
#   inline `style=` attributes. Removing them is a P1-1/Vite refactor.
# - 'unsafe-inline' on script-src is the same story (lots of inline JS in
#   app.html). We MUST drop this as soon as the Vite split lands.
# - cdn.jsdelivr.net is whitelisted for Chart.js. Once we self-host it
#   (P1-4), we can drop the CDN entry.
# - HSTS is enabled in production; we let dev hit HTTP.
try:
    from flask_talisman import Talisman

    _CSP = {
        "default-src": "'self'",
        "script-src": [
            "'self'",
            "'unsafe-inline'",                # TODO: remove with P1-1 (Vite split)
            "https://challenges.cloudflare.com",  # Turnstile (loaded conditionally)
        ],
        "style-src": [
            "'self'",
            "'unsafe-inline'",                # TODO: remove with P1-1
            "https://fonts.googleapis.com",
        ],
        "font-src": ["'self'", "https://fonts.gstatic.com", "data:"],
        "img-src": ["'self'", "data:", "blob:"],
        "connect-src": ["'self'"],
        "frame-ancestors": "'none'",
        "base-uri": "'self'",
        "form-action": "'self'",
        "object-src": "'none'",
    }

    # Permissions-Policy directives (block unused powerful APIs).
    _PERMISSIONS = {
        "geolocation": "()",
        "microphone": "()",
        "camera": "()",
        "payment": "()",
        "usb": "()",
        "interest-cohort": "()",
        "browsing-topics": "()",
    }

    Talisman(
        app,
        content_security_policy=_CSP,
        content_security_policy_nonce_in=[],
        force_https=not IS_DEV,
        strict_transport_security=not IS_DEV,
        strict_transport_security_max_age=31536000,
        strict_transport_security_include_subdomains=True,
        frame_options="DENY",
        referrer_policy="strict-origin-when-cross-origin",
        session_cookie_secure=not IS_DEV,
        session_cookie_http_only=True,
        permissions_policy=_PERMISSIONS,
    )

    @app.after_request
    def _add_extra_security_headers(resp):
        # X-Content-Type-Options is set by Talisman, but we also want to ensure
        # it's present even on responses we generate before Talisman runs.
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        return resp

except ImportError:
    print("[API] flask-talisman not installed — security headers will be missing.")


# Rate limiting (optional — requires flask-limiter)
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    limiter = Limiter(get_remote_address, app=app,
                      default_limits=["200 per minute", "5000 per hour"],
                      storage_uri="memory://")
except ImportError:
    limiter = None
    print("[API] flask-limiter not installed, rate limiting disabled")


# ═══════════════════════════════════════════════
#  P0-1 / P0-2: Register Blueprints (auth + community)
# ═══════════════════════════════════════════════
# Dual-import: relative when loaded as `server.api_server` (flask/gunicorn),
# absolute when loaded as `api_server` (tests with mansa/server on sys.path).
# DO NOT mutate sys.path here — that triggers recursive imports of the
# blueprint modules and Flask raises "blueprint already registered".

try:
    try:
        from .auth import auth_bp, require_auth  # type: ignore[import-not-found]
    except ImportError:
        from auth import auth_bp, require_auth  # type: ignore[no-redef]
    app.register_blueprint(auth_bp)
except Exception as _e:  # pragma: no cover — startup-only
    print(f"[API] auth blueprint not registered: {_e}")
    require_auth = lambda f: f  # noqa: E731

try:
    try:
        from .community import community_bp  # type: ignore[import-not-found]
    except ImportError:
        from community import community_bp  # type: ignore[no-redef]
    app.register_blueprint(community_bp)
except Exception as _e:  # pragma: no cover
    print(f"[API] community blueprint not registered: {_e}")


# ═══════════════════════════════════════════════
#  Database Connection
# ═══════════════════════════════════════════════

def get_db():
    """Get thread-local database connection."""
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
        g.db.execute("PRAGMA cache_size=-64000")  # 64MB cache
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def query_db(query, args=(), one=False):
    """Execute query and return results as list of dicts."""
    cur = get_db().execute(query, args)
    rv = [dict(row) for row in cur.fetchall()]
    return (rv[0] if rv else None) if one else rv


# ═══════════════════════════════════════════════
#  Authentication Helpers
# ═══════════════════════════════════════════════

def require_admin(f):
    """Decorator: require admin API token.

    P0-6: ADMIN_TOKEN is INDEPENDENT from SECRET_KEY (Flask session signing).
    The token must be sent as ``X-Admin-Token`` header. Constant-time comparison
    via hmac.compare_digest to avoid timing side channels.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # Accept legacy header for one release cycle, log a deprecation.
        provided = request.headers.get('X-Admin-Token') or request.headers.get('X-Admin-Key', '')
        if not provided:
            return jsonify({'error': 'Unauthorized', 'code': 401}), 401
        if not hmac.compare_digest(provided, ADMIN_TOKEN):
            return jsonify({'error': 'Unauthorized', 'code': 401}), 401
        return f(*args, **kwargs)
    return decorated


# ═══════════════════════════════════════════════
#  API Endpoints
# ═══════════════════════════════════════════════

@app.route('/api/config')
def public_config():
    """Public configuration the frontend needs at boot.

    Includes only NON-SECRET values: turnstile site key, feature flags.
    The secret key for Turnstile lives in TURNSTILE_SECRET_KEY (server-only).
    """
    try:
        try:
            from .captcha import SITE_KEY as _SITE_KEY  # type: ignore
            from .captcha import is_enabled as _captcha_on  # type: ignore
        except ImportError:
            from captcha import SITE_KEY as _SITE_KEY  # type: ignore
            from captcha import is_enabled as _captcha_on  # type: ignore
    except ImportError:
        _SITE_KEY = ""
        _captcha_on = lambda: False  # noqa: E731
    return jsonify({
        'turnstile': {
            'enabled': _captcha_on(),
            'site_key': _SITE_KEY,
        },
        'payments_enabled': PAYMENTS_ENABLED,
        'analytics': {
            # Public domain only (e.g. "mansa.finance"). Plausible tracks per-domain.
            'plausible_domain': os.environ.get('MANSA_PLAUSIBLE_DOMAIN', ''),
        },
        'version': API_VERSION,
    })


@app.route('/api/health')
def health():
    """Server health check."""
    try:
        db = get_db()
        ticker_count = db.execute("SELECT COUNT(*) FROM tickers").fetchone()[0]
        price_count = db.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
        latest = db.execute("SELECT MAX(date) FROM prices").fetchone()[0]
        pipeline = db.execute(
            "SELECT status, timestamp FROM pipeline_logs ORDER BY id DESC LIMIT 1"
        ).fetchone()

        return jsonify({
            'status': 'healthy',
            'version': API_VERSION,
            'database': {
                'tickers': ticker_count,
                'price_rows': price_count,
                'latest_date': latest,
            },
            'pipeline': {
                'last_run': dict(pipeline) if pipeline else None,
            },
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500


@app.route('/api/tickers')
def get_tickers():
    """List all tickers with latest price and metadata.

    P1-9: rewritten with a window function CTE so we make ONE pass through
    the prices index instead of 2N correlated subqueries (one per ticker for
    last_date, one for prev_close). On a 108k-row prices table the old plan
    showed ~96 SCANS in EXPLAIN; the CTE collapses to a single SCAN + 1 SORT.
    """
    sector = request.args.get('sector', '')
    country = request.args.get('country', '')
    ticker_type = request.args.get('type', '')

    # The CTE numbers each ticker's prices DESC by date — rn=1 is the latest,
    # rn=2 is the previous close. We then LEFT JOIN both rows back onto tickers
    # in a single pass.
    query = """
        WITH ranked AS (
            SELECT symbol, date, close, volume,
                   ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY date DESC) AS rn
            FROM prices
        )
        SELECT t.symbol, t.name, t.sector, t.type, t.country,
               p1.close  AS last_close,
               p1.volume AS last_volume,
               p1.date   AS last_date,
               p2.close  AS prev_close
        FROM tickers t
        LEFT JOIN ranked p1 ON p1.symbol = t.symbol AND p1.rn = 1
        LEFT JOIN ranked p2 ON p2.symbol = t.symbol AND p2.rn = 2
        WHERE 1=1
    """
    params = []

    if sector:
        query += " AND t.sector = ?"
        params.append(sector)
    if country:
        query += " AND t.country = ?"
        params.append(country)
    if ticker_type:
        query += " AND t.type = ?"
        params.append(ticker_type)

    query += " ORDER BY t.symbol"

    results = query_db(query, params)

    # Compute variation
    for r in results:
        if r.get('last_close') and r.get('prev_close') and r['prev_close'] > 0:
            r['variation_pct'] = round((r['last_close'] - r['prev_close']) / r['prev_close'] * 100, 2)
        else:
            r['variation_pct'] = 0

    return jsonify({
        'count': len(results),
        'tickers': results,
        'filters': {'sector': sector, 'country': country, 'type': ticker_type}
    })


@app.route('/api/ticker/<symbol>')
def get_ticker(symbol):
    """Detailed ticker info with recent 60-day prices."""
    ticker = query_db("SELECT * FROM tickers WHERE symbol = ?", [symbol], one=True)
    if not ticker:
        # Try with suffix
        ticker = query_db("SELECT * FROM tickers WHERE symbol LIKE ?", [f"%{symbol}%"], one=True)
    if not ticker:
        return jsonify({'error': 'Ticker not found', 'symbol': symbol}), 404

    # Recent prices (60 days)
    prices = query_db("""
        SELECT date, open, high, low, close, volume
        FROM prices WHERE symbol = ? ORDER BY date DESC LIMIT 60
    """, [ticker['symbol']])
    prices.reverse()

    # 52-week range
    range_52w = query_db("""
        SELECT MIN(low) as low_52w, MAX(high) as high_52w,
               MIN(close) as min_close_52w, MAX(close) as max_close_52w
        FROM prices WHERE symbol = ? AND date >= date('now', '-365 days')
    """, [ticker['symbol']], one=True)

    # Dividends
    dividends = query_db("""
        SELECT year, amount, ex_date, yield_pct
        FROM dividends WHERE symbol = ? ORDER BY year DESC LIMIT 10
    """, [ticker['symbol']])

    return jsonify({
        'ticker': dict(ticker),
        'prices': prices,
        'range_52w': range_52w,
        'dividends': dividends,
    })


@app.route('/api/prices/<symbol>')
def get_prices(symbol):
    """Full price history with optional date filters."""
    date_from = request.args.get('from', '2000-01-01')
    date_to = request.args.get('to', '2099-12-31')
    limit = min(int(request.args.get('limit', MAX_RESULTS)), MAX_RESULTS)

    prices = query_db("""
        SELECT date, open, high, low, close, volume
        FROM prices WHERE symbol = ? AND date BETWEEN ? AND ?
        ORDER BY date ASC LIMIT ?
    """, [symbol, date_from, date_to, limit])

    return jsonify({
        'symbol': symbol,
        'count': len(prices),
        'from': date_from,
        'to': date_to,
        'prices': prices
    })


@app.route('/api/indices')
def get_indices():
    """BRVM indices latest values.

    P1-9: same CTE pattern as /api/tickers. Single index scan.
    """
    indices = query_db("""
        WITH ranked AS (
            SELECT symbol, date, close,
                   ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY date DESC) AS rn
            FROM prices
        )
        SELECT t.symbol, t.name,
               p1.close AS value,
               p1.date  AS date,
               p2.close AS prev_value
        FROM tickers t
        LEFT JOIN ranked p1 ON p1.symbol = t.symbol AND p1.rn = 1
        LEFT JOIN ranked p2 ON p2.symbol = t.symbol AND p2.rn = 2
        WHERE t.type = 'index'
        ORDER BY t.symbol
    """)

    for idx in indices:
        if idx.get('value') and idx.get('prev_value') and idx['prev_value'] > 0:
            idx['change_pct'] = round((idx['value'] - idx['prev_value']) / idx['prev_value'] * 100, 2)
        else:
            idx['change_pct'] = 0

    return jsonify({'indices': indices})


# Whitelist of sortable columns to prevent SQL injection via ?sort= param.
_SCREENER_SORT_COLUMNS = {
    'symbol': 't.symbol',
    'name': 't.name',
    'sector': 't.sector',
    'country': 't.country',
    'price': 'p.close',
    'volume': 'p.volume',
}


@app.route('/api/screener')
def screener():
    """Multi-criteria stock screener.
    Query params: sector, country, min_volume, sort (whitelisted), order (ASC/DESC).
    """
    conditions = ["t.type = 'equity'"]
    params = []

    sector = request.args.get('sector')
    country = request.args.get('country')
    min_volume = request.args.get('min_volume', type=int)
    sort_arg = request.args.get('sort', 'symbol').lower()
    order = request.args.get('order', 'ASC')

    if sector:
        conditions.append("t.sector = ?")
        params.append(sector)
    if country:
        conditions.append("t.country = ?")
        params.append(country)
    if min_volume is not None:
        conditions.append("p.volume >= ?")
        params.append(min_volume)

    where = " AND ".join(conditions)
    safe_sort = _SCREENER_SORT_COLUMNS.get(sort_arg, 't.symbol')
    safe_order = 'DESC' if order.upper() == 'DESC' else 'ASC'

    # SAFE: `where` is composed only of literal SQL strings; user input always rides on `params`.
    # `safe_sort` and `safe_order` are whitelisted above. Bandit/ruff S608 false positive.
    query = f"""
        SELECT t.symbol, t.name, t.sector, t.country,
               p.close as price, p.volume, p.date as last_date
        FROM tickers t
        LEFT JOIN prices p ON p.symbol = t.symbol
            AND p.date = (SELECT MAX(date) FROM prices WHERE symbol = t.symbol)
        WHERE {where}
        ORDER BY {safe_sort} {safe_order}
    """  # noqa: S608  # nosec B608

    results = query_db(query, params)
    return jsonify({'count': len(results), 'results': results})


@app.route('/api/sectors')
def get_sectors():
    """Sector aggregation with totals."""
    sectors = query_db("""
        SELECT t.sector,
               COUNT(DISTINCT t.symbol) as nb_tickers,
               SUM(p.volume) as total_volume
        FROM tickers t
        LEFT JOIN prices p ON p.symbol = t.symbol
            AND p.date = (SELECT MAX(date) FROM prices WHERE symbol = t.symbol)
        WHERE t.type = 'equity'
        GROUP BY t.sector
        ORDER BY nb_tickers DESC
    """)
    return jsonify({'sectors': sectors})


@app.route('/api/fundamentals/<symbol>')
def get_fundamentals(symbol):
    """P0-8: per/pbr/roe/roa/marge/dette ratios for a ticker.

    Accepts both short ('SGBC') and full ('SGBC.ci') forms. Returns the most
    recent year first.
    """
    rows = query_db(
        """
        SELECT year, revenue, ebitda, net_income, eps, equity, total_debt,
               total_assets, shares_outstanding, per, pbr, roe, roa,
               margin_net, debt_equity
        FROM fundamentals WHERE symbol = ?
           OR symbol LIKE ?
        ORDER BY year DESC
        """,
        [symbol, symbol + ".%"],
    )
    return jsonify({"symbol": symbol, "count": len(rows), "fundamentals": rows})


@app.route('/api/dividends/<symbol>')
def get_dividends(symbol):
    """Dividend history for a ticker."""
    dividends = query_db("""
        SELECT year, amount, ex_date, pay_date, yield_pct, payout_ratio
        FROM dividends WHERE symbol = ? ORDER BY year DESC
    """, [symbol])
    return jsonify({'symbol': symbol, 'dividends': dividends})


@app.route('/api/search')
def search():
    """Global search across tickers and names."""
    q = request.args.get('q', '').strip()
    if len(q) < 1:
        return jsonify({'results': []})

    results = query_db("""
        SELECT symbol, name, sector, type, country
        FROM tickers
        WHERE symbol LIKE ? OR name LIKE ?
        ORDER BY
            CASE WHEN symbol LIKE ? THEN 0 ELSE 1 END,
            symbol
        LIMIT 20
    """, [f'%{q}%', f'%{q}%', f'{q}%'])

    return jsonify({'query': q, 'count': len(results), 'results': results})


@app.route('/api/market/snapshot')
def market_snapshot():
    """Latest market overview."""
    latest_date = query_db("SELECT MAX(date) as d FROM prices", one=True)
    if not latest_date or not latest_date['d']:
        return jsonify({'error': 'No data available'}), 404

    date = latest_date['d']

    # Top gainers / losers
    movers = query_db("""
        SELECT t.symbol, t.name, t.sector, p1.close as price,
               p1.volume,
               ROUND((p1.close - p2.close) / p2.close * 100, 2) as change_pct
        FROM tickers t
        JOIN prices p1 ON p1.symbol = t.symbol AND p1.date = ?
        JOIN prices p2 ON p2.symbol = t.symbol
            AND p2.date = (SELECT MAX(date) FROM prices WHERE symbol = t.symbol AND date < ?)
        WHERE t.type = 'equity'
        ORDER BY change_pct DESC
    """, [date, date])

    gainers = movers[:5]
    losers = list(reversed(movers[-5:])) if len(movers) > 5 else []

    return jsonify({
        'date': date,
        'total_tickers': len(movers),
        'gainers': [m for m in movers if m['change_pct'] > 0],
        'losers': [m for m in movers if m['change_pct'] < 0],
        'unchanged': [m for m in movers if m['change_pct'] == 0],
        'top_5_gainers': gainers,
        'top_5_losers': losers,
    })


# ═══════════════════════════════════════════════
#  Analytics Tracking
# ═══════════════════════════════════════════════

@app.route('/api/analytics/track', methods=['POST'])
def track_event():
    """Track user analytics event."""
    data = request.get_json(silent=True) or {}
    event_type = data.get('event', 'page_view')
    tab = data.get('tab', '')
    ticker = data.get('ticker', '')
    metadata = json.dumps(data.get('meta', {}))
    session_id = data.get('session', str(uuid.uuid4())[:8])
    ua = request.headers.get('User-Agent', '')[:200]
    ip_hash = hashlib.sha256(
        (request.remote_addr or 'unknown').encode()
    ).hexdigest()[:16]

    db = get_db()
    db.execute("""
        INSERT INTO analytics (session_id, event_type, tab, ticker, metadata, user_agent, ip_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, [session_id, event_type, tab, ticker, metadata, ua, ip_hash])
    db.commit()

    return jsonify({'status': 'tracked'}), 201


@app.route('/api/analytics/report')
@require_admin
def analytics_report():
    """Admin: weekly analytics report."""
    days = int(request.args.get('days', 7))
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()

    # Page views by tab
    tab_views = query_db("""
        SELECT tab, COUNT(*) as views, COUNT(DISTINCT session_id) as unique_sessions
        FROM analytics
        WHERE event_type = 'page_view' AND timestamp >= ?
        GROUP BY tab ORDER BY views DESC
    """, [since])

    # Most searched tickers
    ticker_views = query_db("""
        SELECT ticker, COUNT(*) as views
        FROM analytics
        WHERE ticker != '' AND ticker IS NOT NULL AND timestamp >= ?
        GROUP BY ticker ORDER BY views DESC LIMIT 20
    """, [since])

    # Daily active sessions
    daily_sessions = query_db("""
        SELECT DATE(timestamp) as day, COUNT(DISTINCT session_id) as sessions,
               COUNT(*) as total_events
        FROM analytics WHERE timestamp >= ?
        GROUP BY DATE(timestamp) ORDER BY day
    """, [since])

    # User behavior flow (most common tab sequences)
    total_events = query_db(
        "SELECT COUNT(*) as n FROM analytics WHERE timestamp >= ?", [since], one=True
    )

    return jsonify({
        'period': f'Last {days} days',
        'since': since,
        'summary': {
            'total_events': total_events['n'] if total_events else 0,
            'unique_tabs_visited': len(tab_views),
        },
        'tab_views': tab_views,
        'popular_tickers': ticker_views,
        'daily_sessions': daily_sessions,
    })


# ═══════════════════════════════════════════════
#  Payment Integration (Orange Money, Wave, MTN)
# ═══════════════════════════════════════════════

# P0-3: Premium disabled by default (Option A).
# Set MANSA_PAYMENTS_ENABLED=1 in .env to expose /api/payment/* (after Wave HMAC
# webhook verification is wired and providers are tested with sandbox).
PAYMENTS_ENABLED = os.environ.get('MANSA_PAYMENTS_ENABLED', '0') == '1'


def _payments_disabled_response():
    return jsonify({
        'error': 'Premium subscriptions are not yet available.',
        'code': 503,
        'detail': 'Set MANSA_PAYMENTS_ENABLED=1 server-side to enable.',
    }), 503


# Payment provider configurations (from environment)
PAYMENT_CONFIG = {
    'orange_money': {
        'merchant_id': os.environ.get('ORANGE_MERCHANT_ID', ''),
        'api_key': os.environ.get('ORANGE_API_KEY', ''),
        'api_url': 'https://api.orange.com/orange-money-webpay/dev/v1/webpayment',
        'return_url': 'https://mansa.finance/payment/success',
        'cancel_url': 'https://mansa.finance/payment/cancel',
        'notify_url': 'https://mansa.finance/api/payment/webhook',
    },
    'wave': {
        'api_key': os.environ.get('WAVE_API_KEY', ''),
        'api_url': 'https://api.wave.com/v1/checkout/sessions',
        'success_url': 'https://mansa.finance/payment/success',
        'error_url': 'https://mansa.finance/payment/cancel',
    },
    'mtn_momo': {
        'subscription_key': os.environ.get('MTN_SUBSCRIPTION_KEY', ''),
        'api_user': os.environ.get('MTN_API_USER', ''),
        'api_key': os.environ.get('MTN_API_KEY', ''),
        'api_url': 'https://sandbox.momodeveloper.mtn.com/collection/v1_0/requesttopay',
        'callback_url': 'https://mansa.finance/api/payment/webhook',
    }
}

PLANS = {
    'pro_monthly': {'name': 'MANSA Pro (Mensuel)', 'amount': 5000, 'currency': 'XOF', 'days': 30},
    'pro_yearly': {'name': 'MANSA Pro (Annuel)', 'amount': 48000, 'currency': 'XOF', 'days': 365},
    'sgi_monthly': {'name': 'MANSA SGI (Mensuel)', 'amount': 50000, 'currency': 'XOF', 'days': 30},
    'sgi_yearly': {'name': 'MANSA SGI (Annuel)', 'amount': 480000, 'currency': 'XOF', 'days': 365},
}


@app.route('/api/payment/plans')
def payment_plans():
    """Available subscription plans."""
    if not PAYMENTS_ENABLED:
        return _payments_disabled_response()
    return jsonify({
        'plans': {k: {**v, 'amount_formatted': f"{v['amount']:,} FCFA"} for k, v in PLANS.items()},
        'methods': ['orange_money', 'wave', 'mtn_momo'],
        'trial_days': 30,
    })


@app.route('/api/payment/initiate', methods=['POST'])
def initiate_payment():
    """Initiate a payment with selected provider."""
    if not PAYMENTS_ENABLED:
        return _payments_disabled_response()
    data = request.get_json(silent=True) or {}
    email = data.get('email', '').strip()
    plan_id = data.get('plan', '')
    method = data.get('method', '')
    # phone is collected by the frontend but used by provider-specific flows
    # only — kept here as documentation, not stored unless validated.
    _phone = data.get('phone', '').strip()  # noqa: F841

    # Validate
    if not email or '@' not in email:
        return jsonify({'error': 'Email invalide'}), 400
    if plan_id not in PLANS:
        return jsonify({'error': 'Plan inconnu', 'available': list(PLANS.keys())}), 400
    if method not in PAYMENT_CONFIG:
        return jsonify({'error': 'Methode de paiement non supportee'}), 400

    plan = PLANS[plan_id]
    ref = f"MANSA-{uuid.uuid4().hex[:12].upper()}"

    # Create pending subscription
    db = get_db()
    db.execute("""
        INSERT INTO subscriptions (user_email, plan, status, payment_method, payment_ref, amount, end_date)
        VALUES (?, ?, 'pending', ?, ?, ?, datetime('now', '+' || ? || ' days'))
    """, [email, plan_id, method, ref, plan['amount'], str(plan['days'])])
    db.commit()

    # Generate payment URL based on provider
    payment_url = None
    instructions = None

    if method == 'orange_money':
        payment_url = f"https://mansa.finance/pay/orange?ref={ref}"
        instructions = (
            f"1. Composez #144*82# sur votre telephone Orange\n"
            f"2. Selectionnez 'Payer une facture'\n"
            f"3. Entrez le code marchand: {PAYMENT_CONFIG['orange_money']['merchant_id']}\n"
            f"4. Montant: {plan['amount']:,} FCFA\n"
            f"5. Reference: {ref}\n"
            f"6. Confirmez avec votre code secret"
        )

    elif method == 'wave':
        payment_url = f"https://mansa.finance/pay/wave?ref={ref}"
        instructions = (
            f"1. Ouvrez l'application Wave\n"
            f"2. Scannez le QR code ou entrez le numero marchand\n"
            f"3. Montant: {plan['amount']:,} FCFA\n"
            f"4. Reference: {ref}\n"
            f"5. Confirmez le paiement"
        )

    elif method == 'mtn_momo':
        payment_url = f"https://mansa.finance/pay/mtn?ref={ref}"
        instructions = (
            f"1. Composez *133# sur votre telephone MTN\n"
            f"2. Selectionnez 'Paiement marchand'\n"
            f"3. Entrez le code marchand\n"
            f"4. Montant: {plan['amount']:,} FCFA\n"
            f"5. Reference: {ref}\n"
            f"6. Confirmez avec votre PIN"
        )

    return jsonify({
        'status': 'pending',
        'reference': ref,
        'plan': plan['name'],
        'amount': plan['amount'],
        'currency': 'FCFA',
        'method': method,
        'payment_url': payment_url,
        'instructions': instructions,
    })


@app.route('/api/payment/webhook', methods=['POST'])
def payment_webhook():
    """Handle payment confirmation from providers."""
    if not PAYMENTS_ENABLED:
        return _payments_disabled_response()
    data = request.get_json(silent=True) or request.form.to_dict()

    # Extract reference (varies by provider)
    ref = (data.get('reference') or data.get('payment_ref') or
           data.get('externalId') or data.get('merchant_reference', ''))
    status = data.get('status', '').lower()

    if not ref:
        return jsonify({'error': 'Missing reference'}), 400

    db = get_db()

    # Map provider status to our status
    if status in ('successful', 'success', 'completed', 'approved', 'paid'):
        new_status = 'active'
    elif status in ('failed', 'rejected', 'declined', 'expired'):
        new_status = 'cancelled'
    else:
        new_status = 'pending'

    db.execute("""
        UPDATE subscriptions SET status = ?, updated_at = datetime('now')
        WHERE payment_ref = ? AND status = 'pending'
    """, [new_status, ref])
    db.commit()

    # Log
    db.execute("""
        INSERT INTO pipeline_logs (source, status, message)
        VALUES ('payment', ?, ?)
    """, [new_status, f"Payment {ref}: {status} -> {new_status}"])
    db.commit()

    return jsonify({'status': 'received', 'reference': ref, 'result': new_status})


@app.route('/api/subscription/status')
def subscription_status():
    """Check subscription status for a user."""
    email = request.args.get('email', '').strip()
    if not email:
        return jsonify({'error': 'Email required'}), 400

    sub = query_db("""
        SELECT plan, status, payment_method, amount, start_date, end_date
        FROM subscriptions
        WHERE user_email = ? AND status = 'active'
        ORDER BY end_date DESC LIMIT 1
    """, [email], one=True)

    if sub:
        is_expired = sub['end_date'] and sub['end_date'] < datetime.utcnow().isoformat()
        if is_expired:
            get_db().execute(
                "UPDATE subscriptions SET status = 'expired' WHERE user_email = ? AND status = 'active'",
                [email]
            )
            get_db().commit()
            return jsonify({'plan': 'free', 'status': 'expired', 'message': 'Abonnement expire'})

        return jsonify({
            'plan': sub['plan'],
            'status': 'active',
            'expires': sub['end_date'],
            'method': sub['payment_method'],
        })

    return jsonify({'plan': 'free', 'status': 'none', 'message': 'Aucun abonnement actif'})


# ═══════════════════════════════════════════════
#  Admin: Weekly Report & Recommendations
# ═══════════════════════════════════════════════

@app.route('/api/admin/weekly-report')
@require_admin
def weekly_report():
    """Generate weekly performance and recommendations report."""
    week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()

    # Market performance this week
    market_perf = query_db("""
        SELECT t.symbol, t.name, t.sector,
               p_now.close as current_price,
               p_week.close as week_ago_price,
               ROUND((p_now.close - p_week.close) / p_week.close * 100, 2) as week_change
        FROM tickers t
        JOIN prices p_now ON p_now.symbol = t.symbol
            AND p_now.date = (SELECT MAX(date) FROM prices WHERE symbol = t.symbol)
        JOIN prices p_week ON p_week.symbol = t.symbol
            AND p_week.date = (SELECT MAX(date) FROM prices WHERE symbol = t.symbol AND date <= ?)
        WHERE t.type = 'equity'
        ORDER BY week_change DESC
    """, [week_ago])

    # Volume anomalies (>2x average)
    volume_alerts = query_db("""
        SELECT p.symbol, t.name, p.date, p.volume,
               avg_vol.avg_volume,
               ROUND(CAST(p.volume AS REAL) / avg_vol.avg_volume, 1) as volume_ratio
        FROM prices p
        JOIN tickers t ON t.symbol = p.symbol
        JOIN (
            SELECT symbol, AVG(volume) as avg_volume
            FROM prices WHERE date >= date('now', '-60 days')
            GROUP BY symbol HAVING AVG(volume) > 0
        ) avg_vol ON avg_vol.symbol = p.symbol
        WHERE p.date >= ? AND p.volume > avg_vol.avg_volume * 2
        ORDER BY volume_ratio DESC LIMIT 20
    """, [week_ago])

    # Pipeline health
    pipeline_health = query_db("""
        SELECT source, status, COUNT(*) as count,
               MAX(timestamp) as last_run
        FROM pipeline_logs
        WHERE timestamp >= ?
        GROUP BY source, status
    """, [week_ago])

    # Analytics summary
    user_stats = query_db("""
        SELECT COUNT(DISTINCT session_id) as unique_users,
               COUNT(*) as total_events,
               COUNT(DISTINCT tab) as tabs_visited
        FROM analytics WHERE timestamp >= ?
    """, [week_ago], one=True)

    # Generate recommendations
    recommendations = []
    if market_perf:
        top_gainers = [m for m in market_perf if m['week_change'] and m['week_change'] > 5]
        top_losers = [m for m in market_perf if m['week_change'] and m['week_change'] < -5]
        if top_gainers:
            recommendations.append({
                'type': 'market',
                'priority': 'info',
                'message': f"{len(top_gainers)} titre(s) en hausse de +5% cette semaine",
                'tickers': [g['symbol'] for g in top_gainers[:5]]
            })
        if top_losers:
            recommendations.append({
                'type': 'market',
                'priority': 'warning',
                'message': f"{len(top_losers)} titre(s) en baisse de -5% cette semaine",
                'tickers': [loser['symbol'] for loser in top_losers[:5]]
            })
    if volume_alerts:
        recommendations.append({
            'type': 'volume',
            'priority': 'alert',
            'message': f"{len(volume_alerts)} anomalies de volume detectees (>2x moyenne)",
            'details': [{'symbol': v['symbol'], 'ratio': v['volume_ratio']} for v in volume_alerts[:5]]
        })

    return jsonify({
        'report_date': datetime.utcnow().isoformat(),
        'period': 'Last 7 days',
        'market': {
            'total_tickers': len(market_perf),
            'top_5_gainers': market_perf[:5],
            'top_5_losers': market_perf[-5:] if market_perf else [],
        },
        'volume_alerts': volume_alerts,
        'pipeline_health': pipeline_health,
        'user_stats': dict(user_stats) if user_stats else {},
        'recommendations': recommendations,
    })


# ═══════════════════════════════════════════════
#  P0-1: Misc endpoints (chatbot, quiz email)
# ═══════════════════════════════════════════════
# These replace the old chatbot.php / index.php?action=send_quiz_email
# routes the frontend used to call.

# Minimal echo chatbot — placeholder until a real LLM/RAG backend is wired.
# The frontend already handles "no API" gracefully; this endpoint just confirms
# 200 with a canned response so the UI doesn't show network errors.
_CHAT_CANNED = (
    "Bonjour ! Je suis MANSA, votre assistant BRVM. "
    "Le chatbot intelligent sera connecté en v2.3 (Claude/GPT). "
    "En attendant, explorez les onglets Dashboard, Screener et Académie."
)


@app.route('/api/chat', methods=['POST'])
def chat():
    """Echo chatbot. Accepts {message: str}, returns a canned reply."""
    data = request.get_json(silent=True) or {}
    msg = (data.get('message') or '').strip()
    if not msg:
        return jsonify({'error': 'Message vide'}), 400
    if len(msg) > 2000:
        return jsonify({'error': 'Message trop long'}), 400
    return jsonify({
        'reply': _CHAT_CANNED,
        'echo': msg[:200],
    })


@app.route('/api/quiz/email', methods=['POST'])
def quiz_email():
    """Receive quiz results and (stub) email them. Returns 202.

    Real SMTP wiring lives in `auth._send_email_stub`; we reuse it.
    """
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    profil = (data.get('profil') or '').strip()
    score = data.get('score')
    max_score = data.get('maxScore')
    date = (data.get('date') or '').strip()

    if '@' not in email or len(email) > 254:
        return jsonify({'error': 'Email invalide'}), 400

    try:
        try:
            from .auth import _send_email_stub  # type: ignore
        except ImportError:
            from auth import _send_email_stub  # type: ignore
        body = (
            f"Bonjour,\n\nVoici votre profil investisseur MANSA :\n\n"
            f"  Profil : {profil}\n"
            f"  Score  : {score} / {max_score}\n"
            f"  Date   : {date}\n\n"
            f"Connectez-vous à MANSA pour découvrir les portefeuilles adaptés.\n"
        )
        _send_email_stub(email, "Votre profil investisseur MANSA", body)
    except Exception as e:
        # Stub never raises in practice but be defensive.
        return jsonify({'error': f'Email send failed: {e}'}), 500

    return jsonify({'status': 'queued', 'email': email}), 202


# ═══════════════════════════════════════════════
#  Error Handlers
# ═══════════════════════════════════════════════

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Endpoint not found', 'code': 404}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({'error': 'Internal server error', 'code': 500}), 500

@app.errorhandler(429)
def rate_limited(e):
    return jsonify({'error': 'Rate limit exceeded. Max 200 req/min.', 'code': 429}), 429


# ═══════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════

if __name__ == '__main__':
    print("=" * 50)
    print("  MANSA API Server v" + API_VERSION)
    print("  Database:", DB_PATH)
    print("  Env:     ", FLASK_ENV)
    print("  Origins: ", ALLOWED_ORIGINS)
    print("=" * 50)

    if not os.path.exists(DB_PATH):
        print("[WARN] Database not found. Run db_init.py first.")
        print("  python server/db_init.py")

    # P0-4: Debug only in dev. Production must use gunicorn.
    if not IS_DEV:
        print("[ERROR] Direct python invocation is only supported in FLASK_ENV=development.")
        print("        For production, use: gunicorn -w 4 -b 127.0.0.1:5000 server.api_server:app")
        sys.exit(1)

    # Bind to localhost only — prod traffic must go through nginx/gunicorn.
    # debug=True is gated above by IS_DEV check; production exits before reaching this line.
    app.run(host='127.0.0.1', port=5000, debug=True)  # noqa: S201  # nosec B201
