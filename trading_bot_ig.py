import os
import sys
import json
import pandas as pd
from trading_ig import IGService

# ==========================================
# 1. LOAD CREDENTIALS FROM ENVIRONMENT
# ==========================================
IG_USERNAME = os.getenv("IG_USERNAME")
IG_PASSWORD = os.getenv("IG_PASSWORD")
IG_API_KEY = os.getenv("IG_API_KEY")
IG_ACC_NUMBER = os.getenv("IG_ACC_NUMBER")
IG_ACC_TYPE = "DEMO"

# COMPLETE EPIC Lookup Table
EPIC_MAP = {
    # --- TECH & GROWTH ---
    "AAPL":     {"epic": "UC.D.AAPL.DAILY.IP",  "sector": "Tech"},
    "MSFT":     {"epic": "UC.D.MSFT.DAILY.IP",  "sector": "Tech"},
    "NVDA":     {"epic": "UC.D.NVDA.DAILY.IP",  "sector": "Tech"},
    "GOOGL":    {"epic": "UC.D.GOOGL.DAILY.IP", "sector": "Tech"},
    "AMZN":     {"epic": "UC.D.AMZN.DAILY.IP",  "sector": "Tech"},
    "META":     {"epic": "UC.D.META.DAILY.IP",  "sector": "Tech"},
    "AMD":      {"epic": "UC.D.AMD.DAILY.IP",   "sector": "Tech"},
    "AVGO":     {"epic": "UC.D.AVGO.DAILY.IP",  "sector": "Tech"},
    "TSLA":     {"epic": "UC.D.TSLA.DAILY.IP",  "sector": "Tech"},
    "ALTR":     {"epic": "UC.D.ALTR.DAILY.IP",  "sector": "Tech"},

    # --- UK / EUROPEAN LARGE CAPS ---
    "RR.L":     {"epic": "SE.D.RR.DAILY.IP",    "sector": "Industrials"},
    "GLEN.L":   {"epic": "SE.D.GLEN.DAILY.IP",  "sector": "Materials"},
    "AZN.L":    {"epic": "SE.D.AZN.DAILY.IP",   "sector": "Healthcare"},
    "SHEL.L":   {"epic": "SE.D.SHEL.DAILY.IP",  "sector": "Energy"},
    "GSK.L":    {"epic": "SE.D.GSK.DAILY.IP",   "sector": "Healthcare"},
    "HSBC.L":   {"epic": "SE.D.HSBC.DAILY.IP",  "sector": "Financials"},
    "ULVR.L":   {"epic": "SE.D.ULVR.DAILY.IP",  "sector": "Consumer"},
    "BP.L":     {"epic": "SE.D.BP.DAILY.IP",    "sector": "Energy"},

    # --- FINANCIALS & INDUSTRIALS ---
    "JPM":      {"epic": "UC.D.JPM.DAILY.IP",   "sector": "Financials"},
    "BAC":      {"epic": "UC.D.BAC.DAILY.IP",   "sector": "Financials"},
    "CAT":      {"epic": "UC.D.CAT.DAILY.IP",   "sector": "Industrials"},
    "GE":       {"epic": "UC.D.GE.DAILY.IP",    "sector": "Industrials"},

    # --- CONSUMER & RETAIL ---
    "PG":       {"epic": "UC.D.PG.DAILY.IP",    "sector": "Consumer"},
    "KO":       {"epic": "UC.D.KO.DAILY.IP",    "sector": "Consumer"},
    "COST":     {"epic": "UC.D.COST.DAILY.IP",  "sector": "Consumer"},
    "CROX":     {"epic": "UC.D.CROX.DAILY.IP",  "sector": "Consumer"},
    "DUOL":     {"epic": "UC.D.DUOL.DAILY.IP",  "sector": "Consumer"},
    "ELF":      {"epic": "UC.D.ELF.DAILY.IP",   "sector": "Consumer"},
    "CELH":     {"epic": "UC.D.CELH.DAILY.IP",  "sector": "Consumer"},
    "WING":     {"epic": "UC.D.WING.DAILY.IP",  "sector": "Consumer"},
    "BOOT":     {"epic": "UC.D.BOOT.DAILY.IP",  "sector": "Consumer"},
    "NIO":      {"epic": "UC.D.NIO.DAILY.IP",   "sector": "Consumer"}
}

# Risk Parameters
MAX_POSITIONS_PER_SECTOR = 2
RISK_PCT_PER_TRADE = 0.01   # Risk 1% of cash per trade
DEFAULT_STOP_DISTANCE = 20  # Fallback 20 points stop-loss


