import os
import sys
import pandas as pd
import yfinance as yf
from trading_ig import IGService

# ==========================================
# 1. LOAD CREDENTIALS FROM ENVIRONMENT
# ==========================================
IG_USERNAME = os.getenv("gdemobot")
IG_PASSWORD = os.getenv("Rednimrug1")
IG_API_KEY = os.getenv("d50de03a31a3e81420be29663d0124c27326dbfa")
IG_ACC_NUMBER = os.getenv("XYLKX")
IG_ACC_TYPE = "DEMO"  # Set to "LIVE" when ready for real funds

# Map Tickers to IG Spread Betting EPICs (DFB = Daily Funded Bet)
# Format: Ticker -> IG EPIC Code
WATCHLIST_EPICS = {
    "AAPL": "UC.D.AAPL.DAILY.IP",       # Apple (US)
    "MSFT": "UC.D.MSFT.DAILY.IP",       # Microsoft (US)
    "NVDA": "UC.D.NVDA.DAILY.IP",       # Nvidia (US)
    "RR.L": "SE.D.RR.DAILY.IP",         # Rolls-Royce (UK)
    "GLEN.L": "SE.D.GLEN.DAILY.IP",     # Glencore (UK)
    "AZN.L": "SE.D.AZN.DAILY.IP",       # AstraZeneca (UK)
}

def connect_to_ig():
    """Establishes session with IG API."""
    if not all([IG_USERNAME, IG_PASSWORD, IG_API_KEY, IG_ACC_NUMBER]):
        print("❌ Error: Missing IG credentials in environment variables.")
        sys.exit(1)

    print("🔌 Connecting to IG Demo API...")
    ig_service = IGService(IG_USERNAME, IG_PASSWORD, IG_API_KEY, IG_ACC_TYPE)
    ig_service.create_session()
    
    # Switch to specified Demo Account
    account_info = ig_service.switch_account(IG_ACC_NUMBER, False)
    print(f"✅ Connected to Account: {IG_ACC_NUMBER}")
    return ig_service

def evaluate_signal(ticker):
    """Calculates SMA and RSI setup for entry decision."""
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
        
        # Strategy Logic: SMA 20/50 Bullish Trend + RSI Momentum
        if latest["SMA_20"] > latest["SMA_50"] and 45 <= latest["RSI"] <= 65:
            return "BUY"
        elif latest["RSI"] > 75 or latest["SMA_20"] < latest["SMA_50"]:
            return "SELL"
    except Exception as e:
        print(f"Error evaluating {ticker}: {e}")
    
    return "HOLD"

def execute_ig_trade(ig_service, ticker, epic, signal):
    """Executes a Spread Bet order on IG Demo."""
    # Check current open positions to avoid duplicate trades
    open_positions = ig_service.fetch_open_positions()
    
    if not open_positions.empty and "marketName" in open_positions.columns:
        existing_epics = open_positions["epic"].tolist() if "epic" in open_positions.columns else []
        if epic in existing_epics:
            print(f"ℹ️ Position already open for {ticker} ({epic}). Skipping.")
            return

    if signal == "BUY":
        print(f"🚀 Signal BUY for {ticker}. Placing Spread Bet order on IG...")
        try:
            # Place DFB Spread Bet Buy Order
            response = ig_service.create_open_position(
                currency_code="GBP",
                direction="BUY",
                epic=epic,
                expiry="-",                # Daily Funded Bet
                force_open=True,
                guaranteed_stop=False,
                order_type="MARKET",
                size=1.0,                  # Bet £1 per point movement
                stop_distance=20,          # Stop loss 20 points away
                limit_distance=40          # Take profit 40 points away
            )
            print(f"✅ Order executed for {ticker}: {response.get('dealReference', 'Success')}")
        except Exception as e:
            print(f"❌ Failed to place trade for {ticker}: {e}")

def run_bot():
    ig_service = connect_to_ig()
    
    print("\n=== SCANNING WATCHLIST FOR IG SPREAD BET TRADES ===")
    for ticker, epic in WATCHLIST_EPICS.items():
        signal = evaluate_signal(ticker)
        print(f"Ticker: {ticker:6} | EPIC: {epic:20} | Signal: {signal}")
        
        if signal == "BUY":
            execute_ig_trade(ig_service, ticker, epic, signal)

if __name__ == "__main__":
    run_bot()
