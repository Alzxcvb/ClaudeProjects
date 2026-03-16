"""
Mean Reversion Options Trader — Contrarian Paper Trading Bot.

Strategy: 2% move from prior day close triggers signal (contrarian):
  - Down 2%+ → buy ATM call (expect recovery)
  - Up 2%+ → buy ATM put (expect pullback)

Exit via option premium ratio:
  - Trailing take profit: after reaching 1.3x entry, sell on first price drop
  - Stop loss: current_price / entry_premium <= 0.95 (5% loss)
  - Session end: market sell all positions at current price with P&L
  - Max hold: 4 trading days

Logging:
  - Structured text log (logging module)
  - Trade journal CSV (append-only)
  - State JSON (open positions + deduplication)
"""

import os
import sys
import time
import logging
import json
import csv
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from typing import Optional, Tuple

import pandas as pd
import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import SYMBOLS

load_dotenv()

ET = ZoneInfo("America/New_York")

# Strategy parameters
MOVE_THRESHOLD = 0.01  # 1% move from prior close triggers signal
TAKE_PROFIT_MULT = 1.30  # target threshold — after reaching this, exit on first price drop
STOP_LOSS_MULT = 0.80  # exit when premium drops to 0.80x entry (20% loss)
EXPIRY_DAYS_MIN = 5  # minimum DTE for option selection
EXPIRY_DAYS_MAX = 9  # maximum DTE (~1 week target)
SCAN_CHUNK_SIZE = int(os.getenv("MEAN_REV_SCAN_CHUNK_SIZE", "15"))  # symbols per bulk request
SCAN_INTERVAL_SEC = int(os.getenv("MEAN_REV_SCAN_INTERVAL", "180"))  # scan every 3 minutes (paper API limits)
SESSION_START = "09:35"
SESSION_END = "15:55"
MAX_HOLD_DAYS = 4  # force-close after 4 trading days
MAX_TRADES_PER_DAY = int(os.getenv("MEAN_REV_MAX_TRADES_PER_DAY", "15"))
REQUEST_RETRIES = int(os.getenv("MEAN_REV_REQUEST_RETRIES", "5"))
REQUEST_BACKOFF_SEC = float(os.getenv("MEAN_REV_BACKOFF_SEC", "3.0"))  # 3s, 6s, 9s, 12s, 15s backoff
SCAN_CHUNK_DELAY_SEC = float(os.getenv("MEAN_REV_CHUNK_DELAY_SEC", "1.0"))

STATE_FILE = "mean_reversion_state.json"
TRADES_FILE = "mean_reversion_trades.csv"
MAX_SEEN_SIGNALS = 20000

# Use top 10 most liquid symbols to avoid rate limits and speed up testing
SCAN_SYMBOLS = SYMBOLS[:10]

# API credentials
API_KEY = os.getenv("ALPACA_API_KEY")
API_SECRET = os.getenv("ALPACA_API_SECRET")
BASE_URL = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
DATA_URL = "https://data.alpaca.markets"

HEADERS = {
    "APCA-API-KEY-ID": API_KEY,
    "APCA-API-SECRET-KEY": API_SECRET,
}

# Logging setup with timestamp-based log file
log_filename = f"logs/mean_reversion_{datetime.now(ET).strftime('%Y%m%d_%H%M%S')}.log"
os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

# In-memory state
open_positions: dict = {}  # contract_symbol -> position dict
seen_signals: set = set()  # dedupe signals (SYMBOL_YYYY-MM-DD)
daily_trade_count: int = 0
session_date: date = None
prior_closes: dict = {}  # cache for prior day closes


