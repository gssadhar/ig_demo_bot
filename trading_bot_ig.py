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
IG_ACC_TYPE = "DEMO"

# EPIC Lookup Table mapped to Sector Categories
EPIC_MAP = {
    # --- TECH & GROWTH (Sector: Tech) ---
    "AAPL": {"epic": "UC.D.AAPL.DAILY.IP", "sector": "Tech"},
    "MSFT": {"epic": "UC.D.MSFT.DAILY.IP", "sector": "Tech"},
    "NVDA": {"epic": "UC.D.NVDA.DAILY.IP", "sector": "Tech"},
    "GOOGL": {"epic": "UC.D.GOOGL.DAILY.IP", "sector": "Tech"},
    "AMZN": {"epic": "UC.D.AMZN.DAILY.IP", "sector": "Tech"},
    "META": {"epic": "UC.D.META.DAILY.IP", "sector": "Tech"},
    "AMD":  {"epic": "UC.D.AMD.DAILY.IP",  "sector": "Tech"},
    
    # --- INDUSTRIALS & MATERIALS (Sector: Industrials) ---
    "RR.L":   {"epic": "SE.D.RR.DAILY.IP",   "sector": "Industrials"},
    "GLEN.L": {"epic": "SE.D.GLEN.DAILY.IP", "sector": "Industrials"},
    "CAT":    {"epic": "UC.D.CAT.DAILY.IP",  "sector": "Industrials"},
    "GE":     {"epic": "UC.D.GE.DAILY.IP",   "sector": "Industrials"},
    
    # --- HEALTHCARE & PHARMA (Sector: Healthcare) ---
    "AZN.L": {"epic": "SE.D.AZN.DAILY.IP", "sector": "Healthcare"},
    "GSK.L": {"epic": "SE.D.GSK.DAILY.IP", "sector": "Healthcare"},
    
    # --- ENERGY (Sector: Energy) ---
    "SHEL.L": {"epic": "SE.D.SHEL.DAILY.IP", "sector": "Energy"},
    "BP.L":   {"epic": "SE.D.BP.DAILY.IP",   "sector": "Energy"},
    
    # --- FINANCIALS & CONSUMER (Sector: Consumer/Financials) ---
    "HSBC.L": {"epic": "SE.D.HSBC.DAILY.IP", "sector": "Financials"},
    "JPM":    {"epic": "UC.D.JPM.DAILY.IP",  "sector": "Financials"},
    "COST":   {"epic": "UC.D.COST.DAILY.IP", "sector": "Consumer"}
}

# Risk Parameters
MAX_POSITIONS_PER_SECTOR = 2
RISK_PCT_PER_TRADE = 0.01  # Risk 1% of available cash per trade
DEFAULT_STOP_DISTANCE = 20  # 20 points stop-loss


def connect_to_ig():
    if not all([IG_USERNAME, IG_PASSWORD, IG_API_KEY, IG_ACC_NUMBER]):
        print("❌ Error: Missing IG credentials in environment variables.")
        sys.exit(1)

    print("🔌 Connecting to IG Demo API...")
    ig_service = IGService(IG_USERNAME, IG_PASSWORD, IG_API_KEY, IG_ACC_TYPE)
    ig_service.create_session()
    
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
        print(f"⚠️ Could not fetch balance via API: {e}")
    return 22000.0


def calculate_stake_size(available_cash, stop_loss_points=20):
    risk_amount = available_cash * RISK_PCT_PER_TRADE
    stake = risk_amount / stop_loss_points
    max_stake = 5.0  # Max safety limit (£5/point)
    return max(min(round(stake, 2), max_stake), 0.50)


def count_sector_positions(open_positions):
    """Calculates active trade count per sector."""
    sector_counts = {}
    if not open_positions.empty and "epic" in open_positions.columns:
        active_epics = open_positions["epic"].tolist()
        for ticker, data in EPIC_MAP.items():
            if data["epic"] in active_epics:
                sec = data["sector"]
                sector_counts[sec] = sector_counts.get(sec, 0) + 1
    return sector_counts


