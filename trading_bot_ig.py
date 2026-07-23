import os
import sys
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
IG_ACC_TYPE = "DEMO"  # Always test on DEMO first

# Map Tickers to IG Spread Betting EPICs
# Expanded Global Watchlist Across Sectors & Market Caps
WATCHLIST_EPICS = {
    # --- US LARGE CAP TECH & GROWTH ---
    "AAPL": "UC.D.AAPL.DAILY.IP",
    "MSFT": "UC.D.MSFT.DAILY.IP",
    "NVDA": "UC.D.NVDA.DAILY.IP",
    "GOOGL": "UC.D.GOOGL.DAILY.IP",
    "AMZN": "UC.D.AMZN.DAILY.IP",
    "META": "UC.D.META.DAILY.IP",
    "TSLA": "UC.D.TSLA.DAILY.IP",
    "AMD": "UC.D.AMD.DAILY.IP",
    
    # --- UK & EUROPEAN LARGE CAPS ---
    "RR.L": "SE.D.RR.DAILY.IP",         # Rolls-Royce
    "GLEN.L": "SE.D.GLEN.DAILY.IP",     # Glencore
    "AZN.L": "SE.D.AZN.DAILY.IP",       # AstraZeneca
    "SHEL.L": "SE.D.SHEL.DAILY.IP",     # Shell
    "BP.L": "SE.D.BP.DAILY.IP",         # BP
    "GSK.L": "SE.D.GSK.DAILY.IP",       # GSK
    "HSBC.L": "SE.D.HSBC.DAILY.IP",     # HSBC
    
    # --- MID & SMALL CAPS / HIGH GROWTH ---
    "CROX": "UC.D.CROX.DAILY.IP",
    "DUOL": "UC.D.DUOL.DAILY.IP",
    "ELF": "UC.D.ELF.DAILY.IP",
    "WING": "UC.D.WING.DAILY.IP",
    "BOOT": "UC.D.BOOT.DAILY.IP",
    
    # --- DEFENSIVE & CONSUMER STAPLES ---
    "PG": "UC.D.PG.DAILY.IP",
    "KO": "UC.D.KO.DAILY.IP",
    "COST": "UC.D.COST.DAILY.IP",
    "JPM": "UC.D.JPM.DAILY.IP"
}

def connect_to_ig():
    """Establishes session with IG API."""
    if not all([IG_USERNAME, IG_PASSWORD, IG_API_KEY, IG_ACC_NUMBER]):
        print("❌ Error: Missing IG credentials in environment variables.")
        sys.exit(1)

    print("🔌 Connecting to IG Demo API...")
    ig_service = IGService(IG_USERNAME, IG_PASSWORD, IG_API_KEY, IG_ACC_TYPE)
    ig_service.create_session()
    
    # Safely switch account
    try:
        ig_service.switch_account(IG_ACC_NUMBER, False)
        print(f"✅ Switched to Account: {IG_ACC_NUMBER}")
    except Exception as e:
        if "error.switch.accountId-must-be-different" in str(e):
            print(f"✅ Already active on Account: {IG_ACC_NUMBER}")
        else:
            print(f"⚠️ Account switch note: {e}")

    return ig_service


def get_account_balance(ig_service):
    """Fetches real-time available funds from IG Demo."""
    try:
        accounts = ig_service.fetch_accounts()
        # Find active account details
        if isinstance(accounts, pd.DataFrame) and not accounts.empty:
            for _, acc in accounts.iterrows():
                if acc.get("accountId") == IG_ACC_NUMBER or len(accounts) == 1:
                    balance_info = acc.get("balance", {})
                    available_cash = balance_info.get("available", 0) if isinstance(balance_info, dict) else acc.get("available", 0)
                    print(f"💰 Current Available Capital: £{float(available_cash):,.2f}")
                    return float(available_cash)
    except Exception as e:
        print(f"⚠️ Could not fetch account balance via API: {e}")
    
    # Default fallback balance if API call details vary
    return 20000.0


def calculate_stake_size(available_cash, stop_loss_points=20, risk_pct=0.01):
    """
    Calculates £ per point based on risking 1% of available capital per trade.
    Example: 1% of £22,654 = £226.54 risk budget.
    With a 20-point stop loss -> £226.54 / 20 = ~£11.32/point.
    """
    risk_amount = available_cash * risk_pct
    stake = risk_amount / stop_loss_points
    
    # Maximum safety limit during demo testing (£5/point max)
    max_stake = 5.0  
    final_stake = min(round(stake, 2), max_stake)
    
    # Ensure minimum IG bet size requirements (£0.50/point)
    return max(final_stake, 0.50)


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
        
        if latest["SMA_20"] > latest["SMA_50"] and 45 <= latest["RSI"] <= 65:
            return "BUY"
    except Exception as e:
        print(f"Error evaluating {ticker}: {e}")
    
    return "HOLD"


def execute_ig_trade(ig_service, ticker, epic, signal, available_cash):
    """Executes a Spread Bet order using dynamic position sizing."""
    open_positions = ig_service.fetch_open_positions()
    
    if not open_positions.empty and "epic" in open_positions.columns:
        if epic in open_positions["epic"].tolist():
            print(f"ℹ️ Position already open for {ticker} ({epic}). Skipping.")
            return

    if signal == "BUY":
        stop_points = 20
        limit_points = 40
        
        # Calculate dynamic stake size based on current cash balance
        dynamic_size = calculate_stake_size(available_cash, stop_loss_points=stop_points, risk_pct=0.01)
        
        print(f"🚀 Signal BUY for {ticker}. Placing Spread Bet at £{dynamic_size}/point...")
        try:
            response = ig_service.create_open_position(
                currency_code="GBP",
                direction="BUY",
                epic=epic,
                expiry="-",                # Daily Funded Bet (DFB)
                force_open=True,
                guaranteed_stop=False,
                order_type="MARKET",
                size=dynamic_size,         # Dynamic Stake Size (£/point)
                stop_distance=stop_points,  # 20 points stop loss
                limit_distance=limit_points # 40 points take profit
            )
            print(f"✅ Order executed for {ticker}: {response.get('dealReference', 'Success')}")
        except Exception as e:
            print(f"❌ Failed to place trade for {ticker}: {e}")


def run_bot():
    ig_service = connect_to_ig()
    
    # 1. Fetch real-time available cash balance
    available_cash = get_account_balance(ig_service)
    
    # 2. Evaluate Watchlist
    print("\n=== SCANNING WATCHLIST FOR IG SPREAD BET TRADES ===")
    for ticker, epic in WATCHLIST_EPICS.items():
        signal = evaluate_signal(ticker)
        print(f"Ticker: {ticker:6} | EPIC: {epic:20} | Signal: {signal}")
        
        if signal == "BUY":
            execute_ig_trade(ig_service, ticker, epic, signal, available_cash)


if __name__ == "__main__":
    run_bot()
