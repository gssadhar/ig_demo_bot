import os
import sys
import pandas as pd
import yfinance as yf
from trading_ig import IGService

IG_USERNAME = os.getenv("IG_USERNAME")
IG_PASSWORD = os.getenv("IG_PASSWORD")
IG_API_KEY = os.getenv("IG_API_KEY")
IG_ACC_NUMBER = os.getenv("IG_ACC_NUMBER")
IG_ACC_TYPE = "DEMO"

WATCHLIST_EPICS = {
    "AAPL": "UC.D.AAPL.DAILY.IP",
    "MSFT": "UC.D.MSFT.DAILY.IP",
    "NVDA": "UC.D.NVDA.DAILY.IP",
    "RR.L": "SE.D.RR.DAILY.IP",
    "GLEN.L": "SE.D.GLEN.DAILY.IP",
    "AZN.L": "SE.D.AZN.DAILY.IP",
}

def connect_to_ig():
    if not all([IG_USERNAME, IG_PASSWORD, IG_API_KEY, IG_ACC_NUMBER]):
        print("❌ Error: Missing IG credentials.")
        sys.exit(1)

    print("🔌 Connecting to IG Demo API...")
    ig_service = IGService(IG_USERNAME, IG_PASSWORD, IG_API_KEY, IG_ACC_TYPE)
    ig_service.create_session()
    ig_service.switch_account(IG_ACC_NUMBER, False)
    print(f"✅ Connected to Account: {IG_ACC_NUMBER}")
    return ig_service

def evaluate_signal(ticker):
    try:
        df = yf.Ticker(ticker).history(period="6mo", interval="1d")
        if len(df) < 50:
            return "HOLD"

        df["SMA_20"] = df["Close"].rolling(20).mean()
        df["SMA_50"] = df["Close"].rolling(50).mean()

        delta = df["Close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df["RSI"] = 100 - (100 / (1 + rs))

        latest = df.iloc[-1]
        if latest["SMA_20"] > latest["SMA_50"] and 45 <= latest["RSI"] <= 65:
            return "BUY"
    except Exception as e:
        print(f"Error evaluating {ticker}: {e}")
    return "HOLD"

def execute_ig_trade(ig_service, ticker, epic, signal):
    open_positions = ig_service.fetch_open_positions()
    if not open_positions.empty and "epic" in open_positions.columns:
        if epic in open_positions["epic"].tolist():
            print(f"ℹ️ Position already open for {ticker}. Skipping.")
            return

    if signal == "BUY":
        print(f"🚀 Signal BUY for {ticker}. Placing IG Spread Bet...")
        try:
            response = ig_service.create_open_position(
                currency_code="GBP",
                direction="BUY",
                epic=epic,
                expiry="-",
                force_open=True,
                guaranteed_stop=False,
                order_type="MARKET",
                size=1.0,           # £1/point
                stop_distance=20,   # 20-point stop loss
                limit_distance=40   # 40-point take profit
            )
            print(f"✅ Order executed for {ticker}: {response.get('dealReference', 'Success')}")
        except Exception as e:
            print(f"❌ Failed to place trade for {ticker}: {e}")

def run_bot():
    ig_service = connect_to_ig()
    for ticker, epic in WATCHLIST_EPICS.items():
        signal = evaluate_signal(ticker)
        print(f"Ticker: {ticker:6} | Signal: {signal}")
        if signal == "BUY":
            execute_ig_trade(ig_service, ticker, epic, signal)

if __name__ == "__main__":
    run_bot()