def load_screener_candidates():
    if os.path.exists("top_candidates.json"):
        try:
            with open("top_candidates.json", "r") as f:
                candidates = json.load(f)
                print(f"📋 Loaded {len(candidates)} candidates from Screener output.")
                return candidates
        except Exception as e:
            print(f"⚠️ Error loading candidates: {e}")
            
    return [
        {"Ticker": "AAPL", "Signal": "BUY"},
        {"Ticker": "MSFT", "Signal": "BUY"},
        {"Ticker": "NVDA", "Signal": "BUY"},
        {"Ticker": "RR.L", "Signal": "BUY"},
        {"Ticker": "GLEN.L", "Signal": "BUY"},
        {"Ticker": "AZN.L", "Signal": "BUY"}
    ]


def evaluate_signal_realtime(ticker):
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
        if latest["SMA_20"] > latest["SMA_50"] and 40 <= latest["RSI"] <= 68:
            return "BUY"
    except Exception as e:
        print(f"Error evaluating {ticker}: {e}")
    return "HOLD"


def execute_ig_trade(ig_service, ticker, epic, sector, open_positions, sector_counts, available_cash):
    # 1. Prevent duplicate position entries
    if not open_positions.empty and "epic" in open_positions.columns:
        if epic in open_positions["epic"].tolist():
            print(f"ℹ️ Open position already exists for {ticker} ({epic}). Skipping.")
            return

    # 2. Enforce Sector Concentration Cap
    current_sector_trades = sector_counts.get(sector, 0)
    if current_sector_trades >= MAX_POSITIONS_PER_SECTOR:
        print(f"🛡️ Sector Cap Reached: {sector} already has {current_sector_trades} active trades. Skipping {ticker}.")
        return

    stake_size = calculate_stake_size(available_cash, stop_loss_points=DEFAULT_STOP_DISTANCE)
    
    print(f"🚀 Placing BUY Trade on {ticker} ({sector}) @ £{stake_size}/point with Trailing Stop...")
    try:
        response = ig_service.create_open_position(
            currency_code="GBP",
            direction="BUY",
            epic=epic,
            expiry="-",
            force_open=True,
            guaranteed_stop=False,
            order_type="MARKET",
            size=stake_size,
            stop_distance=DEFAULT_STOP_DISTANCE,
            trailing_stop=True,               # Enables Trailing Stop Loss
            trailing_stop_increment=1.0       # Moves stop up every 1-point gain
        )
        deal_ref = response.get("dealReference", "Success") if isinstance(response, dict) else "Executed"
        print(f"✅ Order executed for {ticker} | Ref: {deal_ref}")
        
        # Update sector count dynamically
        sector_counts[sector] = sector_counts.get(sector, 0) + 1
    except Exception as e:
        print(f"❌ Execution failed for {ticker}: {e}")


def run_bot():
    ig_service = connect_to_ig()
    available_cash = get_account_balance(ig_service)
    
    # Fetch active open positions
    open_positions = ig_service.fetch_open_positions()
    sector_counts = count_sector_positions(open_positions)
    
    candidates = load_screener_candidates()
    print("\n=== SCANNING SCREENER CANDIDATES FOR LIVE IG SPREAD BET TRADES ===")
    
    for item in candidates:
        ticker = item.get("Ticker")
        signal = item.get("Signal", "BUY")
        
        meta = EPIC_MAP.get(ticker)
        if not meta:
            print(f"⚠️ Skipped {ticker}: Missing IG EPIC mapping.")
            continue
            
        epic = meta["epic"]
        sector = meta["sector"]
        
        live_signal = evaluate_signal_realtime(ticker)
        print(f"Ticker: {ticker:6} | Sector: {sector:11} | Signal: {signal:10} | Live: {live_signal:5}")
        
        if live_signal == "BUY" and signal in ["STRONG BUY", "BUY"]:
            execute_ig_trade(ig_service, ticker, epic, sector, open_positions, sector_counts, available_cash)

    print("\n=== EXECUTION SCAN COMPLETE ===")


if __name__ == "__main__":
    run_bot()
