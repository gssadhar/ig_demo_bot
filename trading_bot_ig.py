import os
import sys
import json
import pandas as pd
import yfinance as yf
from trading_ig import IGService

# ==========================================
# 1. LOAD CREDENTIALS FROM ENVIRONMENT
# ==========================================
IG_USERNAME = os.getenv("IG_USERNAME")
IG_PASSWORD = os.getenv("IG_PASSWORD")
IG_API_KEY = os.getenv("IG_API_KEY")
IG_ACC_NUMBER = os.getenv("IG_ACC_NUMBER")
IG_ACC_TYPE = "DEMO"  # Always test on DEMO account first

# Comprehensive EPIC Lookup Table for US & UK Equities (DFB = Daily Funded Bet)
EPIC_MAP = {
    # --- US Large-Cap Tech & Growth ---
    "AAPL": "UC.D.AAPL.DAILY.IP",
    "MSFT": "UC.D.MSFT.DAILY.IP",
    "NVDA": "UC.D.NVDA.DAILY.IP",
    "GOOGL": "UC.D.GOOGL.DAILY.IP",
    "AMZN": "UC.D.AMZN.DAILY.IP",
    "META": "UC.D.META.DAILY.IP",
    "TSLA": "UC.D.TSLA.DAILY.IP",
    "AMD": "UC.D.AMD.DAILY.IP",
    "AVGO": "UC.D.AVGO.DAILY.IP",
    
    # --- UK & European Large-Caps ---
    "RR.L": "SE.D.RR.DAILY.IP",         # Rolls-Royce
    "GLEN.L": "SE.D.GLEN.DAILY.IP",     # Glencore
    "AZN.L": "SE.D.AZN.DAILY.IP",       # AstraZeneca
    "SHEL.L": "SE.D.SHEL.DAILY.IP",     # Shell
    "BP.L": "SE.D.BP.DAILY.IP",         # BP
    "GSK.L": "SE.D.GSK.DAILY.IP",       # GSK
    "HSBC.L": "SE.D.HSBC.DAILY.IP",     # HSBC
    "ULVR.L": "SE.D.ULVR.DAILY.IP",     # Unilever
    
    # --- US Industrials, Financials & Consumer ---
    "JPM": "UC.D.JPM.DAILY.IP",
    "BAC": "UC.D.BAC.DAILY.IP",
    "CAT": "UC.D.CAT.DAILY.IP",
    "GE": "UC.D.GE.DAILY.IP",
    "PG": "UC.D.PG.DAILY.IP",
    "KO": "UC.D.KO.DAILY.IP",
    "COST": "UC.D.COST.DAILY.IP",
    
    # --- Mid/Small-Caps & High Growth ---
    "CROX": "UC.D.CROX.DAILY.IP",
    "DUOL": "UC.D.DUOL.DAILY.IP",
    "ELF": "UC.D.ELF.DAILY.IP",
    "CELH": "UC.D.CELH.DAILY.IP",
    "WING": "UC.D.WING.DAILY.IP",
    "BOOT": "UC.D.BOOT.DAILY.IP",
    "NIO": "UC.D.NIO.DAILY.IP",
    "ALTR": "UC.D.ALTR.DAILY.IP"
}


def connect_to_ig():
    """Establishes authenticated session with IG API."""
    if not all([IG_USERNAME, IG_PASSWORD, IG_API_KEY, IG_ACC_NUMBER]):
        print("❌ Error: Missing IG credentials in environment variables.")
        sys.exit(1)

    print("🔌 Connecting to IG Demo API...")
    ig_service = IGService(IG_USERNAME, IG_PASSWORD, IG_API_KEY, IG_ACC_TYPE)
    ig_service.create_session()
    
    # Safely switch account without raising exception if already active
    try:
        ig_service.switch_account(IG_ACC_NUMBER, False)
        print(f"✅ Switched to Account ID: {IG_ACC_NUMBER}")
    except Exception as e:
        if "error.switch.accountId-must-be-different" in str(e):
            print(f"✅ Active on Account ID: {IG_ACC_NUMBER}")
        else:
            print(f"⚠️ Account switch note: {e}")

    return ig_service


def get_account_balance(ig_service):
    """Fetches real-time available cash balance from IG Demo."""
    try:
        accounts = ig_service.fetch_accounts()
        if isinstance(accounts, pd.DataFrame) and not accounts.empty:
            for _, acc in accounts.iterrows():
                if acc.get("accountId") == IG_ACC_NUMBER or len(accounts) == 1:
                    balance_info = acc.get("balance", {})
                    available_cash = balance_info.get("available", 0) if isinstance(balance_info, dict) else acc.get("available", 0)
                    print(f"💰 Current Available Capital: £{float(available_cash):,.2f}")
                    return float(available_cash)
    except Exception as e:
        print(f"⚠️ Could not fetch real-time balance via API: {e}")
    
    # Fallback capital estimate if API structure varies
    return 22000.0


