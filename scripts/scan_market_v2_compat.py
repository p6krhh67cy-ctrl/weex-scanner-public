#!/usr/bin/env python3
"""Compatibility launcher for scan_market_v2 using current WEEX v3 tickers."""
import os
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
import scan_market_v2 as scanner

V2_TICKERS = f"{scanner.BASE}/capi/v2/market/tickers"
V3_24H = f"{scanner.BASE}/capi/v3/market/ticker/24hr"
V3_BOOK = f"{scanner.BASE}/capi/v3/market/ticker/bookTicker"
_original_get_json = scanner.get_json


def _rows(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("data", "rows", "list"):
            val = payload.get(key)
            if isinstance(val, list):
                return val
    return []


def _stable_rows(url, timeout=20, attempts=3):
    """WEEX list endpoints occasionally return partial universes; union retries by symbol."""
    merged = {}
    counts = []
    for i in range(attempts):
        rows = _rows(_original_get_json(url, timeout=timeout))
        counts.append(len(rows))
        for x in rows:
            if not isinstance(x, dict):
                continue
            sym = str(x.get('symbol', '')).upper()
            if sym:
                merged[sym] = x
        if i + 1 < attempts:
            time.sleep(0.35)
    print(f'WEEX_UNIVERSE_RETRIES url={url.rsplit("/",1)[-1]} counts={counts} union={len(merged)}', flush=True)
    return list(merged.values())


def _legacy_tickers_from_v3(timeout=20):
    stats = _stable_rows(V3_24H, timeout=timeout)
    books = _stable_rows(V3_BOOK, timeout=timeout)
    book_by_symbol = {str(x.get("symbol", "")).upper(): x for x in books if isinstance(x, dict)}
    out = []
    for x in stats:
        sym = str(x.get("symbol", "")).upper()
        if not sym:
            continue
        b = book_by_symbol.get(sym, {})
        try:
            change_fraction = float(x.get("priceChangePercent", 0)) / 100.0
        except Exception:
            change_fraction = 0.0
        out.append({
            "symbol": sym,
            "last": x.get("lastPrice"),
            "high_24h": x.get("highPrice"),
            "low_24h": x.get("lowPrice"),
            "priceChangePercent": change_fraction,
            "volume_24h": x.get("quoteVolume"),
            "best_bid": b.get("bidPrice"),
            "best_ask": b.get("askPrice"),
        })
    if not out:
        raise RuntimeError("WEEX v3 ticker compatibility layer returned zero symbols")
    return out


def compat_get_json(url, timeout=20):
    if url.rstrip("/") == V2_TICKERS.rstrip("/"):
        return _legacy_tickers_from_v3(timeout=timeout)
    return _original_get_json(url, timeout=timeout)


scanner.get_json = compat_get_json

if __name__ == "__main__":
    scanner.main()
