import json
import time
from datetime import datetime, timezone
import numpy as np
import pandas as pd

# --- CONFIGURATION & RISK PARAMETERS ---
TRADING_LOG_PATH = "trading_log.json"
MIN_COOLDOWN_SECONDS = 1200  # 20-minute mandatory time gap between fills on the same ticker
ATR_MULTIPLIER_GAP = 0.5     # Requires price to move at least 0.5x ATR away from the last fill price


def load_trading_log(filepath=TRADING_LOG_PATH):
    """Loads existing trade logs to evaluate previous execution timestamps and prices."""
    try:
        with open(filepath, "r") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def calculate_atr(price_history, period=14):
    """Calculates Average True Range (ATR) for dynamic distance thresholding."""
    if len(price_history) < period:
        return np.std(price_history) if len(price_history) > 1 else 0.01
    
    highs = pd.Series([x['high'] for x in price_history])
    lows = pd.Series([x['low'] for x in price_history])
    closes = pd.Series([x['close'] for x in price_history])
    
    prev_closes = closes.shift(1)
    tr1 = highs - lows
    tr2 = (highs - prev_closes).abs()
    tr3 = (lows - prev_closes).abs()
    
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return true_range.rolling(window=period).mean().iloc[-1]


def check_execution_allowed(symbol, current_price, current_high, current_low, strategy_score, price_history):
    """
    Validates if a new order can be placed for a ticker based on:
    1. Time Cool-Down Timer (MIN_COOLDOWN_SECONDS)
    2. Dynamic Price Spacing via ATR (ATR_MULTIPLIER_GAP)
    3. Momentum Override Exception for high conviction runaways.
    """
    logs = load_trading_log()
    ticker_logs = [log for log in logs if log.get("symbol") == symbol]
    
    if not ticker_logs:
        return True, "Initial position allowed."
    
    # Get the most recent execution record for this symbol
    last_trade = max(ticker_logs, key=lambda x: x.get("timestamp", ""))
    last_timestamp_str = last_trade.get("timestamp")
    last_price = float(last_trade.get("price", current_price))
    
    # 1. Check Time Cool-Down
    if last_timestamp_str:
        last_time = datetime.fromisoformat(last_timestamp_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        elapsed_seconds = (now - last_time).total_seconds()
        
        if elapsed_seconds < MIN_COOLDOWN_SECONDS:
            # High-conviction momentum override check
            if strategy_score >= 0.85 and current_price > last_price:
                return True, f"Override: High momentum score ({strategy_score}) bypassed time cool-down."
            
            remaining = int((MIN_COOLDOWN_SECONDS - elapsed_seconds) / 60)
            return False, f"Blocked: Cooldown active. {remaining} minutes remaining for {symbol}."

    # 2. Check ATR-based Price Spacing Gap
    atr = calculate_atr(price_history)
    required_gap = atr * ATR_MULTIPLIER_GAP
    price_distance = abs(current_price - last_price)
    
    if price_distance < required_gap:
        return False, f"Blocked: Price distance ({price_distance:.2f}) is less than required ATR gap ({required_gap:.2f})."
        
    return True, "Passed all spacing and risk filters."


def execute_trade_signal(symbol, current_price, strategy_score, price_history):
    """Core execution wrapper enforcing spacing logic before submitting orders."""
    current_high = current_price * 1.002 # proxy if tick high/low not fed directly
    current_low = current_price * 0.998
    
    allowed, reason = check_execution_allowed(symbol, current_price, current_high, current_low, strategy_score, price_history)
    
    if not allowed:
        print(f"[REJECTED] {symbol} at {current_price} -> {reason}")
        return False
        
    # --- PROCEED WITH ORDER EXECUTION ---
    print(f"[EXECUTING] {symbol} at {current_price} -> {reason}")
    
    new_entry = {
        "symbol": symbol,
        "price": current_price,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "score": strategy_score
    }
    
    # Save back to persistent log
    logs = load_trading_log()
    logs.append(new_entry)
    with open(TRADING_LOG_PATH, "w") as file:
        json.dump(logs, file, indent=4)
        
    return True