def _json_default(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    return str(obj)


def _request_with_retries(method: str, url: str, **kwargs) -> requests.Response:
    """HTTP request with retry/backoff for transient failures and rate limits."""
    attempt = 0
    while True:
        attempt += 1
        resp = requests.request(method, url, **kwargs)
        status = resp.status_code
        if status not in (429, 500, 502, 503, 504):
            return resp
        if attempt >= REQUEST_RETRIES:
            return resp
        retry_after = resp.headers.get("Retry-After")
        if retry_after:
            sleep_for = float(retry_after)
        else:
            sleep_for = REQUEST_BACKOFF_SEC * attempt
        log.warning("Retrying %s %s after status=%s (attempt %d/%d, sleep %.2fs)",
                    method, url, status, attempt, REQUEST_RETRIES, sleep_for)
        time.sleep(sleep_for)


def load_state() -> None:
    """Load persisted state from disk."""
    global open_positions, seen_signals, daily_trade_count, session_date

    if not os.path.exists(STATE_FILE):
        session_date = date.today()
        return

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
    except Exception as e:
        log.warning("State load failed (%s). Starting with empty state.", e)
        session_date = date.today()
        return

    open_positions = state.get("open_positions", {}) or {}
    seen_signals = set(state.get("seen_signals", []) or [])
    daily_trade_count = state.get("daily_trade_count", 0) or 0
    session_date = date.fromisoformat(state.get("session_date", date.today().isoformat()))

    # Clear counters if we've moved to a new trading day
    if session_date != date.today():
        seen_signals.clear()
        daily_trade_count = 0
        session_date = date.today()

    log.info(
        "State restored: %d open positions, %d seen signals, date=%s",
        len(open_positions),
        len(seen_signals),
        session_date.isoformat(),
    )


def save_state() -> None:
    """Persist state to disk."""
    global seen_signals
    if len(seen_signals) > MAX_SEEN_SIGNALS:
        seen_signals = set(sorted(seen_signals)[-MAX_SEEN_SIGNALS:])
    payload = {
        "saved_at": datetime.now(ET).isoformat(),
        "open_positions": open_positions,
        "seen_signals": list(seen_signals),
        "daily_trade_count": daily_trade_count,
        "session_date": session_date.isoformat(),
    }
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=_json_default)