def connect_to_ig():
    if not all([IG_USERNAME, IG_PASSWORD, IG_API_KEY, IG_ACC_NUMBER]):
        print("❌ Error: Missing IG credentials in environment variables.")
        sys.exit(1)

    print("🔌 Connecting to IG Demo API...")
    ig_service = IGService(IG_USERNAME, IG_PASSWORD, IG_API_KEY, IG_ACC_TYPE)
    ig_service.create_session()
    
    try:
        ig_service.switch_account(IG_ACC_NUMBER, False)
        print(f"✅ Active Account ID: {IG_ACC_NUMBER}")
    except Exception as e:
        print(f"ℹ️ Account notice: {e}")

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
    return 20000.0


def calculate_stake_size(available_cash, stop_loss_points=20):
    risk_amount = available_cash * RISK_PCT_PER_TRADE
    stake = risk_amount / stop_loss_points
    max_stake = 5.0  # Safety cap at £5/point
    return max(min(round(stake, 2), max_stake), 0.50)


def count_sector_positions(open_positions):
    sector_counts = {}
    if isinstance(open_positions, pd.DataFrame) and not open_positions.empty and "epic" in open_positions.columns:
        active_epics = open_positions["epic"].tolist()
        for ticker, data in EPIC_MAP.items():
            if data["epic"] in active_epics:
                sec = data["sector"]
                sector_counts[sec] = sector_counts.get(sec, 0) + 1
    return sector_counts


def load_screener_candidates():
    filename = "top_candidates.json"
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
                candidates = json.load(f)
                print(f"📋 Loaded {len(candidates)} candidates from {filename}.")
                return candidates
        except Exception as e:
            print(f"⚠️ Error reading {filename}: {e}")
    
    print("⚠️ Warning: top_candidates.json not found or invalid.")
    return []


def execute_ig_trade(ig_service, ticker, epic, sector, open_positions, sector_counts, available_cash, atr_points):
    # 1. Prevent duplicate position entries
    if isinstance(open_positions, pd.DataFrame) and not open_positions.empty and "epic" in open_positions.columns:
        if epic in open_positions["epic"].tolist():
            print(f"ℹ️ Active position already exists for {ticker} ({epic}). Skipping.")
            return

    # 2. Enforce Sector Concentration Cap
    current_sector_trades = sector_counts.get(sector, 0)
    if current_sector_trades >= MAX_POSITIONS_PER_SECTOR:
        print(f"🛡️ Sector Limit Reached: {sector} already has {current_sector_trades} active trades. Skipping {ticker}.")
        return

    stop_dist = atr_points if atr_points and atr_points >= 10 else DEFAULT_STOP_DISTANCE
    stake_size = calculate_stake_size(available_cash, stop_loss_points=stop_dist)
    
    print(f"🚀 Placing BUY Trade on {ticker} ({sector}) @ £{stake_size}/point (Stop: {stop_dist} pts)...")
    try:
        # Fully explicit argument signature required by trading-ig package
        response = ig_service.create_open_position(
            currency_code="GBP",
            direction="BUY",
            epic=epic,
            expiry="-",
            force_open=True,
            guaranteed_stop=False,
            level=None,
            limit_distance=None,
            limit_level=None,
            order_type="MARKET",
            quote_id=None,
            size=stake_size,
            stop_distance=int(stop_dist),
            stop_level=None,
            trailing_stop=True,
            trailing_stop_increment=1.0
        )
        deal_ref = response.get("dealReference", "Success") if isinstance(response, dict) else "Executed"
        print(f"✅ Order executed for {ticker} | Ref: {deal_ref}")
        
        sector_counts[sector] = sector_counts.get(sector, 0) + 1
    except Exception as e:
        print(f"❌ Trade execution failed for {ticker}: {e}")


def run_bot():
    ig_service = connect_to_ig()
    available_cash = get_account_balance(ig_service)
    
    open_positions = ig_service.fetch_open_positions()
    sector_counts = count_sector_positions(open_positions)
    
    candidates = load_screener_candidates()
    if not candidates:
        print("🛑 Execution halt: No candidates passed from screener.")
        return

    print("\n=== EXECUTING IG SPREAD BET TRADES FROM SCREENER ===")
    
    for item in candidates:
        ticker = item.get("Ticker")
        signal = item.get("Signal", "HOLD")
        atr_pts = item.get("ATR_Points", DEFAULT_STOP_DISTANCE)
        
        if signal not in ["BUY", "STRONG BUY"]:
            print(f"⏩ Skipping {ticker}: Signal is {signal}")
            continue

        meta = EPIC_MAP.get(ticker)
        if not meta:
            print(f"⚠️ Skipped {ticker}: Missing IG EPIC mapping. Add to EPIC_MAP.")
            continue
            
        epic = meta["epic"]
        sector = meta["sector"]
        
        execute_ig_trade(ig_service, ticker, epic, sector, open_positions, sector_counts, available_cash, atr_pts)

    print("\n=== EXECUTION COMPLETE ===")


if __name__ == "__main__":
    run_bot()