def calculate_stake_size(available_cash, stop_loss_points=20, risk_pct=0.01):
    """
    Calculates dynamic bet size (£ per point) risking 1% of available capital per trade.
    Example: 1% of £22,654 = £226.54. With a 20-point stop loss -> £226.54 / 20 = ~£11.32/point.
    """
    risk_amount = available_cash * risk_pct
    stake = risk_amount / stop_loss_points
    
    # Safety cap: Max £5.00/point stake limit during demo phase
    max_stake = 5.0  
    final_stake = min(round(stake, 2), max_stake)
    
    # Ensure minimum bet size matches IG requirements (£0.50/point)
    return max(final_stake, 0.50)


def load_screener_candidates():
    """Loads top-ranked candidates produced by stock_screener.py."""
    if os.path.exists("top_candidates.json"):
        try:
            with open("top_candidates.json", "r") as f:
                candidates = json.load(f)
                print(f"📋 Loaded {len(candidates)} candidates from Screener output.")
                return candidates
        except Exception as e:
            print(f"⚠️ Error reading top_candidates.json: {e}")
            
    print("ℹ️ No screener output found. Falling back to default core watchlist.")
    # Default fallback setup
    return [
        {"Ticker": "AAPL", "Signal": "BUY"},
        {"Ticker": "MSFT", "Signal": "BUY"},
        {"Ticker": "NVDA", "Signal": "BUY"},
        {"Ticker": "RR.L", "Signal": "BUY"},
        {"Ticker": "GLEN.L", "Signal": "BUY"},
        {"Ticker": "AZN.L", "Signal": "BUY"}
    ]


def evaluate_signal_realtime(ticker):
    """Confirms technical setup prior to execution."""
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
        
        # Bullish setup: 20-day SMA > 50-day SMA and RSI within neutral/bullish range
        if latest["SMA_20"] > latest["SMA_50"] and 40 <= latest["RSI"] <= 68:
            return "BUY"
    except Exception as e:
        print(f"Error evaluating live chart for {ticker}: {e}")
    
    return "HOLD"


def execute_ig_trade(ig_service, ticker, epic, available_cash):
    """Places Spread Bet order on IG Demo using dynamic stake sizing."""
    open_positions = ig_service.fetch_open_positions()
    
    # Prevent duplicate position entries
    if not open_positions.empty and "epic" in open_positions.columns:
        if epic in open_positions["epic"].tolist():
            print(f"ℹ️ Open position already exists for {ticker} ({epic}). Skipping.")
            return

    stop_points = 20
    limit_points = 40
    stake_size = calculate_stake_size(available_cash, stop_loss_points=stop_points, risk_pct=0.01)
    
    print(f"🚀 Placing BUY Spread Bet on {ticker} ({epic}) @ £{stake_size}/point...")
    try:
        response = ig_service.create_open_position(
            currency_code="GBP",
            direction="BUY",
            epic=epic,
            expiry="-",                # Daily Funded Bet (DFB)
            force_open=True,
            guaranteed_stop=False,
            order_type="MARKET",
            size=stake_size,           # Dynamic calculated stake (£/point)
            stop_distance=stop_points,  # 20 points stop loss
            limit_distance=limit_points # 40 points take profit
        )
        deal_ref = response.get("dealReference", "Success") if isinstance(response, dict) else "Executed"
        print(f"✅ Order successfully executed for {ticker} | Ref: {deal_ref}")
    except Exception as e:
        print(f"❌ Order execution failed for {ticker}: {e}")


def run_bot():
    ig_service = connect_to_ig()
    available_cash = get_account_balance(ig_service)
    
    candidates = load_screener_candidates()
    
    print("\n=== SCANNING SCREENER CANDIDATES FOR LIVE IG SPREAD BET TRADES ===")
    trades_evaluated = 0
    
    for item in candidates:
        ticker = item.get("Ticker")
        signal = item.get("Signal", "BUY")
        
        # Find matching IG EPIC code
        epic = EPIC_MAP.get(ticker)
        if not epic:
            print(f"⚠️ Skipped {ticker}: Missing IG EPIC mapping in lookup table.")
            continue
            
        # Re-confirm technical setup on live data
        live_signal = evaluate_signal_realtime(ticker)
        print(f"Ticker: {ticker:6} | Screener Signal: {signal:10} | Live Check: {live_signal:5}")
        
        if live_signal == "BUY" and signal in ["STRONG BUY", "BUY"]:
            execute_ig_trade(ig_service, ticker, epic, available_cash)
            trades_evaluated += 1

    print(f"\n=== EXECUTION SCAN COMPLETE. Processed {trades_evaluated} Trade Signals. ===")


if __name__ == "__main__":
    run_bot()