def log_trade(
    event_type: str,
    symbol: str,
    contract_symbol: str,
    option_type: str,
    direction: str,
    entry_premium: float = None,
    exit_premium: float = None,
    qty: int = 1,
    pnl_per_contract: float = None,
    pnl_total: float = None,
    exit_reason: str = None,
    prior_close: float = None,
    trigger_price: float = None,
    pct_move: float = None,
    expiry_date: str = None,
    strike: float = None,
    entry_time: str = None,
    exit_time: str = None,
    hold_minutes: int = None,
) -> None:
    """Append a row to trade journal CSV."""
    row = {
        "timestamp": datetime.now(ET).isoformat(),
        "event_type": event_type,
        "symbol": symbol,
        "contract_symbol": contract_symbol,
        "option_type": option_type,
        "direction": direction,
        "entry_premium": entry_premium,
        "exit_premium": exit_premium,
        "qty": qty,
        "pnl_per_contract": pnl_per_contract,
        "pnl_total": pnl_total,
        "exit_reason": exit_reason,
        "prior_close": prior_close,
        "trigger_price": trigger_price,
        "pct_move": pct_move,
        "expiry_date": expiry_date,
        "strike": strike,
        "entry_time": entry_time,
        "exit_time": exit_time,
        "hold_minutes": hold_minutes,
    }
    file_exists = os.path.exists(TRADES_FILE)
    with open(TRADES_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


# ── Alpaca REST helpers ────────────────────────────────────────────────────────


def get_prior_closes(symbols: list) -> dict:
    """Fetch prior day's daily bar close for all symbols.

    Uses per-symbol endpoint (bulk endpoint unreliable on paper tier).
    Returns: {symbol: float}
    Caches result per session date.
    """
    global prior_closes

    if prior_closes and session_date == date.today():
        return prior_closes

    prior_closes = {}
    today_et = date.today()
    start = (datetime.utcnow() - timedelta(days=5)).strftime("%Y-%m-%dT00:00:00Z")

    for sym in symbols:
        try:
            r = _request_with_retries(
                "GET",
                f"{DATA_URL}/v2/stocks/{sym}/bars",
                headers=HEADERS,
                params={"timeframe": "1Day", "limit": 5, "start": start},
                timeout=15,
            )
            r.raise_for_status()
            bars = r.json().get("bars", [])
            # bars returned ascending — pick latest bar strictly before today
            for bar in reversed(bars):
                bar_day = pd.to_datetime(bar["t"], utc=True).tz_convert(ET).date()
                if bar_day < today_et:
                    prior_closes[sym] = float(bar["c"])
                    break
        except Exception as e:
            log.error("[PRIOR_CLOSES] %s failed: %s", sym, e)
        time.sleep(SCAN_CHUNK_DELAY_SEC)

    log.info("Prior closes fetched for %d/%d symbols", len(prior_closes), len(symbols))
    return prior_closes


def get_current_prices(symbols: list) -> dict:
    """Fetch latest 15-min bar close price for all symbols.

    Uses per-symbol endpoint (bulk endpoint unreliable on paper tier).
    Returns: {symbol: float}
    """
    result = {}
    start = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%dT00:00:00Z")

    for sym in symbols:
        try:
            r = _request_with_retries(
                "GET",
                f"{DATA_URL}/v2/stocks/{sym}/bars",
                headers=HEADERS,
                params={"timeframe": "15Min", "limit": 5, "start": start},
                timeout=15,
            )
            r.raise_for_status()
            bars = r.json().get("bars", [])
            if bars:
                result[sym] = float(bars[-1]["c"])
        except Exception as e:
            log.error("[CURRENT_PRICES] %s failed: %s", sym, e)
        time.sleep(SCAN_CHUNK_DELAY_SEC)

    log.info("Current prices fetched for %d/%d symbols", len(result), len(symbols))
    return result


def scan_for_moves(prior: dict, current: dict) -> list:
    """Scan for 2% moves from prior close.

    Returns: list of (symbol, direction, pct_move, trigger_price)
    where direction is "call" (down) or "put" (up).

    Excludes symbols already in open_positions or seen_signals.
    """
    signals = []
    for symbol in SCAN_SYMBOLS:
        if symbol not in prior or symbol not in current:
            continue

        # Skip if already in open position for same underlying, or already seen today.
        sig_id = f"{symbol}_{session_date.isoformat()}"
        already_open = any(p.get("symbol") == symbol for p in open_positions.values())
        if already_open or sig_id in seen_signals:
            continue

        prior_close = prior[symbol]
        current_price = current[symbol]
        pct_move = (current_price - prior_close) / prior_close

        if abs(pct_move) < MOVE_THRESHOLD:
            continue

        # Down move → buy call (contrarian: expect recovery)
        if pct_move <= -MOVE_THRESHOLD:
            direction = "call"
            signals.append((symbol, direction, pct_move, current_price, prior_close, sig_id))
            log.info(
                "SIGNAL | %s | direction=call | pct_move=%.3f%% | prior_close=%.2f | current=%.2f",
                symbol, pct_move * 100, prior_close, current_price
            )

        # Up move → buy put (contrarian: expect pullback)
        elif pct_move >= MOVE_THRESHOLD:
            direction = "put"
            signals.append((symbol, direction, pct_move, current_price, prior_close, sig_id))
            log.info(
                "SIGNAL | %s | direction=put | pct_move=%.3f%% | prior_close=%.2f | current=%.2f",
                symbol, pct_move * 100, prior_close, current_price
            )

    if not signals:
        log.info("No qualifying moves found in scan")

    return signals


def find_atm_option(symbol: str, direction: str, current_price: float):
    """Find ATM option contract (5-9 day expiry, closest strike).

    Returns: tuple (OCC option symbol, strike, expiry_date) or (None, None, None).
    """
    opt_type = "call" if direction == "call" else "put"
    today = date.today()
    min_expiry = (today + timedelta(days=EXPIRY_DAYS_MIN)).isoformat()
    max_expiry = (today + timedelta(days=EXPIRY_DAYS_MAX)).isoformat()

    try:
        r = _request_with_retries(
            "GET",
            f"{BASE_URL}/v2/options/contracts",
            headers=HEADERS,
            params={
                "underlying_symbols": symbol,
                "type": opt_type,
                "expiration_date_gte": min_expiry,
                "expiration_date_lte": max_expiry,
                "limit": 100,
            },
            timeout=15,
        )
        r.raise_for_status()
        contracts = r.json().get("option_contracts", [])
        log.debug(
            "[OPTIONS] API response for %s %s: %d contracts found (expiry %s to %s)",
            symbol, opt_type, len(contracts), min_expiry, max_expiry
        )
    except Exception as e:
        log.error("[OPTIONS] Failed to fetch contracts for %s: %s", symbol, e)
        return None, None, None

    if not contracts:
        log.warning(
            "[OPTIONS] No contracts found for %s %s (searched %s to %s, limit=%d)",
            symbol, opt_type, min_expiry, max_expiry, 100
        )
        return None, None, None

    # Convert to DataFrame for easy filtering
    df = pd.DataFrame(contracts)
    df["strike_price"] = df["strike_price"].astype(float)
    df["expiration_date"] = pd.to_datetime(df["expiration_date"])

    # Pick nearest expiry first, then closest strike
    nearest_expiry = df["expiration_date"].min()
    df = df[df["expiration_date"] == nearest_expiry]
    df["strike_dist"] = (df["strike_price"] - current_price).abs()
    best = df.loc[df["strike_dist"].idxmin()]

    log.info(
        "[OPTIONS] %s %s: using %s | strike=%.2f | expiry=%s",
        symbol, opt_type, best["symbol"],
        best["strike_price"], best["expiration_date"].date()
    )
    return best["symbol"], float(best["strike_price"]), best["expiration_date"].date().isoformat()


def place_option_order(contract_symbol: str, qty: int = 1) -> dict:
    """Place a market buy order for an option."""
    try:
        r = _request_with_retries(
            "POST",
            f"{BASE_URL}/v2/orders",
            headers=HEADERS,
            json={
                "symbol": contract_symbol,
                "qty": qty,
                "side": "buy",
                "type": "market",
                "time_in_force": "day",
                "order_class": "simple",
            },
            timeout=15,
        )
        r.raise_for_status()
        order = r.json()

        # Resolve actual option fill premium.
        filled_price = None
        order_id = order.get("id")
        for _ in range(8):
            time.sleep(1.0)
            # 1) Order-level filled average price
            if order_id:
                try:
                    ro = _request_with_retries(
                        "GET",
                        f"{BASE_URL}/v2/orders/{order_id}",
                        headers=HEADERS,
                        timeout=15,
                    )
                    if ro.status_code == 200:
                        order_view = ro.json()
                        status = str(order_view.get("status", "")).lower()
                        favg = order_view.get("filled_avg_price")
                        if favg is not None and float(favg) > 0:
                            filled_price = float(favg)
                            break
                        if status in {"canceled", "expired", "rejected"}:
                            break
                except Exception:
                    pass
            # 2) Position average entry price
            try:
                rp = _request_with_retries(
                    "GET",
                    f"{BASE_URL}/v2/positions/{contract_symbol}",
                    headers=HEADERS,
                    timeout=15,
                )
                if rp.status_code == 200:
                    pos = rp.json()
                    avg_entry = pos.get("avg_entry_price")
                    if avg_entry is not None and float(avg_entry) > 0:
                        filled_price = float(avg_entry)
                        break
            except Exception:
                pass

        if filled_price is None and order_id:
            # Avoid leaving unknown/untracked orders alive.
            try:
                _request_with_retries(
                    "DELETE",
                    f"{BASE_URL}/v2/orders/{order_id}",
                    headers=HEADERS,
                    timeout=15,
                )
            except Exception:
                pass
            log.error("[ORDER] Could not confirm fill premium for %s order=%s", contract_symbol, order_id)
            return None

        order["filled_price"] = filled_price

        return order
    except Exception as e:
        log.error("[ORDER] Failed to place order for %s: %s", contract_symbol, e)
        return None


def close_option_position(contract_symbol: str, qty: int = 1) -> dict:
    """Sell/close an open option position."""
    try:
        r = _request_with_retries(
            "POST",
            f"{BASE_URL}/v2/orders",
            headers=HEADERS,
            json={
                "symbol": contract_symbol,
                "qty": qty,
                "side": "sell",
                "type": "market",
                "time_in_force": "day",
                "order_class": "simple",
            },
            timeout=15,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log.error("[CLOSE] Failed to close %s: %s", contract_symbol, e)
        return None


def get_position_current_price(contract_symbol: str) -> Tuple[Optional[float], bool]:
    """Get option position current premium.

    Returns:
      (price, True) when position exists
      (None, False) when position does not exist (404)
    Raises:
      RuntimeError on transient/API failures so caller does not drop state.
    """
    try:
        r = _request_with_retries(
            "GET",
            f"{BASE_URL}/v2/positions/{contract_symbol}",
            headers=HEADERS,
            timeout=15,
        )
    except Exception as e:
        raise RuntimeError(f"request error: {e}") from e

    if r.status_code == 404:
        return None, False
    if r.status_code >= 400:
        raise RuntimeError(f"status={r.status_code} body={r.text[:300]}")

    pos = r.json()
    current = pos.get("current_price")
    if current is None:
        current = pos.get("lastday_price")
    return (float(current) if current is not None else None), True


def is_market_open() -> bool:
    """Check if market is open via /v2/clock."""
    try:
        r = requests.get(f"{BASE_URL}/v2/clock", headers=HEADERS, timeout=10)
        r.raise_for_status()
        return r.json()["is_open"]
    except Exception as e:
        # Fallback to time-based check
        now = datetime.now(ET)
        if now.weekday() >= 5:
            log.warning("Clock check failed (%s), weekend — assuming closed.", e)
            return False
        t = now.strftime("%H:%M")
        fallback = "09:30" <= t <= "16:00"
        log.warning("Clock check failed (%s), time-based fallback → %s.",
                    e, "OPEN" if fallback else "closed")
        return fallback


def in_session() -> bool:
    """Check if current time is within trading session window."""
    t = datetime.now(ET).strftime("%H:%M")
    return SESSION_START <= t <= SESSION_END


def get_open_option_positions() -> dict:
    """Return open option positions keyed by option contract symbol."""
    r = _request_with_retries(
        "GET",
        f"{BASE_URL}/v2/positions",
        headers=HEADERS,
        timeout=20,
    )
    r.raise_for_status()
    out = {}
    for p in r.json():
        if p.get("asset_class") != "us_option":
            continue
        sym = p.get("symbol")
        if sym:
            out[sym] = p
    return out


def _infer_option_type_from_contract(contract_symbol: str) -> str:
    marker = contract_symbol[-9:-8] if len(contract_symbol) >= 9 else ""
    if marker == "C":
        return "call"
    if marker == "P":
        return "put"
    return ""


def reconcile_positions_with_broker() -> None:
    """Align local open position tracking with broker truth."""
    try:
        broker_positions = get_open_option_positions()
    except Exception as e:
        log.warning("Reconcile skipped: could not load broker positions (%s)", e)
        return

    local_contracts = set(open_positions.keys())
    broker_contracts = set(broker_positions.keys())

    # Local entries that no longer exist at broker -> remove.
    stale_local = sorted(local_contracts - broker_contracts)
    for contract_symbol in stale_local:
        pos = open_positions.get(contract_symbol, {})
        log.warning("Reconciling stale local position: %s", contract_symbol)
        log_trade(
            event_type="EXIT",
            symbol=pos.get("symbol", ""),
            contract_symbol=contract_symbol,
            option_type=pos.get("option_type", ""),
            direction=pos.get("direction", ""),
            entry_premium=pos.get("entry_premium"),
            qty=pos.get("qty", 1),
            exit_reason="STARTUP_RECONCILE_MISSING_BROKER_POSITION",
            exit_time=datetime.now(ET).isoformat(),
        )
        open_positions.pop(contract_symbol, None)

    # Broker entries missing locally -> add so risk management can close/track them.
    missing_local = sorted(broker_contracts - local_contracts)
    for contract_symbol in missing_local:
        p = broker_positions[contract_symbol]
        avg_entry = float(p.get("avg_entry_price", 0) or 0)
        qty = abs(int(float(p.get("qty", 0) or 0)))
        opt_type = _infer_option_type_from_contract(contract_symbol)
        direction = "call" if opt_type == "call" else "put" if opt_type == "put" else ""
        open_positions[contract_symbol] = {
            "symbol": p.get("underlying_symbol", ""),
            "direction": direction,
            "option_type": opt_type,
            "entry_premium": avg_entry,
            "entry_time": datetime.now(ET).isoformat(),
            "qty": qty if qty > 0 else 1,
            "expiry": p.get("expiration_date"),
            "strike": float(p.get("strike_price", 0) or 0),
            "prior_close": None,
            "trigger_price": None,
            "pct_move": None,
        }
        log.warning("Reconciling broker-only position into local state: %s", contract_symbol)

    if stale_local or missing_local:
        save_state()
        log.info("Reconcile complete: removed=%d, added=%d", len(stale_local), len(missing_local))


def manage_positions() -> None:
    """Check exit conditions for open positions.

    Exits when:
    - Trailing take profit: price drops after having reached TAKE_PROFIT_MULT
    - Premium ratio <= STOP_LOSS_MULT (stop loss)
    - Held for MAX_HOLD_DAYS (force close)
    """
    to_close = []

    for contract_symbol, pos in list(open_positions.items()):
        try:
            current_price, exists = get_position_current_price(contract_symbol)
            if not exists:
                log.warning("[POSITION] %s not found at broker, removing from tracking", contract_symbol)
                log_trade(
                    event_type="EXIT",
                    symbol=pos.get("symbol", ""),
                    contract_symbol=contract_symbol,
                    option_type=pos.get("option_type", ""),
                    direction=pos.get("direction", ""),
                    entry_premium=pos.get("entry_premium"),
                    qty=pos.get("qty", 1),
                    exit_reason="BROKER_POSITION_MISSING",
                    exit_time=datetime.now(ET).isoformat(),
                )
                to_close.append(contract_symbol)
                continue
            if current_price is None or current_price <= 0:
                log.warning("[POSITION] %s returned invalid current_price=%s", contract_symbol, current_price)
                continue

            entry_premium = pos["entry_premium"]
            ratio = current_price / entry_premium if entry_premium > 0 else 0

            # Track peak price for trailing take-profit
            peak_price = pos.get("peak_price", entry_premium)
            if current_price > peak_price:
                peak_price = current_price
                pos["peak_price"] = peak_price

            # Check if target has been reached
            target_reached = pos.get("target_reached", False)
            if ratio >= TAKE_PROFIT_MULT and not target_reached:
                pos["target_reached"] = True
                target_reached = True
                log.info("TARGET REACHED | %s | entry=%.2f | current=%.2f | ratio=%.3f | now trailing",
                         contract_symbol, entry_premium, current_price, ratio)

            # Log position check
            log.info(
                "POSITION | %s | entry=%.2f | current=%.2f | ratio=%.3f | peak=%.2f | target=%s",
                contract_symbol, entry_premium, current_price, ratio, peak_price,
                "REACHED" if target_reached else "pending"
            )

            exit_reason = None

            # Trailing take profit: sell on first drop after target reached
            if target_reached and current_price < peak_price:
                exit_reason = "TAKE_PROFIT_TRAIL"
            # Check stop loss
            elif ratio <= STOP_LOSS_MULT:
                exit_reason = "STOP_LOSS"
            # Check max hold (in trading days)
            else:
                entry_time = datetime.fromisoformat(pos["entry_time"])
                days_held = (datetime.now(ET) - entry_time).days
                if days_held >= MAX_HOLD_DAYS:
                    exit_reason = "MAX_HOLD"

            if exit_reason:
                _close_position_with_pnl(contract_symbol, pos, exit_reason, to_close)

        except Exception as e:
            log.error("[ERROR] manage_positions for %s: %s", contract_symbol, e)

    # Remove closed positions
    for contract_symbol in to_close:
        open_positions.pop(contract_symbol, None)

    if to_close:
        save_state()


def _close_position_with_pnl(contract_symbol: str, pos: dict, exit_reason: str, to_close: list) -> None:
    """Close a position via market sell and log P&L."""
    current_price, _ = get_position_current_price(contract_symbol)
    order = close_option_position(contract_symbol, pos["qty"])
    if not order:
        log.error("[EXIT] Failed to close %s, will retry next cycle", contract_symbol)
        return
    to_close.append(contract_symbol)

    entry_premium = pos["entry_premium"]
    # Use current_price we just fetched; fallback to entry if unavailable
    exit_price = current_price if (current_price is not None and current_price > 0) else entry_premium

    pnl_per_contract = (exit_price - entry_premium) * 100
    pnl_total = pnl_per_contract * pos["qty"]

    exit_time = datetime.now(ET).isoformat()
    entry_time_dt = datetime.fromisoformat(pos["entry_time"])
    hold_minutes = int((datetime.now(ET) - entry_time_dt).total_seconds() / 60)

    log.info("EXIT | %s | reason=%s | entry=%.2f | exit=%.2f | pnl=$%+.2f",
             contract_symbol, exit_reason, entry_premium, exit_price, pnl_total)

    log_trade(
        event_type="EXIT",
        symbol=pos["symbol"],
        contract_symbol=contract_symbol,
        option_type=pos["option_type"],
        direction=pos["direction"],
        entry_premium=entry_premium,
        exit_premium=exit_price,
        qty=pos["qty"],
        pnl_per_contract=pnl_per_contract,
        pnl_total=pnl_total,
        exit_reason=exit_reason,
        exit_time=exit_time,
        hold_minutes=hold_minutes,
    )


def status() -> int:
    """Preflight checks for contrarian trader."""
    ok = True
    print("=== Mean Reversion Contrarian Trader Status ===")
    print(f"Time (ET):      {datetime.now(ET).isoformat()}")
    print(f"State file:     {STATE_FILE}")
    print(f"Trade journal:  {TRADES_FILE}")
    print(f"API base URL:   {BASE_URL}")
    print(f"Session (ET):   {SESSION_START}-{SESSION_END}")
    print(f"Scan chunk:     {SCAN_CHUNK_SIZE}")
    print(f"Max/day:        {MAX_TRADES_PER_DAY}")

    if not API_KEY or not API_SECRET:
        print("API keys:       MISSING")
        return 1
    print("API keys:       Present")

    try:
        load_state()
        save_state()
        print("State I/O:      OK")
    except Exception as e:
        ok = False
        print(f"State I/O:      FAIL ({e})")

    try:
        file_exists = os.path.exists(TRADES_FILE)
        with open(TRADES_FILE, "a", newline="", encoding="utf-8") as f:
            if not file_exists:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "timestamp", "event_type", "symbol", "contract_symbol", "option_type",
                        "direction", "entry_premium", "exit_premium", "qty", "pnl_per_contract",
                        "pnl_total", "exit_reason", "prior_close", "trigger_price", "pct_move",
                        "expiry_date", "strike", "entry_time", "exit_time", "hold_minutes",
                    ],
                )
                writer.writeheader()
        print("Journal I/O:    OK")
    except Exception as e:
        ok = False
        print(f"Journal I/O:    FAIL ({e})")

    try:
        r = _request_with_retries("GET", f"{BASE_URL}/v2/account", headers=HEADERS, timeout=15)
        r.raise_for_status()
        acct = r.json()
        print(f"Account:        OK (equity=${acct.get('equity')}, buying_power=${acct.get('buying_power')})")
    except Exception as e:
        ok = False
        print(f"Account:        FAIL ({e})")

    try:
        r = _request_with_retries("GET", f"{BASE_URL}/v2/clock", headers=HEADERS, timeout=10)
        r.raise_for_status()
        clock = r.json()
        print(f"Market clock:   OK (is_open={clock.get('is_open')})")
    except Exception as e:
        ok = False
        print(f"Market clock:   FAIL ({e})")

    try:
        broker_positions = get_open_option_positions()
        print(f"Broker options: OK ({len(broker_positions)} open option position(s))")
    except Exception as e:
        ok = False
        print(f"Broker options: FAIL ({e})")

    print("Overall:        " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def run() -> None:
    """Main trading loop."""
    global daily_trade_count, session_date

    if not API_KEY or not API_SECRET:
        raise RuntimeError("ALPACA_API_KEY / ALPACA_API_SECRET not set in .env")

    load_state()
    reconcile_positions_with_broker()
    save_state()

    log.info("=" * 60)
    log.info("Mean Reversion Contrarian Trader started")
    log.info("Config | threshold=%.2f%% take_profit=%.2fx stop_loss=%.2fx dte=%d-%d chunk=%d max_trades=%d",
             MOVE_THRESHOLD * 100, TAKE_PROFIT_MULT, STOP_LOSS_MULT,
             EXPIRY_DAYS_MIN, EXPIRY_DAYS_MAX, SCAN_CHUNK_SIZE, MAX_TRADES_PER_DAY)
    log.info("=" * 60)

    while True:
        try:
            now = datetime.now(ET)

            # Check market hours
            if not is_market_open():
                log.info("Market closed, sleeping 60s")
                time.sleep(60)
                continue

            # Check session window
            if not in_session():
                if open_positions:
                    log.info("Outside session window, force-closing %d positions at market price", len(open_positions))
                    to_close_eod = []
                    for contract_symbol, pos in list(open_positions.items()):
                        _close_position_with_pnl(contract_symbol, pos, "SESSION_END", to_close_eod)
                    for cs in to_close_eod:
                        open_positions.pop(cs, None)
                    save_state()
                log.info("Outside session window (%s), sleeping 60s", now.strftime("%H:%M"))
                time.sleep(60)
                continue

            # Reset daily counter if new day
            if session_date != date.today():
                session_date = date.today()
                daily_trade_count = 0
                seen_signals.clear()
                prior_closes.clear()
                log.info("New trading day: %s", session_date.isoformat())

            # Manage existing positions
            manage_positions()

            # Fetch prior closes (cached per session)
            priors = get_prior_closes(SCAN_SYMBOLS)
            if not priors:
                log.warning("Failed to fetch prior closes, retrying in %ds", SCAN_INTERVAL_SEC)
                time.sleep(SCAN_INTERVAL_SEC)
                continue

            # Fetch current prices
            currents = get_current_prices(SCAN_SYMBOLS)
            if not currents:
                log.warning("Failed to fetch current prices, retrying in 60s")
                time.sleep(60)
                continue

            # Scan for signals
            signals = scan_for_moves(priors, currents)
            log.info("SCAN SUMMARY | priors=%d currents=%d signals=%d open_positions=%d daily_trades=%d",
                     len(priors), len(currents), len(signals), len(open_positions), daily_trade_count)

            # Process each signal
            for symbol, direction, pct_move, trigger_price, prior_close, sig_id in signals:
                if daily_trade_count >= MAX_TRADES_PER_DAY:
                    log.info("Daily trade cap (%d) reached", MAX_TRADES_PER_DAY)
                    break

                try:
                    # Find ATM option
                    option_sym, strike, expiry = find_atm_option(symbol, direction, trigger_price)
                    if not option_sym:
                        log.warning("[SKIP] %s — no option contract found", symbol)
                        continue

                    # Place order
                    order = place_option_order(option_sym, qty=1)
                    if not order:
                        log.warning("[SKIP] %s — order placement failed", symbol)
                        continue

                    # Get filled price from order response (set during place_option_order)
                    entry_premium = order.get("filled_price", trigger_price)

                    # Record open position
                    entry_time = datetime.now(ET).isoformat()
                    open_positions[option_sym] = {
                        "symbol": symbol,
                        "direction": direction,
                        "option_type": "call" if direction == "call" else "put",
                        "entry_premium": entry_premium,
                        "entry_time": entry_time,
                        "qty": 1,
                        "expiry": expiry,
                        "strike": strike,
                        "prior_close": prior_close,
                        "trigger_price": trigger_price,
                        "pct_move": pct_move,
                    }
                    seen_signals.add(sig_id)
                    daily_trade_count += 1

                    # Log to CSV
                    log_trade(
                        event_type="ENTRY",
                        symbol=symbol,
                        contract_symbol=option_sym,
                        option_type="call" if direction == "call" else "put",
                        direction=direction,
                        entry_premium=entry_premium,
                        qty=1,
                        prior_close=prior_close,
                        trigger_price=trigger_price,
                        pct_move=pct_move,
                        expiry_date=expiry,
                        strike=strike,
                        entry_time=entry_time,
                    )

                    log.info("BUY | %s | qty=1 | entry_premium=%.2f", option_sym, entry_premium)
                    save_state()

                except Exception as e:
                    log.error("[ERROR] Processing signal for %s: %s", symbol, e)

            # Sleep for next scan interval
            time.sleep(SCAN_INTERVAL_SEC)

        except KeyboardInterrupt:
            log.info("Interrupted by user, exiting")
            break
        except Exception as e:
            log.error("[CRITICAL] Unhandled exception: %s", e, exc_info=True)
            time.sleep(60)


if __name__ == "__main__":
    run()
